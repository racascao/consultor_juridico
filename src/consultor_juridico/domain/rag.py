"""Contratos imutáveis do fluxo RAG do MVP2."""

from dataclasses import dataclass
from enum import StrEnum


class RagDecision(StrEnum):
    ANSWER = "ANSWER"
    ABSTAIN = "ABSTAIN"
    CLARIFY = "CLARIFY"


class CitationStatus(StrEnum):
    VALID = "VALID"
    INVALID_CITATION = "INVALID_CITATION"
    OUT_OF_EVIDENCE = "OUT_OF_EVIDENCE"


@dataclass(frozen=True, slots=True)
class AnswerContract:
    decision: RagDecision
    answer: str
    citations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CitationValidation:
    status: CitationStatus
    invalid_citations: tuple[str, ...] = ()
    out_of_evidence: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return self.status is CitationStatus.VALID


@dataclass(frozen=True, slots=True)
class RagIdentity:
    model: str
    model_digest: str
    freeze_id: str
    prompt_identity: str
    generation_config: tuple[tuple[str, float | int | bool], ...]
