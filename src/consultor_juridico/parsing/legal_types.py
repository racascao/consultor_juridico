"""Representação jurídica imutável produzida exclusivamente em memória."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ElementType(StrEnum):
    DOCUMENT_ROOT = "DOCUMENT_ROOT"
    PREAMBLE = "PREAMBLE"
    TITLE = "TITLE"
    CHAPTER = "CHAPTER"
    SECTION = "SECTION"
    SUBSECTION = "SUBSECTION"
    ARTICLE = "ARTICLE"
    CAPUT = "CAPUT"
    PARAGRAPH = "PARAGRAPH"
    INCISO = "INCISO"
    ALINEA = "ALINEA"
    ITEM = "ITEM"
    NOTE = "NOTE"


class TextStatus(StrEnum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"
    REVOKED = "REVOKED"
    UNRESOLVED = "UNRESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ContentRole(StrEnum):
    NORMATIVE = "NORMATIVE"
    AMENDMENT_NOTE = "AMENDMENT_NOTE"
    REFERENCE_NOTE = "REFERENCE_NOTE"
    EDITORIAL_NOTE = "EDITORIAL_NOTE"


class CoverageDisposition(StrEnum):
    CONSUMED = "CONSUMED"
    IGNORED_WITH_REASON = "IGNORED_WITH_REASON"


class IgnoredBlockReason(StrEnum):
    EMPTY_PRESENTATION_BLOCK = "empty_presentation_block"
    STRUCTURAL_RUBRIC_MERGED = "structural_rubric_merged"
    DOCUMENT_HEADER_REPRESENTED_BY_ROOT = "document_header_represented_by_root"
    UNCLASSIFIED_BLOCK = "unclassified_block"


@dataclass(frozen=True, slots=True)
class ParsedLegalElement:
    element_type: ElementType
    number_label: str | None
    raw_text: str
    normalized_text: str
    text_status: TextStatus
    content_role: ContentRole
    document_order: int
    source_locator: dict[str, Any]
    parser_metadata: dict[str, Any] | None
    identity_key: str | None
    children: tuple["ParsedLegalElement", ...]


@dataclass(frozen=True, slots=True)
class ParsedLegalProvision:
    """Identidade normativa reconciliada, sem texto ou posição documental."""

    identity_key: str
    parent_identity_key: str | None
    element_type: ElementType
    number_label: str | None


@dataclass(frozen=True, slots=True)
class BlockCoverage:
    block_index: int
    disposition: CoverageDisposition
    reason: IgnoredBlockReason | None
    produced_element_types: tuple[ElementType, ...]


@dataclass(frozen=True, slots=True)
class CoverageReport:
    total_blocks: int
    consumed_blocks: int
    ignored_blocks: int
    coverage_ratio: float
    ignored_by_reason: dict[str, int]
    entries: tuple[BlockCoverage, ...]


@dataclass(frozen=True, slots=True)
class ParsedLegalAct:
    act_code: str
    root: ParsedLegalElement
    coverage: CoverageReport
    fingerprint_sha256: str
    provisions: tuple[ParsedLegalProvision, ...]


@dataclass(frozen=True, slots=True)
class ParsedConstitution:
    cf88: ParsedLegalAct
    adct: ParsedLegalAct
    parsing_duration_ms: float
