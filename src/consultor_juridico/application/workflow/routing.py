"""Roteamento mínimo por resultado tipado da consulta."""

from consultor_juridico.application.workflow.context import WorkflowLimits
from consultor_juridico.application.workflow.state import ConsultationState
from consultor_juridico.domain import ConsultationDecisionKind
from consultor_juridico.domain.errors import InvalidWorkflowState

CONSULTATION_ROUTES = {
    ConsultationDecisionKind.ANSWER: "validate_citations",
    ConsultationDecisionKind.CLARIFY: "clarify_user",
    ConsultationDecisionKind.ABSTAIN: "abstain",
}


def route_consultation(state: ConsultationState, limits: WorkflowLimits) -> str:
    outcome = state.get("consultation_outcome")
    if outcome is None:
        raise InvalidWorkflowState("Resultado da consulta ausente.")
    if (
        outcome.kind is ConsultationDecisionKind.CLARIFY
        and state["clarification_attempts"] >= limits.max_clarification_turns
    ):
        return "abstain"
    return CONSULTATION_ROUTES[outcome.kind]


def route_citation_validation(state: ConsultationState) -> str:
    return "finish" if "final_result" in state else "abstain"
