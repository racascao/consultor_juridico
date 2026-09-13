"""Contratos imutáveis do fluxo RAG do MVP2."""

from dataclasses import dataclass
from enum import StrEnum


class RagDecision(StrEnum):
    ANSWER = "ANSWER"
    ABSTAIN = "ABSTAIN"
    CLARIFY = "CLARIFY"


class QueryMode(StrEnum):
    """Intenção declarada pelo consumidor; nunca inferida do texto."""

    LEGAL_RULE = "legal-rule"
    CASE_APPLICATION = "case-application"


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


@dataclass(frozen=True, slots=True)
class RagQueryRequest:
    question: str
    version_hash: str
    mode: QueryMode
    limit: int = 10

    def __post_init__(self) -> None:
        if not isinstance(self.mode, QueryMode):
            raise ValueError("mode deve ser QueryMode explícito")
        if not self.question.strip():
            raise ValueError("A pergunta RAG não pode ser vazia")
        if len(self.version_hash) != 64 or any(
            char not in "0123456789abcdef" for char in self.version_hash
        ):
            raise ValueError("version_hash deve ser um SHA-256 hexadecimal minúsculo")
        if not 1 <= self.limit <= 100:
            raise ValueError("limit deve estar entre 1 e 100")
