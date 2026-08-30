"""Adapter determinístico do parser constitucional comprovado para o domínio v0.2."""

from __future__ import annotations

import json
import re
from datetime import date
from uuid import NAMESPACE_URL, uuid5

from consultor_juridico.domain import (
    DuplicateProvisionStableKey,
    ParsedAct,
    ParsedCorpus,
    ParsedMetadata,
    ParsedProvision,
    ProvisionType,
    SourceCapture,
)
from consultor_juridico.parsing.blocks import DocumentBlock, enumerate_document_blocks
from consultor_juridico.parsing.decoder import decode_raw_document
from consultor_juridico.parsing.dom import build_dom
from consultor_juridico.parsing.legal_parser import parse_constitution
from consultor_juridico.parsing.legal_types import (
    ContentRole,
    ElementType,
    ParsedLegalAct,
    ParsedLegalElement,
    TextStatus,
)
from consultor_juridico.parsing.segmentation import segment_constitution_document

PARSER_VERSION = "constitutional-corpus-v3"
PROMULGATION = re.compile(
    r"Brasília,\s*(?P<day>\d{1,2})\s+de\s+(?P<month>[a-zç]+)\s+de\s+(?P<year>\d{4})",
    re.IGNORECASE,
)
MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}
TYPE_MAP = {
    ElementType.PREAMBLE: ProvisionType.PREAMBLE,
    ElementType.TITLE: ProvisionType.TITLE,
    ElementType.CHAPTER: ProvisionType.CHAPTER,
    ElementType.SECTION: ProvisionType.SECTION,
    ElementType.SUBSECTION: ProvisionType.SUBSECTION,
    ElementType.ARTICLE: ProvisionType.ARTICLE,
    ElementType.CAPUT: ProvisionType.CAPUT,
    ElementType.PARAGRAPH: ProvisionType.PARAGRAPH,
    ElementType.INCISO: ProvisionType.INCISO,
    ElementType.ALINEA: ProvisionType.ALINEA,
    ElementType.ITEM: ProvisionType.ITEM,
}


class ConstitutionCorpusParser:
    def parse(self, capture: SourceCapture) -> ParsedCorpus:
        decoded = decode_raw_document(
            source_document_id=uuid5(NAMESPACE_URL, capture.sha256),
            raw_bytes=capture.raw_bytes,
            expected_sha256=capture.sha256,
            source_url=capture.final_url,
        )
        blocks = enumerate_document_blocks(build_dom(decoded)).blocks
        segments = segment_constitution_document(blocks)
        parsed = parse_constitution(segments)
        promulgation = _promulgation_metadata(blocks)
        cf_metadata = _cf_metadata(parsed.cf88, blocks, promulgation)
        return ParsedCorpus(
            acts=(
                _convert_act(
                    parsed.cf88,
                    "Constituição da República Federativa do Brasil de 1988",
                    "CONSTITUTION",
                    cf_metadata,
                    promulgation.promulgation_date if promulgation else None,
                ),
                _convert_act(
                    parsed.adct,
                    "Ato das Disposições Constitucionais Transitórias",
                    "TRANSITIONAL_PROVISIONS",
                    (),
                    None,
                ),
            ),
            parser_version=PARSER_VERSION,
        )


def _convert_act(
    source: ParsedLegalAct,
    title: str,
    act_type: str,
    metadata: tuple[ParsedMetadata, ...],
    promulgation_date: date | None,
) -> ParsedAct:
    roots = _convert_occurrences(source.root.children)
    return ParsedAct(
        code=source.act_code,
        title=title,
        act_type=act_type,
        root_provisions=roots,
        metadata=metadata,
        promulgation_date=promulgation_date,
    )


def _convert_provision(element: ParsedLegalElement) -> ParsedProvision | None:
    provision_type = TYPE_MAP.get(element.element_type)
    if provision_type is None:
        return None
    children = _convert_occurrences(element.children)
    stable_key = element.identity_key
    if stable_key is None:
        return None
    return ParsedProvision(
        stable_key=stable_key,
        provision_type=provision_type,
        label=element.number_label,
        document_order=element.document_order,
        citation_text=element.raw_text,
        source_locator=json.dumps(
            element.source_locator,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        children=children,
    )


def _convert_occurrences(
    elements: tuple[ParsedLegalElement, ...],
) -> tuple[ParsedProvision, ...]:
    """Seleciona a ocorrência consolidada sem apagar ambiguidades ativas."""
    grouped: dict[str, list[ParsedLegalElement]] = {}
    order: list[str] = []
    for element in elements:
        if element.identity_key is None or element.element_type not in TYPE_MAP:
            continue
        if element.identity_key not in grouped:
            grouped[element.identity_key] = []
            order.append(element.identity_key)
        grouped[element.identity_key].append(element)

    converted: list[ParsedProvision] = []
    for identity_key in order:
        selected = _select_consolidated_occurrence(grouped[identity_key])
        if selected is None:
            continue
        provision = _convert_provision(selected)
        if provision is not None:
            converted.append(provision)
    return tuple(converted)


def _select_consolidated_occurrence(
    occurrences: list[ParsedLegalElement],
) -> ParsedLegalElement | None:
    normative = [
        item for item in occurrences if item.content_role is ContentRole.NORMATIVE
    ]
    current = [item for item in normative if item.text_status is TextStatus.CURRENT]
    if len(current) == 1:
        return current[0]
    if len(current) > 1:
        _raise_occurrence_collision(current)

    unresolved = [
        item for item in normative if item.text_status is TextStatus.UNRESOLVED
    ]
    if len(unresolved) == 1:
        return unresolved[0]
    if len(unresolved) > 1:
        _raise_occurrence_collision(unresolved)
    return None


def _raise_occurrence_collision(occurrences: list[ParsedLegalElement]) -> None:
    first, second = occurrences[:2]
    raise DuplicateProvisionStableKey(
        first.identity_key or "<sem-identity-key>",
        json.dumps(first.source_locator, ensure_ascii=False, sort_keys=True),
        json.dumps(second.source_locator, ensure_ascii=False, sort_keys=True),
    )


def _promulgation_metadata(
    blocks: tuple[DocumentBlock, ...],
) -> ParsedMetadata | None:
    for block in blocks:
        match = PROMULGATION.search(block.text)
        if match is None:
            continue
        month = MONTHS.get(match.group("month").casefold())
        if month is None:
            continue
        return ParsedMetadata(
            kind="PROMULGATION",
            citation_text=match.group(0),
            source_locator=f"block:{block.block_index}",
            promulgation_date=date(
                int(match.group("year")), month, int(match.group("day"))
            ),
        )
    return None


def _cf_metadata(
    act: ParsedLegalAct,
    blocks: tuple[DocumentBlock, ...],
    promulgation: ParsedMetadata | None,
) -> tuple[ParsedMetadata, ...]:
    preambles = tuple(
        ParsedMetadata(
            kind="PREAMBLE",
            citation_text=element.raw_text,
            source_locator=json.dumps(element.source_locator, sort_keys=True),
        )
        for element in act.root.children
        if element.element_type is ElementType.PREAMBLE
    )
    identification = next(
        (
            ParsedMetadata(
                kind="DOCUMENT_IDENTIFICATION",
                citation_text=block.text.strip(),
                source_locator=f"block:{block.block_index}",
            )
            for block in blocks
            if "constituição da república federativa do brasil"
            in block.normalized_text_for_matching
        ),
        None,
    )
    return (
        *((identification,) if identification else ()),
        *preambles,
        *((promulgation,) if promulgation else ()),
    )
