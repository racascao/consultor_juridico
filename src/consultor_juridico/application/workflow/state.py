"""Estado precisamente tipado e serializável pelo LangGraph."""

from typing import NotRequired, TypedDict

from consultor_juridico.domain import (
    AnswerDraft,
    ClarificationTurn,
    ConsultationModelOutcome,
    ConsultationResult,
    EvidenceCandidate,
    Question,
    SelectedEvidence,
)


class ConsultationState(TypedDict):
    original_question: Question
    resolved_question: Question
    clarifications: tuple[ClarificationTurn, ...]
    candidates: tuple[EvidenceCandidate, ...]
    selected_evidence: tuple[SelectedEvidence, ...]
    consultation_outcome: NotRequired[ConsultationModelOutcome]
    draft_answer: NotRequired[AnswerDraft]
    clarification_attempts: int
    final_result: NotRequired[ConsultationResult]


class ConsultationStateUpdate(TypedDict, total=False):
    resolved_question: Question
    clarifications: tuple[ClarificationTurn, ...]
    candidates: tuple[EvidenceCandidate, ...]
    selected_evidence: tuple[SelectedEvidence, ...]
    consultation_outcome: ConsultationModelOutcome
    draft_answer: AnswerDraft
    clarification_attempts: int
    final_result: ConsultationResult


def initial_state(question: Question) -> ConsultationState:
    return ConsultationState(
        original_question=question,
        resolved_question=question,
        clarifications=(),
        candidates=(),
        selected_evidence=(),
        clarification_attempts=0,
    )
