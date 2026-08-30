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
    consult,
    finish,
    retrieve_candidates,
    validate_citations,
)
from consultor_juridico.application.workflow.routing import (
    route_citation_validation,
    route_consultation,
)
from consultor_juridico.application.workflow.state import ConsultationState


def build_consultation_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Compila o grafo com persistência injetável pelo composition root."""

    graph = StateGraph(ConsultationState, context_schema=WorkflowContext)
    graph.add_node("retrieve_candidates", retrieve_candidates)
    graph.add_node("consult", consult)
    graph.add_node("clarify_user", clarify_user)
    graph.add_node("validate_citations", validate_citations)
    graph.add_node("abstain", abstain)
    graph.add_node("finish", finish)

    graph.add_edge(START, "retrieve_candidates")
    graph.add_edge("retrieve_candidates", "consult")
    graph.add_conditional_edges(
        "consult",
        _with_limits(route_consultation),
        {
            "validate_citations": "validate_citations",
            "clarify_user": "clarify_user",
            "abstain": "abstain",
        },
    )
    graph.add_edge("clarify_user", "retrieve_candidates")
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
