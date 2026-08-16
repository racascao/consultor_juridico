"""Parser jurídico determinístico da CF/88 e ADCT, exclusivamente em memória."""

import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field, replace
from time import perf_counter
from typing import Any

from consultor_juridico.parsing.blocks import DocumentBlock
from consultor_juridico.parsing.errors import (
    DocumentCoverageError,
    LegalHierarchyError,
    LegalStructureValidationError,
)
from consultor_juridico.parsing.legal_types import (
    BlockCoverage,
    ContentRole,
    CoverageDisposition,
    CoverageReport,
    ElementType,
    IgnoredBlockReason,
    ParsedConstitution,
    ParsedLegalAct,
    ParsedLegalElement,
    ParsedLegalProvision,
    TextStatus,
)
from consultor_juridico.parsing.segmentation import ConstitutionDocumentSegments

ARTICLE = re.compile(r"^\s*Art\.\s*(\d+[º°.]?(?:\s*-\s*[A-Z])?)\s*(.*)$", re.I | re.S)
PARAGRAPH = re.compile(r"^\s*§\s*(\d+[º°.]?(?:\s*-\s*[A-Z])?)\s*(.*)$", re.I | re.S)
SOLE_PARAGRAPH = re.compile(r"^\s*Parágrafo\s+único[.:]?\s*(.*)$", re.I | re.S)
INCISO = re.compile(r"^\s*([IVXLCDM]+(?:-?[A-Z])?)(?:\s*[-–—]\s*|\s+)(\S.*)$", re.S)
ALINEA = re.compile(r"^\s*([a-z])\s*\)\s*(.*)$", re.I | re.S)
ITEM = re.compile(r"^\s*(\d+)\s*[.)-]\s*(.*)$", re.S)
DIVISIONS = (
    (ElementType.TITLE, re.compile(r"^TÍTULO\s+([IVXLCDM]+(?:-[A-Z])?)$", re.I)),
    (ElementType.CHAPTER, re.compile(r"^CAPÍTULO\s+([IVXLCDM]+(?:-[A-Z])?)$", re.I)),
    (ElementType.SECTION, re.compile(r"^SEÇÃO\s+([IVXLCDM]+(?:-[A-Z])?)$", re.I)),
    (ElementType.SUBSECTION, re.compile(r"^SUBSEÇÃO\s+([IVXLCDM]+(?:-[A-Z])?)$", re.I)),
)
NOTE_PATTERN = re.compile(
    r"\(([^()]*(?:Emenda Constitucional|Vide\b|Regulamento|Vigência|"
    r"Produção de efeito)[^()]*)\)",
    re.I,
)
NUMBERED_TYPES = {
    ElementType.TITLE,
    ElementType.CHAPTER,
    ElementType.SECTION,
    ElementType.SUBSECTION,
    ElementType.ARTICLE,
    ElementType.PARAGRAPH,
    ElementType.INCISO,
    ElementType.ALINEA,
    ElementType.ITEM,
}


@dataclass(slots=True)
class _Node:
    element_type: ElementType
    number_label: str | None
    raw_text: str
    text_status: TextStatus
    content_role: ContentRole
    source_locator: dict[str, Any]
    parser_metadata: dict[str, Any] | None = None
    children: list["_Node"] = field(default_factory=list)


