"""Nós do workflow CPU-first com uma inferência de consulta por pergunta."""

from langgraph.runtime import Runtime
from langgraph.types import interrupt

from consultor_juridico.application.workflow.context import WorkflowContext
from consultor_juridico.application.workflow.diagnostics import AbstentionCause
from consultor_juridico.application.workflow.state import (
    ConsultationState,
    ConsultationStateUpdate,
)
from consultor_juridico.domain import (
    AnswerDraft,
    AnswerOutcome,
    Citation,
    ClarificationOutcome,
    ClarificationTurn,
    ConsultationOutcome,
    ConsultationResult,
    Question,
    SelectedEvidence,
)
from consultor_juridico.domain.errors import InvalidWorkflowState

ABSTENTION_MESSAGE = "Não há evidência oficial suficiente para responder com segurança."


def retrieve_candidates(
    state: ConsultationState, runtime: Runtime[WorkflowContext]
) -> ConsultationStateUpdate:
    diagnostics = runtime.context.diagnostics
    attempt = diagnostics.node_execution_counts.get("candidate_retrieval", 0) + 1
    diagnostics.add_route("RETRIEVE")
    with diagnostics.node("candidate_retrieval", attempt):
        candidates = runtime.context.retriever.retrieve(
            state["resolved_question"], runtime.context.candidate_limit
        )
    diagnostics.add_detail(
        "candidate_retrieval",
        attempt=attempt,
        candidate_count=len(candidates),
        candidates=tuple(
            (item.candidate_id, item.stable_reference) for item in candidates
        ),
    )
    return {"candidates": candidates, "selected_evidence": ()}


def consult(
    state: ConsultationState, runtime: Runtime[WorkflowContext]
) -> ConsultationStateUpdate:
    diagnostics = runtime.context.diagnostics
    attempt = diagnostics.node_execution_counts.get("consultation_model", 0) + 1
    with diagnostics.node("consultation_model", attempt):
        outcome = runtime.context.consultation_responder.respond(
            state["resolved_question"], state["candidates"]
        )
    call = diagnostics.last_provider_call("consultation_model")
    if call and call.error_kind:
        diagnostics.abstention_cause = (
            AbstentionCause.PROVIDER_FAILURE
            if call.error_kind in {"PROVIDER_TIMEOUT", "PROVIDER_ERROR"}
            else AbstentionCause.CONSULTATION_OUTPUT_INVALID
        )
    route_decision = outcome.kind.value
    if call and call.error_kind in {"PROVIDER_TIMEOUT", "PROVIDER_ERROR"}:
        route_decision = "PROVIDER_FAILURE"
    elif call and call.error_kind == "INVALID_STRUCTURED_OUTPUT":
        route_decision = "OUTPUT_INVALID"
    diagnostics.add_route(f"CONSULTATION:{route_decision}")
    selected = ()
    draft = None
    if isinstance(outcome, AnswerOutcome):
        selected = _select_evidence(state, outcome.evidence_ids)
        draft = AnswerDraft(
            outcome.answer,
            tuple(
                Citation(item.candidate_id, item.citation_label, item.source_locator)
                for item in selected
            ),
        )
    diagnostics.add_detail(
        "consultation_model",
        attempt=attempt,
        question=state["resolved_question"].text,
        candidate_count=len(state["candidates"]),
        selected_evidence_ids=tuple(item.candidate_id for item in selected),
        decision=outcome.kind.value,
        request_chars=call.request_chars if call else None,
        output_validation=call.output_validation if call else "NOT_RECORDED",
    )
    update: ConsultationStateUpdate = {
        "consultation_outcome": outcome,
        "selected_evidence": selected,
    }
    if draft is not None:
        update["draft_answer"] = draft
    return update


