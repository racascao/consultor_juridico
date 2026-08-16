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


@dataclass(frozen=True, slots=True)
class ValidationReport:
    is_valid: bool
    errors: tuple[str, ...]
    cited_evidence: int
    total_claims: int


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