class _ActParser:
    def __init__(self, act_code: str, blocks: tuple[DocumentBlock, ...]) -> None:
        self.act_code = act_code
        self.blocks = blocks
        root_block = blocks[0]
        self.root = _Node(
            ElementType.DOCUMENT_ROOT,
            None,
            "Constituição Federal de 1988"
            if act_code == "CF88"
            else "Ato das Disposições Constitucionais Transitórias",
            TextStatus.CURRENT,
            ContentRole.NORMATIVE,
            _locator(root_block),
            {"synthetic_structure": True, "classification_rule": "act_root"},
        )
        self.context: dict[ElementType, _Node | None] = {
            kind: None
            for kind in (
                ElementType.TITLE,
                ElementType.CHAPTER,
                ElementType.SECTION,
                ElementType.SUBSECTION,
                ElementType.ARTICLE,
                ElementType.PARAGRAPH,
                ElementType.INCISO,
                ElementType.ALINEA,
            )
        }
        self.coverage: dict[int, BlockCoverage] = {}

    def parse(self) -> ParsedLegalAct:
        index = 0
        while index < len(self.blocks):
            block = self.blocks[index]
            if self.act_code == "ADCT" and index == 0:
                self._consumed(block, (ElementType.DOCUMENT_ROOT,))
                index += 1
                continue
            if (
                self.act_code == "CF88"
                and block.normalized_text_for_matching == "preâmbulo"
            ):
                next_block = (
                    self.blocks[index + 1] if index + 1 < len(self.blocks) else block
                )
                text = next_block.text.strip() or block.text.strip()
                node = self._node(ElementType.PREAMBLE, None, text, next_block)
                self.root.children.append(node)
                self._consumed(block, (ElementType.PREAMBLE,))
                if next_block is not block:
                    self._consumed(next_block, (ElementType.PREAMBLE,))
                    index += 1
                index += 1
                continue

            division = self._division(block)
            if division is not None:
                kind, label = division
                notes: list[DocumentBlock] = []
                cursor = index + 1
                while cursor < len(self.blocks) and self._is_note(
                    self.blocks[cursor].text
                ):
                    notes.append(self.blocks[cursor])
                    cursor += 1
                rubrics: list[DocumentBlock] = []
                while cursor < len(self.blocks) and re.match(
                    r"^(?:do|da|dos|das)\s+",
                    self.blocks[cursor].normalized_text_for_matching,
                ):
                    rubrics.append(self.blocks[cursor])
                    cursor += 1
                rubric = rubrics[0] if rubrics else None
                raw = block.text.strip()
                metadata: dict[str, Any] = {"classification_rule": "division_marker"}
                if rubric is not None and rubric.text.strip():
                    raw = f"{raw}\n{rubric.text.strip()}"
                source_blocks = [block.block_index]
                source_blocks.extend(note.block_index for note in notes)
                if rubric is not None:
                    source_blocks.append(rubric.block_index)
                if len(source_blocks) > 1:
                    metadata["source_blocks"] = source_blocks
                node = self._node(kind, label, raw, block, metadata=metadata)
                if rubric is not None:
                    node.text_status = _status(rubric)
                self._attach_division(kind, node)
                self._consumed(block, (kind,))
                for note_block in notes:
                    node.children.append(
                        self._note(note_block, note_block.text.strip())
                    )
                    self._consumed(note_block, (ElementType.NOTE,))
                if rubric is not None:
                    self._consumed(rubric, (kind,))
                for alternative in rubrics[1:]:
                    alternative_node = self._node(
                        kind,
                        label,
                        alternative.text.strip(),
                        alternative,
                        metadata={"classification_rule": "alternative_rubric"},
                    )
                    self._attach_division(kind, alternative_node)
                    self._consumed(alternative, (kind,))
                index = cursor
                continue

            if match := ARTICLE.match(block.text):
                self._parse_article(block, match)
            elif match := SOLE_PARAGRAPH.match(block.text):
                self._parse_subdivision(
                    block, ElementType.PARAGRAPH, "único", match.group(1)
                )
            elif match := PARAGRAPH.match(block.text):
                self._parse_subdivision(
                    block,
                    ElementType.PARAGRAPH,
                    _number_label(match.group(1)),
                    match.group(2),
                )
            elif match := INCISO.match(block.text):
                self._parse_subdivision(
                    block, ElementType.INCISO, match.group(1).upper(), match.group(2)
                )
            elif match := ALINEA.match(block.text):
                self._parse_subdivision(
                    block, ElementType.ALINEA, match.group(1), match.group(2)
                )
            elif self.context[ElementType.ALINEA] is not None and (
                match := ITEM.match(block.text)
            ):
                self._parse_subdivision(
                    block, ElementType.ITEM, match.group(1), match.group(2)
                )
            elif self._is_note(block.text):
                note = self._note(block, block.text.strip())
                self._current_parent().children.append(note)
                self._consumed(block, (ElementType.NOTE,))
            elif not block.text.strip():
                self._ignored(block, IgnoredBlockReason.EMPTY_PRESENTATION_BLOCK)
            else:
                self._ignored(block, IgnoredBlockReason.UNCLASSIFIED_BLOCK)
            index += 1

        frozen, provisions = _freeze_tree(self.act_code, self.root)
        coverage = _coverage_report(self.blocks, self.coverage)
        validate_parsed_act(self.act_code, frozen, self.blocks)
        return ParsedLegalAct(
            self.act_code,
            frozen,
            coverage,
            _tree_fingerprint(frozen, coverage, provisions),
            provisions,
        )

    def _parse_article(self, block: DocumentBlock, match: re.Match[str]) -> None:
        label, body = _number_label(match.group(1)), match.group(2).strip()
        article = self._node(
            ElementType.ARTICLE,
            label,
            block.text[: match.start(2)].strip(),
            block,
        )
        self._structural_parent().children.append(article)
        self.context[ElementType.ARTICLE] = article
        for kind in (ElementType.PARAGRAPH, ElementType.INCISO, ElementType.ALINEA):
            self.context[kind] = None
        normative, notes = _split_notes(body)
        caput_text = normative.strip() or block.text.strip()
        caput = self._node(
            ElementType.CAPUT,
            None,
            caput_text,
            block,
            metadata={
                "synthetic_structure": True,
                "classification_rule": "article_caput",
            },
        )
        article.children.append(caput)
        for note_text in notes:
            caput.children.append(self._note(block, note_text))
        self._consumed(
            block,
            (
                ElementType.ARTICLE,
                ElementType.CAPUT,
                *(ElementType.NOTE for _ in notes),
            ),
        )

    def _parse_subdivision(
        self, block: DocumentBlock, kind: ElementType, label: str, body: str
    ) -> None:
        parent = self._parent_for(kind)
        normative, notes = _split_notes(body)
        raw = normative.strip() or block.text.strip()
        node = self._node(kind, label, raw, block)
        parent.children.append(node)
        if kind in self.context:
            self.context[kind] = node
        if kind == ElementType.PARAGRAPH:
            self.context[ElementType.INCISO] = None
            self.context[ElementType.ALINEA] = None
        elif kind == ElementType.INCISO:
            self.context[ElementType.ALINEA] = None
        for note_text in notes:
            node.children.append(self._note(block, note_text))
        self._consumed(block, (kind, *(ElementType.NOTE for _ in notes)))

    def _node(
        self,
        kind: ElementType,
        label: str | None,
        raw: str,
        block: DocumentBlock,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> _Node:
        return _Node(
            kind,
            label,
            raw.strip(),
            _status(block),
            ContentRole.NORMATIVE,
            _locator(block),
            _merge_metadata(block, metadata),
        )

    def _note(self, block: DocumentBlock, raw: str) -> _Node:
        return _Node(
            ElementType.NOTE,
            None,
            raw.strip(),
            TextStatus.NOT_APPLICABLE,
            _note_role(raw),
            _locator(block),
            _merge_metadata(block, {"classification_rule": "editorial_note"}),
        )

    def _division(self, block: DocumentBlock) -> tuple[ElementType, str] | None:
        for kind, pattern in DIVISIONS:
            if match := pattern.match(block.normalized_text_for_matching.upper()):
                return kind, match.group(1).upper()
        return None

    def _recognizable(self, block: DocumentBlock) -> bool:
        return bool(
            self._division(block)
            or ARTICLE.match(block.text)
            or PARAGRAPH.match(block.text)
            or SOLE_PARAGRAPH.match(block.text)
            or INCISO.match(block.text)
            or ALINEA.match(block.text)
        )

    def _attach_division(self, kind: ElementType, node: _Node) -> None:
        levels = [
            ElementType.TITLE,
            ElementType.CHAPTER,
            ElementType.SECTION,
            ElementType.SUBSECTION,
        ]
        level = levels.index(kind)
        parent = self.root
        for ancestor in reversed(levels[:level]):
            if self.context[ancestor] is not None:
                parent = self.context[ancestor]  # type: ignore[assignment]
                break
        parent.children.append(node)
        self.context[kind] = node
        for lower in levels[level + 1 :]:
            self.context[lower] = None

    def _structural_parent(self) -> _Node:
        for kind in (
            ElementType.SUBSECTION,
            ElementType.SECTION,
            ElementType.CHAPTER,
            ElementType.TITLE,
        ):
            if self.context[kind] is not None:
                return self.context[kind]  # type: ignore[return-value]
        return self.root

    def _parent_for(self, kind: ElementType) -> _Node:
        article = self.context[ElementType.ARTICLE]
        if article is None:
            raise LegalHierarchyError(f"{kind} sem ARTICLE ancestral.")
        if kind == ElementType.PARAGRAPH:
            return article
        if kind == ElementType.INCISO:
            return self.context[ElementType.PARAGRAPH] or article
        if kind == ElementType.ALINEA:
            parent = self.context[ElementType.INCISO]
        else:
            parent = self.context[ElementType.ALINEA]
        if parent is None:
            raise LegalHierarchyError(f"{kind} sem ancestral compatível.")
        return parent

    def _current_parent(self) -> _Node:
        for kind in (
            ElementType.ALINEA,
            ElementType.INCISO,
            ElementType.PARAGRAPH,
            ElementType.ARTICLE,
        ):
            if self.context[kind] is not None:
                return self.context[kind]  # type: ignore[return-value]
        return self._structural_parent()

    def _is_note(self, text: str) -> bool:
        return bool(
            NOTE_PATTERN.fullmatch(text.strip())
            or re.search(r"Este texto não substitui|Vigência", text, re.I)
        )

    def _consumed(self, block: DocumentBlock, kinds: tuple[ElementType, ...]) -> None:
        self.coverage[block.block_index] = BlockCoverage(
            block.block_index, CoverageDisposition.CONSUMED, None, kinds
        )

    def _ignored(self, block: DocumentBlock, reason: IgnoredBlockReason) -> None:
        self.coverage[block.block_index] = BlockCoverage(
            block.block_index, CoverageDisposition.IGNORED_WITH_REASON, reason, ()
        )


def parse_constitution(segments: ConstitutionDocumentSegments) -> ParsedConstitution:
    started = perf_counter()
    cf88 = _ActParser("CF88", segments.cf_blocks).parse()
    adct = _ActParser("ADCT", segments.adct_blocks).parse()
    return ParsedConstitution(cf88, adct, (perf_counter() - started) * 1000)


def normalize_legal_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\u202f", " ")
    return re.sub(r"\s+", " ", text).strip()


def validate_parsed_act(
    act_code: str, root: ParsedLegalElement, blocks: tuple[DocumentBlock, ...]
) -> None:
    flat = tuple(_walk(root))
    orders = tuple(item.document_order for item in flat)
    if root.element_type != ElementType.DOCUMENT_ROOT or root.document_order != 1:
        raise LegalStructureValidationError(f"Root inválido para {act_code}.")
    if orders != tuple(range(1, len(flat) + 1)):
        raise LegalStructureValidationError(f"document_order inválido para {act_code}.")
    allowed_blocks = {block.block_index for block in blocks}
    for item in flat:
        if not item.raw_text.strip() or not item.normalized_text.strip():
            raise LegalStructureValidationError("Elemento com texto obrigatório vazio.")
        if item.source_locator.get("block_index") not in allowed_blocks:
            raise LegalStructureValidationError("source_locator fora do segmento.")
        if item.element_type in NUMBERED_TYPES and not item.number_label:
            raise LegalStructureValidationError("Elemento numerado sem label.")
        if item.element_type == ElementType.NOTE:
            if item.identity_key is not None:
                raise LegalStructureValidationError("NOTE não pode possuir identidade.")
            if (
                item.content_role == ContentRole.NORMATIVE
                or item.text_status != TextStatus.NOT_APPLICABLE
            ):
                raise LegalStructureValidationError(
                    "NOTE com role/status incompatível."
                )
        elif item.identity_key is None:
            raise LegalStructureValidationError(
                "Ocorrência normativa sem identity_key."
            )
        if item.element_type == ElementType.ARTICLE:
            caputs = [
                child
                for child in item.children
                if child.element_type == ElementType.CAPUT
            ]
            if len(caputs) != 1 or not caputs[0].raw_text.strip():
                raise LegalStructureValidationError(
                    "ARTICLE deve possuir exatamente um CAPUT."
                )


def _freeze_tree(
    act_code: str, root: _Node
) -> tuple[ParsedLegalElement, tuple[ParsedLegalProvision, ...]]:
    counter = iter(range(1, 10_000_000))
    provisions: dict[str, ParsedLegalProvision] = {}

    def freeze(node: _Node, parent_identity_key: str | None) -> ParsedLegalElement:
        order = next(counter)
        identity_key = _identity_key(act_code, parent_identity_key, node)
        if identity_key is not None:
            candidate = ParsedLegalProvision(
                identity_key,
                parent_identity_key,
                node.element_type,
                node.number_label,
            )
            previous = provisions.setdefault(identity_key, candidate)
            if previous != candidate:
                raise LegalStructureValidationError(
                    f"Colisão de identity_key incompatível: {identity_key}."
                )
        children = tuple(freeze(child, identity_key) for child in node.children)
        return ParsedLegalElement(
            node.element_type,
            node.number_label,
            node.raw_text,
            normalize_legal_text(node.raw_text),
            node.text_status,
            node.content_role,
            order,
            node.source_locator,
            node.parser_metadata,
            identity_key,
            children,
        )

    frozen = _resolve_current_collisions(freeze(root, None))
    return frozen, tuple(provisions.values())


def _resolve_current_collisions(root: ParsedLegalElement) -> ParsedLegalElement:
    """Preserva colisões anteriores como UNRESOLVED e mantém uma única CURRENT."""
    current_by_key: dict[str, list[int]] = {}
    for item in _walk(root):
        if (
            item.identity_key
            and item.text_status == TextStatus.CURRENT
            and item.element_type not in {ElementType.ARTICLE, ElementType.CAPUT}
        ):
            current_by_key.setdefault(item.identity_key, []).append(item.document_order)
    demoted = {
        order
        for orders in current_by_key.values()
        if len(orders) > 1
        for order in orders[:-1]
    }

    def rebuild(node: ParsedLegalElement) -> ParsedLegalElement:
        status = node.text_status
        metadata = node.parser_metadata
        if node.document_order in demoted:
            status = TextStatus.UNRESOLVED
            metadata = {
                **(metadata or {}),
                "status_rule": "earlier_current_identity_collision",
            }
        return replace(
            node,
            text_status=status,
            parser_metadata=metadata,
            children=tuple(rebuild(child) for child in node.children),
        )

    return rebuild(root)


def _number_label(label: str) -> str:
    cleaned = re.sub(r"[º°.]", "", label.strip())
    return re.sub(r"\s*-\s*", "-", cleaned).upper()


def canonical_identity_token(label: str) -> str:
    """Canonicaliza somente o token auxiliar de matching normativo."""
    normalized = unicodedata.normalize("NFC", label).strip()
    return re.sub(r"\s+", " ", normalized).upper()


def _identity_key(
    act_code: str, parent_identity_key: str | None, node: _Node
) -> str | None:
    if node.element_type == ElementType.NOTE:
        return None
    if node.element_type == ElementType.DOCUMENT_ROOT:
        return f"{act_code}/@root"
    if parent_identity_key is None:
        raise LegalStructureValidationError("Elemento normativo sem identidade pai.")
    singleton = {
        ElementType.PREAMBLE: "@preamble",
        ElementType.CAPUT: "@caput",
    }
    token = singleton.get(node.element_type)
    if token is None:
        if not node.number_label:
            raise LegalStructureValidationError(
                f"{node.element_type} sem token de identidade."
            )
        token = canonical_identity_token(node.number_label)
    return f"{parent_identity_key}/{node.element_type.value}:{token}"


def _walk(node: ParsedLegalElement):
    yield node
    for child in node.children:
        yield from _walk(child)


def _locator(block: DocumentBlock) -> dict[str, Any]:
    locator: dict[str, Any] = {
        "block_index": block.block_index,
        "tag": block.tag,
        "anchors": list(block.anchors),
    }
    if block.source_line is not None:
        locator["source_line"] = block.source_line
    return locator


def _merge_metadata(
    block: DocumentBlock, metadata: dict[str, Any] | None
) -> dict[str, Any] | None:
    result = dict(metadata or {})
    if block.contains_strike:
        result["strike_coverage"] = "full" if block.fully_struck else "partial"
    if block.links:
        result["links"] = [
            {
                "anchor_text": link.anchor_text,
                "href_original": link.href_original,
                "resolved_url": link.resolved_url,
            }
            for link in block.links
        ]
    return result or None


def _status(block: DocumentBlock) -> TextStatus:
    if re.search(r"Revogad[oa]", block.text, re.I):
        return TextStatus.REVOKED
    if block.contains_strike and re.search(r"Redação dada|Incluído", block.text, re.I):
        return TextStatus.HISTORICAL
    if block.contains_strike:
        return TextStatus.UNRESOLVED
    return TextStatus.CURRENT


def _note_role(text: str) -> ContentRole:
    if re.search(r"Emenda Constitucional|Revogad|Incluído|Redação dada", text, re.I):
        return ContentRole.AMENDMENT_NOTE
    if re.search(r"Vide|Regulamento", text, re.I):
        return ContentRole.REFERENCE_NOTE
    return ContentRole.EDITORIAL_NOTE


def _split_notes(text: str) -> tuple[str, tuple[str, ...]]:
    notes = tuple(match.group(0) for match in NOTE_PATTERN.finditer(text))
    normative = NOTE_PATTERN.sub("", text)
    return normative, notes


def _coverage_report(
    blocks: tuple[DocumentBlock, ...], entries: dict[int, BlockCoverage]
) -> CoverageReport:
    if set(entries) != {block.block_index for block in blocks}:
        raise DocumentCoverageError("Há blocos sem destino explícito na cobertura.")
    ordered = tuple(entries[block.block_index] for block in blocks)
    consumed = sum(item.disposition == CoverageDisposition.CONSUMED for item in ordered)
    reasons = Counter(item.reason.value for item in ordered if item.reason is not None)
    return CoverageReport(
        len(blocks),
        consumed,
        len(blocks) - consumed,
        consumed / len(blocks) if blocks else 0.0,
        dict(sorted(reasons.items())),
        ordered,
    )


def _tree_fingerprint(
    root: ParsedLegalElement,
    coverage: CoverageReport,
    provisions: tuple[ParsedLegalProvision, ...],
) -> str:
    def record(node: ParsedLegalElement):
        return {
            "type": node.element_type,
            "label": node.number_label,
            "raw": node.raw_text,
            "normalized": node.normalized_text,
            "status": node.text_status,
            "role": node.content_role,
            "order": node.document_order,
            "locator": node.source_locator,
            "metadata": node.parser_metadata,
            "identity_key": node.identity_key,
            "children": [record(child) for child in node.children],
        }

    payload = {
        "root": record(root),
        "coverage": [
            {
                "block": item.block_index,
                "disposition": item.disposition,
                "reason": item.reason,
            }
            for item in coverage.entries
        ],
        "provisions": [
            {
                "identity_key": item.identity_key,
                "parent_identity_key": item.parent_identity_key,
                "element_type": item.element_type,
                "number_label": item.number_label,
            }
            for item in provisions
        ],
    }
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def parsed_act_metrics(act: ParsedLegalAct) -> dict[str, Any]:
    flat = tuple(_walk(act.root))
    by_type = Counter(item.element_type.value for item in flat)
    by_status = Counter(item.text_status.value for item in flat)
    by_role = Counter(item.content_role.value for item in flat)

    def depth(node: ParsedLegalElement) -> int:
        return 1 + max((depth(child) for child in node.children), default=0)

    return {
        "total_elements": len(flat),
        "elements_by_type": dict(sorted(by_type.items())),
        "elements_by_text_status": dict(sorted(by_status.items())),
        "elements_by_content_role": dict(sorted(by_role.items())),
        "max_tree_depth": depth(act.root),
        "document_order_min": 1,
        "document_order_max": len(flat),
    }