def clarify_user(
    state: ConsultationState, runtime: Runtime[WorkflowContext]
) -> ConsultationStateUpdate:
    outcome = state.get("consultation_outcome")
    if not isinstance(outcome, ClarificationOutcome):
        raise InvalidWorkflowState("Pedido de clarificação ausente.")
    diagnostics = runtime.context.diagnostics
    diagnostics.add_route("CLARIFY")
    with diagnostics.node("clarification", state["clarification_attempts"] + 1):
        resumed = interrupt(outcome.request.as_payload())
    answer = _clarification_answer(resumed)
    clarifications = (
        *state["clarifications"],
        ClarificationTurn(outcome.request, answer),
    )
    return {
        "clarifications": clarifications,
        "resolved_question": _resolve_question(
            state["original_question"], clarifications
        ),
        "clarification_attempts": state["clarification_attempts"] + 1,
    }


def validate_citations(
    state: ConsultationState, runtime: Runtime[WorkflowContext]
) -> ConsultationStateUpdate:
    draft = state.get("draft_answer")
    if draft is None:
        raise InvalidWorkflowState("Resposta fundamentada ausente.")
    diagnostics = runtime.context.diagnostics
    attempt = diagnostics.node_execution_counts.get("citation_validation", 0) + 1
    with diagnostics.node("citation_validation", attempt):
        validation = runtime.context.citation_validator.validate(
            draft, state["selected_evidence"]
        )
    diagnostics.add_route("CITATION:PASS" if validation.valid else "CITATION:FAIL")
    diagnostics.add_detail(
        "citation_validation",
        attempt=attempt,
        valid=validation.valid,
        reason=validation.reason,
    )
    if not validation.valid:
        diagnostics.abstention_cause = AbstentionCause.CITATION_VALIDATION_FAILED
        return {}
    return {
        "final_result": ConsultationResult(
            outcome=ConsultationOutcome.ANSWERED,
            answer=draft.text,
            evidence=state["selected_evidence"],
            citations=draft.citations,
        )
    }


def abstain(
    state: ConsultationState, runtime: Runtime[WorkflowContext]
) -> ConsultationStateUpdate:
    diagnostics = runtime.context.diagnostics
    if diagnostics.abstention_cause is None:
        diagnostics.abstention_cause = (
            AbstentionCause.WORKFLOW_LIMIT_REACHED
            if isinstance(state.get("consultation_outcome"), ClarificationOutcome)
            else AbstentionCause.NO_RELEVANT_EVIDENCE
        )
    diagnostics.add_route("ABSTAIN")
    diagnostics.add_route("END")
    diagnostics.add_detail("abstain", cause=diagnostics.abstention_cause.value)
    return {
        "final_result": ConsultationResult(
            outcome=ConsultationOutcome.ABSTAINED,
            answer=ABSTENTION_MESSAGE,
            evidence=(),
            citations=(),
            reason=diagnostics.abstention_cause.value,
        )
    }


def finish(
    state: ConsultationState, runtime: Runtime[WorkflowContext]
) -> ConsultationStateUpdate:
    del state
    runtime.context.diagnostics.add_route("END")
    return {}


def _select_evidence(
    state: ConsultationState, selected_ids: tuple[str, ...]
) -> tuple[SelectedEvidence, ...]:
    candidates = {item.candidate_id: item for item in state["candidates"]}
    missing = tuple(item_id for item_id in selected_ids if item_id not in candidates)
    if missing:
        raise InvalidWorkflowState(
            f"Consulta selecionou candidatas inexistentes: {', '.join(missing)}"
        )
    return tuple(
        SelectedEvidence.from_candidate(candidates[item_id]) for item_id in selected_ids
    )


def _clarification_answer(resumed: object) -> str:
    if isinstance(resumed, str) and resumed.strip():
        return resumed.strip()
    if isinstance(resumed, dict):
        answer = resumed.get("answer")
        if isinstance(answer, str) and answer.strip():
            return answer.strip()
    raise InvalidWorkflowState("Resposta de clarificação vazia ou inválida.")


def _resolve_question(
    original: Question, clarifications: tuple[ClarificationTurn, ...]
) -> Question:
    details = "\n".join(
        f"Esclarecimento {index}: {turn.answer}"
        for index, turn in enumerate(clarifications, start=1)
    )
    return Question(f"{original.text}\n{details}")
