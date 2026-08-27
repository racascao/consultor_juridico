"""Montagem declarativa do StateGraph de consulta v0.2."""

from collections.abc import Callable

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from consultor_juridico.application.workflow.context import (
    WorkflowContext,
    WorkflowLimits,
)
from consultor_juridico.application.workflow.nodes import (
    abstain,
    clarify_user,
    finish,
    generate_answer,
    judge_answer,
    judge_evidence_relevance,
    retrieve_candidates,
    validate_citations,
)
from consultor_juridico.application.workflow.routing import (
    route_answer,
    route_citation_validation,
    route_relevance,
)
from consultor_juridico.application.workflow.state import ConsultationState


def build_consultation_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Compila o grafo com persistência injetável pelo composition root."""

    graph = StateGraph(ConsultationState, context_schema=WorkflowContext)
    graph.add_node("retrieve_candidates", retrieve_candidates)
    graph.add_node("judge_evidence_relevance", judge_evidence_relevance)
    graph.add_node("clarify_user", clarify_user)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("judge_answer", judge_answer)
    graph.add_node("validate_citations", validate_citations)
    graph.add_node("abstain", abstain)
    graph.add_node("finish", finish)

    graph.add_edge(START, "retrieve_candidates")
    graph.add_edge("retrieve_candidates", "judge_evidence_relevance")
    graph.add_conditional_edges(
        "judge_evidence_relevance",
        _with_limits(route_relevance),
        {
            "generate_answer": "generate_answer",
            "clarify_user": "clarify_user",
            "abstain": "abstain",
        },
    )
    graph.add_edge("clarify_user", "retrieve_candidates")
    graph.add_edge("generate_answer", "judge_answer")
    graph.add_conditional_edges(
        "judge_answer",
        _with_limits(route_answer),
        {
            "validate_citations": "validate_citations",
            "generate_answer": "generate_answer",
            "retrieve_candidates": "retrieve_candidates",
            "abstain": "abstain",
        },
    )
    graph.add_conditional_edges(
        "validate_citations",
        route_citation_validation,
        {"finish": "finish", "abstain": "abstain"},
    )
    graph.add_edge("finish", END)
    graph.add_edge("abstain", END)
    return graph.compile(checkpointer=checkpointer, name="consultation-v0.2")


def _with_limits(
    router: Callable[[ConsultationState, WorkflowLimits], str],
) -> Callable[[ConsultationState, Runtime[WorkflowContext]], str]:
    def route(state: ConsultationState, runtime: Runtime[WorkflowContext]) -> str:
        return router(state, runtime.context.limits)

    return route
