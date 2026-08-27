"""Ports pequenos para as capacidades coordenadas pelo workflow."""

from typing import Protocol

from consultor_juridico.domain import (
    AnswerDecision,
    AnswerDraft,
    CitationValidation,
    EvidenceCandidate,
    Question,
    RelevanceDecision,
    SelectedEvidence,
)


class CandidateRetriever(Protocol):
    def retrieve(
        self, question: Question, limit: int
    ) -> tuple[EvidenceCandidate, ...]: ...


class EvidenceRelevanceJudge(Protocol):
    def judge(
        self, question: Question, candidates: tuple[EvidenceCandidate, ...]
    ) -> RelevanceDecision: ...


class AnswerGenerator(Protocol):
    def generate(
        self,
        question: Question,
        evidence: tuple[SelectedEvidence, ...],
        feedback: str | None = None,
    ) -> AnswerDraft: ...


class AnswerJudge(Protocol):
    def judge(
        self,
        question: Question,
        answer: AnswerDraft,
        evidence: tuple[SelectedEvidence, ...],
    ) -> AnswerDecision: ...


class CitationValidator(Protocol):
    def validate(
        self, answer: AnswerDraft, evidence: tuple[SelectedEvidence, ...]
    ) -> CitationValidation: ...
