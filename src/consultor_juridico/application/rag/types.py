"""Resultado auditável da aplicação RAG."""

from dataclasses import dataclass

from consultor_juridico.application.gold_evidence.types import GoldEvidenceItem
from consultor_juridico.domain.rag import (
    AnswerContract,
    CitationValidation,
    QueryMode,
    RagIdentity,
)
from consultor_juridico.domain.retrieval import RetrievalCandidate


@dataclass(frozen=True, slots=True)
class RagResult:
    question: str
    retrieved: tuple[RetrievalCandidate, ...]
    evidence: tuple[GoldEvidenceItem, ...]
    output: AnswerContract
    citation_validation: CitationValidation
    identity: RagIdentity | None
    query_mode: QueryMode
    retrieval_executed: bool
    answerer_executed: bool
    routing_reason: str | None = None
