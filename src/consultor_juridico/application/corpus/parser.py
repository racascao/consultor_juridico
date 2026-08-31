"""Parser estrutural determinístico da Lei 9.784/1999."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from consultor_juridico.domain.corpus import (
    CoverageRecord,
    IgnoreReason,
    LegalStatus,
    ParsedDocument,
    ParsedProvision,
    ProvisionType,
    SourceLocator,
    UnsupportedSourceStructure,
    decode_strict,
    through_first_html_close,
)

_CHAPTER = re.compile(r"^CAPÍTULO\s+([IVXLCDM]+(?:-[A-Z])?)(?:\s+(.+))?$", re.I)
_ARTICLE = re.compile(r"^Art\.\s*(\d+(?:-[A-Z])?)\s*(?:[.º]|o)?\s+(.*)$", re.I)
_NUMBERED_PARAGRAPH = re.compile(r"^§\s*(\d+)\s*(?:[º°]|o)?\s+(.*)$", re.I)
_UNIQUE_PARAGRAPH = re.compile(r"^Parágrafo\s+único\.\s*(.*)$", re.I)
_INCISO = re.compile(r"^([IVXLCDM]+)\s*[-–]\s+(.+)$")
_LAW_HEADER = re.compile(r"^LEI\s+N[ºO]", re.I)


@dataclass(frozen=True, slots=True)
class _Paragraph:
    index: int
    text: str
    anchor_name: str | None


def _normalize_presentation(text: str) -> str:
    compact = " ".join(text.split())
    return re.sub(r"\s+([,.;:])", r"\1", compact)


def _anchor(node: Tag) -> str | None:
    anchor = node.find("a", attrs={"name": True})
    return str(anchor["name"]) if anchor else None


def _locator(paragraph: _Paragraph, end: int | None = None) -> SourceLocator:
    return SourceLocator(paragraph.index, end or paragraph.index, paragraph.anchor_name)


class PlanaltoLeiParser:
    """Reconhece somente as classes estruturais comprovadas na fonte piloto."""

    def parse(self, raw_bytes: bytes, *, encoding: str) -> ParsedDocument:
        decoded = decode_strict(raw_bytes, encoding)
        document_html = through_first_html_close(decoded)
        soup = BeautifulSoup(document_html, "html.parser")
        paragraphs = tuple(
            _Paragraph(
                i,
                _normalize_presentation(node.get_text(" ", strip=True)),
                _anchor(node),
            )
            for i, node in enumerate(soup.find_all("p"))
        )
        return self._parse_paragraphs(paragraphs)

    def _parse_paragraphs(self, paragraphs: tuple[_Paragraph, ...]) -> ParsedDocument:
        non_empty = tuple(p for p in paragraphs if p.text)
        law_header = next((p for p in non_empty if _LAW_HEADER.match(p.text)), None)
        first_chapter = next((p for p in non_empty if _CHAPTER.match(p.text)), None)
        if (
            law_header is None
            or first_chapter is None
            or law_header.index >= first_chapter.index
        ):
            raise UnsupportedSourceStructure(
                -1, "", "preâmbulo/capítulo inicial ausente"
            )

        structural_indices = [
            p.index
            for p in non_empty
            if _CHAPTER.match(p.text)
            or _ARTICLE.match(p.text)
            or _NUMBERED_PARAGRAPH.match(p.text)
            or _UNIQUE_PARAGRAPH.match(p.text)
            or _INCISO.match(p.text)
        ]
        last_structural = max(structural_indices)
        coverage: dict[int, CoverageRecord] = {}
        provisions: list[ParsedProvision] = []
        order = 1

        root_parts = [
            p
            for p in paragraphs
            if law_header.index <= p.index < first_chapter.index and p.text
        ]
        root_text = "\n".join(p.text for p in root_parts)
        provisions.append(
            ParsedProvision(
                ProvisionType.DOCUMENT_ROOT,
                "PREAMBLE",
                None,
                root_text,
                SourceLocator(
                    root_parts[0].index, root_parts[-1].index, root_parts[0].anchor_name
                ),
                order,
            )
        )
        order += 1
        for paragraph in root_parts:
            coverage[paragraph.index] = CoverageRecord(
                paragraph.index, consumed_by="PREAMBLE"
            )

        current_chapter = "PREAMBLE"
        current_article: str | None = None
        current_text_parent: str | None = None
        skipped: set[int] = set()

        for position, paragraph in enumerate(paragraphs):
            if paragraph.index in skipped or paragraph.index in coverage:
                continue
            if not paragraph.text:
                coverage[paragraph.index] = CoverageRecord(
                    paragraph.index, ignored_reason=IgnoreReason.EMPTY_PRESENTATION
                )
                continue
            if paragraph.index < law_header.index or paragraph.index > last_structural:
                coverage[paragraph.index] = CoverageRecord(
                    paragraph.index, ignored_reason=IgnoreReason.NON_LEGAL_PAGE_CHROME
                )
                continue

            chapter_match = _CHAPTER.match(paragraph.text)
            if chapter_match:
                label = chapter_match.group(1).upper()
                parts = [paragraph]
                if chapter_match.group(2) is None:
                    for following in paragraphs[position + 1 :]:
                        if not following.text:
                            continue
                        if self._is_structural_start(following.text):
                            break
                        parts.append(following)
                        skipped.add(following.index)
                key = f"CHAPTER:{label}"
                provisions.append(
                    ParsedProvision(
                        ProvisionType.CHAPTER,
                        key,
                        label,
                        "\n".join(part.text for part in parts),
                        SourceLocator(
                            paragraph.index, parts[-1].index, paragraph.anchor_name
                        ),
                        order,
                        parent_stable_key="PREAMBLE",
                    )
                )
                order += 1
                current_chapter = key
                current_article = None
                current_text_parent = None
                for part in parts:
                    coverage[part.index] = CoverageRecord(part.index, consumed_by=key)
                continue

            article_match = _ARTICLE.match(paragraph.text)
            if article_match:
                label = article_match.group(1).upper()
                article_key = f"ARTICLE:{label}"
                caput_key = f"{article_key}/CAPUT"
                status = self._status(paragraph.text)
                provisions.extend(
                    (
                        ParsedProvision(
                            ProvisionType.ARTICLE,
                            article_key,
                            label,
                            None,
                            _locator(paragraph),
                            order,
                            status,
                            current_chapter,
                        ),
                        ParsedProvision(
                            ProvisionType.CAPUT,
                            caput_key,
                            None,
                            paragraph.text,
                            _locator(paragraph),
                            order + 1,
                            status,
                            article_key,
                        ),
                    )
                )
                order += 2
                current_article = article_key
                current_text_parent = caput_key
                coverage[paragraph.index] = CoverageRecord(
                    paragraph.index, consumed_by=caput_key
                )
                continue

            paragraph_match = _NUMBERED_PARAGRAPH.match(paragraph.text)
            unique_match = _UNIQUE_PARAGRAPH.match(paragraph.text)
            if paragraph_match or unique_match:
                if current_article is None:
                    raise UnsupportedSourceStructure(
                        paragraph.index, paragraph.text, "parágrafo sem artigo"
                    )
                label = paragraph_match.group(1) if paragraph_match else "UNIQUE"
                key = f"{current_article}/PARAGRAPH:{label}"
                provisions.append(
                    ParsedProvision(
                        ProvisionType.PARAGRAPH,
                        key,
                        label,
                        paragraph.text,
                        _locator(paragraph),
                        order,
                        self._status(paragraph.text),
                        current_article,
                    )
                )
                order += 1
                current_text_parent = key
                coverage[paragraph.index] = CoverageRecord(
                    paragraph.index, consumed_by=key
                )
                continue

            inciso_match = _INCISO.match(paragraph.text)
            if inciso_match:
                if current_text_parent is None:
                    raise UnsupportedSourceStructure(
                        paragraph.index, paragraph.text, "inciso sem caput/parágrafo"
                    )
                label = inciso_match.group(1)
                key = f"{current_text_parent}/INCISO:{label}"
                provisions.append(
                    ParsedProvision(
                        ProvisionType.INCISO,
                        key,
                        label,
                        paragraph.text,
                        _locator(paragraph),
                        order,
                        self._status(paragraph.text),
                        current_text_parent,
                    )
                )
                order += 1
                coverage[paragraph.index] = CoverageRecord(
                    paragraph.index, consumed_by=key
                )
                continue

            raise UnsupportedSourceStructure(
                paragraph.index, paragraph.text, "texto jurídico não reconhecido"
            )

        ordered_coverage = tuple(coverage[i] for i in range(len(paragraphs)))
        return ParsedDocument(
            tuple(provisions),
            ordered_coverage,
            total_dom_paragraphs=len(paragraphs),
            non_empty_paragraphs=len(non_empty),
        )

    @staticmethod
    def _is_structural_start(text: str) -> bool:
        return bool(
            _CHAPTER.match(text)
            or _ARTICLE.match(text)
            or _NUMBERED_PARAGRAPH.match(text)
            or _UNIQUE_PARAGRAPH.match(text)
            or _INCISO.match(text)
        )

    @staticmethod
    def _status(text: str) -> LegalStatus:
        return (
            LegalStatus.VETOED if "(VETADO)" in text.upper() else LegalStatus.IN_FORCE
        )
