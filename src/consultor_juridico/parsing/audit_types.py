"""Tipos imutáveis da auditoria estrutural pré-materialização."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AuditSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKER = "BLOCKER"


class MaterializationGate(StrEnum):
    APPROVED = "APPROVED_FOR_MATERIALIZATION"
    BLOCKED = "BLOCKED_FOR_MATERIALIZATION"


class ArticleDuplicateKind(StrEnum):
    SAME_LEGAL_DEVICE_HISTORICAL_REDACTION = "SAME_LEGAL_DEVICE_HISTORICAL_REDACTION"
    DISTINCT_DOCUMENT_OCCURRENCE = "DISTINCT_DOCUMENT_OCCURRENCE"
    PARSER_DUPLICATION = "PARSER_DUPLICATION"
    STRUCTURAL_AMBIGUITY = "STRUCTURAL_AMBIGUITY"


class UnclassifiedBlockKind(StrEnum):
    EMPTY_PRESENTATION = "EMPTY_PRESENTATION"
    EDITORIAL_SPACING = "EDITORIAL_SPACING"
    SIGNATURE_BLOCK = "SIGNATURE_BLOCK"
    NAVIGATION_ARTIFACT = "NAVIGATION_ARTIFACT"
    TECHNICAL_ARTIFACT = "TECHNICAL_ARTIFACT"
    EDITORIAL_NOTICE = "EDITORIAL_NOTICE"
    NON_NORMATIVE_FOOTER = "NON_NORMATIVE_FOOTER"
    HISTORICAL_RUBRIC_MODEL_GAP = "HISTORICAL_RUBRIC_MODEL_GAP"
    PARSER_MISSED_STRUCTURE = "PARSER_MISSED_STRUCTURE"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


@dataclass(frozen=True, slots=True)
class AuditFinding:
    code: str
    severity: AuditSeverity
    act: str
    element_type: str | None
    number_label: str | None
    block_index: int | None
    message: str
    evidence: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ArticleOccurrence:
    act: str
    number_label: str
    structural_key: str
    document_order: int
    block_index: int
    source_line: int | None
    article_raw_text: str
    caput_raw_text: str
    caput_status: str
    ancestry: tuple[str, ...]
    classification_rule: str | None


@dataclass(frozen=True, slots=True)
class DuplicateArticleGroup:
    act: str
    number_label: str
    structural_key: str
    kind: ArticleDuplicateKind
    occurrences: tuple[ArticleOccurrence, ...]


@dataclass(frozen=True, slots=True)
class UnclassifiedBlockAudit:
    act: str
    block_index: int
    source_line: int | None
    normalized_text: str
    anchors: tuple[str, ...]
    contains_strike: bool
    inside_table: bool
    current_ignore_reason: str
    diagnostic_kind: UnclassifiedBlockKind


@dataclass(frozen=True, slots=True)
class ActAudit:
    act: str
    total_elements: int
    total_articles: int
    unique_article_labels: int
    duplicate_labels: tuple[str, ...]
    duplicate_groups: tuple[DuplicateArticleGroup, ...]
    article_caput_anomalies: int
    unclassified_blocks: tuple[UnclassifiedBlockAudit, ...]
    unresolved_by_type: dict[str, int]
    unresolved_by_cause: dict[str, int]
    historical_by_type: dict[str, int]
    revoked_by_type: dict[str, int]
    strike_status_matrix: dict[str, dict[str, int]]
    notes_by_role: dict[str, int]
    notes_by_parent_type: dict[str, int]
    notes_by_article: dict[str, int]
    elements_per_block: dict[str, int]
    unusual_block_reuse: tuple[int, ...]
    parent_child_matrix: dict[str, int]
    depth_distribution: dict[str, int]
    maximum_depth_path: tuple[dict[str, Any], ...]
    coverage: dict[str, Any]
    provenance: dict[str, int]
    alphanumeric_article_labels: tuple[str, ...]
    findings: tuple[AuditFinding, ...]


@dataclass(frozen=True, slots=True)
class StructuralAuditReport:
    cf88: ActAudit
    adct: ActAudit
    findings: tuple[AuditFinding, ...]
    gate: MaterializationGate
    fingerprint_sha256: str
