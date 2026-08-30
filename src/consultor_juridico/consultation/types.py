"""Contratos imutáveis da consulta jurídica fundamentada."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ConsultationOutcome(StrEnum):
    ANSWERED = "ANSWERED"
    ABSTAINED = "ABSTAINED"


@dataclass(frozen=True, slots=True)
class GeneratedClaim:
    claim_code: str
    text: str
    evidence_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeneratedResponse:
    answer: str
    claims: tuple[GeneratedClaim, ...]
    abstain: bool = False


class AttributionMode(StrEnum):
    SIMPLE = "SIMPLE"
    CLAUSE = "CLAUSE"


class AttributionStatus(StrEnum):
    ATTRIBUTED = "ATTRIBUTED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class ClaimClause:
    index: int
    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class ClauseAttribution:
    clause: ClaimClause
    evidence_codes: tuple[str, ...]
    score: float
    reason: str


@dataclass(frozen=True, slots=True)
class ClaimAttributionDiagnostic:
    claim_code: str
    mode: AttributionMode
    status: AttributionStatus
    clauses: tuple[ClauseAttribution, ...]
    evidence_codes: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class ValidationReport:
    is_valid: bool
    errors: tuple[str, ...]
    cited_evidence: int
    total_claims: int


class SufficiencyDecision(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True, slots=True)
class SufficiencyReport:
    decision: SufficiencyDecision
    reasons: tuple[str, ...]
    lexical_score: float
    vector_score: float
    retriever_agreement: int

    @property
    def is_sufficient(self) -> bool:
        return self.decision is SufficiencyDecision.SUFFICIENT


class SemanticSupportStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class ClaimSupport:
    claim_code: str
    status: SemanticSupportStatus
    evidence_codes: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class SemanticSupportReport:
    claims: tuple[ClaimSupport, ...]
    technical_error: str | None = None

    @property
    def is_valid(self) -> bool:
        return (
            bool(self.claims)
            and self.technical_error is None
            and all(
                item.status is SemanticSupportStatus.SUPPORTED for item in self.claims
            )
        )

    @property
    def errors(self) -> tuple[str, ...]:
        if self.technical_error:
            return (self.technical_error,)
        return tuple(
            f"Claim {item.claim_code}: {item.status.value} ({item.reason})"
            for item in self.claims
            if item.status is not SemanticSupportStatus.SUPPORTED
        )


@dataclass(frozen=True, slots=True)
class CitationReference:
    claim_code: str
    evidence_code: str
    citation_label: str
    source_url: str


@dataclass(frozen=True, slots=True)
class ConsultationResult:
    outcome: ConsultationOutcome
    evidence_set_id: UUID
    answer: str
    claims: tuple[GeneratedClaim, ...]
    citations: tuple[CitationReference, ...]
    validation_errors: tuple[str, ...] = ()
    validation_stage: str | None = None
    sufficiency: SufficiencyReport | None = None
    semantic_support: SemanticSupportReport | None = None
    attribution_diagnostics: tuple[ClaimAttributionDiagnostic, ...] = ()
