"""Roteamento central por decisões tipadas e limites explícitos."""

from consultor_juridico.application.workflow.context import WorkflowLimits
from consultor_juridico.application.workflow.state import ConsultationState
from consultor_juridico.domain import AnswerDecisionKind, RelevanceDecisionKind
from consultor_juridico.domain.errors import InvalidWorkflowState

RELEVANCE_ROUTES = {
    RelevanceDecisionKind.CLEAR: "generate_answer",
    RelevanceDecisionKind.AMBIGUOUS: "clarify_user",
    RelevanceDecisionKind.UNSUPPORTED: "abstain",
}

ANSWER_ROUTES = {
    AnswerDecisionKind.ACCEPT: "validate_citations",
    AnswerDecisionKind.REWRITE: "generate_answer",
    AnswerDecisionKind.RETRIEVE_AGAIN: "retrieve_candidates",
    AnswerDecisionKind.ABSTAIN: "abstain",
}


def route_relevance(state: ConsultationState, limits: WorkflowLimits) -> str:
    decision = state.get("relevance_decision")
    if decision is None:
        raise InvalidWorkflowState("Decisão de relevância ausente.")
    if (
        decision.kind is RelevanceDecisionKind.AMBIGUOUS
        and state["clarification_attempts"] >= limits.max_clarification_turns
    ):
        return "abstain"
    return RELEVANCE_ROUTES[decision.kind]


def route_answer(state: ConsultationState, limits: WorkflowLimits) -> str:
    decision = state.get("answer_decision")
    if decision is None:
        raise InvalidWorkflowState("Decisão sobre a resposta ausente.")
    if (
        decision.kind is AnswerDecisionKind.REWRITE
        and state["generation_attempts"] >= limits.max_generation_attempts
    ):
        return "abstain"
    if (
        decision.kind is AnswerDecisionKind.RETRIEVE_AGAIN
        and state["retrieval_attempts"] >= limits.max_retrieval_attempts
    ):
        return "abstain"
    return ANSWER_ROUTES[decision.kind]


def route_citation_validation(state: ConsultationState) -> str:
    return "finish" if "final_result" in state else "abstain"
