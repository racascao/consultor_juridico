"""Estado precisamente tipado e serializável pelo LangGraph."""

from typing import NotRequired, TypedDict

from consultor_juridico.domain import (
    AnswerDecision,
    AnswerDraft,
    ClarificationTurn,
    ConsultationResult,
    EvidenceCandidate,
    Question,
    RelevanceDecision,
    SelectedEvidence,
)


class ConsultationState(TypedDict):
    original_question: Question
    resolved_question: Question
    clarifications: tuple[ClarificationTurn, ...]
    candidates: tuple[EvidenceCandidate, ...]
    selected_evidence: tuple[SelectedEvidence, ...]
    relevance_decision: NotRequired[RelevanceDecision]
    draft_answer: NotRequired[AnswerDraft]
    answer_decision: NotRequired[AnswerDecision]
    retrieval_attempts: int
    generation_attempts: int
    clarification_attempts: int
    final_result: NotRequired[ConsultationResult]


class ConsultationStateUpdate(TypedDict, total=False):
    resolved_question: Question
    clarifications: tuple[ClarificationTurn, ...]
    candidates: tuple[EvidenceCandidate, ...]
    selected_evidence: tuple[SelectedEvidence, ...]
    relevance_decision: RelevanceDecision
    draft_answer: AnswerDraft
    answer_decision: AnswerDecision
    retrieval_attempts: int
    generation_attempts: int
    clarification_attempts: int
    final_result: ConsultationResult


def initial_state(question: Question) -> ConsultationState:
    return ConsultationState(
        original_question=question,
        resolved_question=question,
        clarifications=(),
        candidates=(),
        selected_evidence=(),
        retrieval_attempts=0,
        generation_attempts=0,
        clarification_attempts=0,
    )
