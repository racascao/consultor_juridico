"""Ports pequenos para as capacidades coordenadas pelo workflow."""

from typing import Protocol

from consultor_juridico.domain import (
    AnswerDraft,
    CitationValidation,
    ConsultationModelOutcome,
    EvidenceCandidate,
    Question,
    SelectedEvidence,
)


class CandidateRetriever(Protocol):
    def retrieve(
        self, question: Question, limit: int
    ) -> tuple[EvidenceCandidate, ...]: ...


class ConsultationResponder(Protocol):
    def respond(
        self, question: Question, candidates: tuple[EvidenceCandidate, ...]
    ) -> ConsultationModelOutcome: ...


class CitationValidator(Protocol):
    def validate(
        self, answer: AnswerDraft, evidence: tuple[SelectedEvidence, ...]
    ) -> CitationValidation: ...
