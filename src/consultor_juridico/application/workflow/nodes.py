"""Nós coesos do workflow; decisões e I/O são delegados aos ports."""

from langgraph.runtime import Runtime
from langgraph.types import interrupt

from consultor_juridico.application.workflow.context import WorkflowContext
from consultor_juridico.application.workflow.state import (
    ConsultationState,
    ConsultationStateUpdate,
)
from consultor_juridico.domain import (
    AnswerDecisionKind,
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
    candidates = runtime.context.retriever.retrieve(
        state["resolved_question"], runtime.context.candidate_limit
    )
    return {
        "candidates": candidates,
        "selected_evidence": (),
        "retrieval_attempts": state["retrieval_attempts"] + 1,
    }


def judge_evidence_relevance(
    state: ConsultationState, runtime: Runtime[WorkflowContext]
) -> ConsultationStateUpdate:
    decision = runtime.context.relevance_judge.judge(
        state["resolved_question"], state["candidates"]
    )
    selected = _select_evidence(state, decision.selected_candidate_ids)
    return {"relevance_decision": decision, "selected_evidence": selected}


def clarify_user(
    state: ConsultationState, runtime: Runtime[WorkflowContext]
) -> ConsultationStateUpdate:
    del runtime
    decision = state.get("relevance_decision")
    if decision is None or decision.clarification is None:
        raise InvalidWorkflowState("Pedido de clarificação ausente.")

    resumed = interrupt(decision.clarification.as_payload())
    answer = _clarification_answer(resumed)
    turn = ClarificationTurn(decision.clarification, answer)
    clarifications = (*state["clarifications"], turn)
    resolved = _resolve_question(state["original_question"], clarifications)
    return {
        "clarifications": clarifications,
        "resolved_question": resolved,
        "clarification_attempts": state["clarification_attempts"] + 1,
    }


def generate_answer(
    state: ConsultationState, runtime: Runtime[WorkflowContext]
) -> ConsultationStateUpdate:
    previous = state.get("answer_decision")
    feedback = (
        previous.reason
        if previous is not None and previous.kind is AnswerDecisionKind.REWRITE
        else None
    )
    draft = runtime.context.answer_generator.generate(
        state["resolved_question"], state["selected_evidence"], feedback
    )
    return {
        "draft_answer": draft,
        "generation_attempts": state["generation_attempts"] + 1,
    }


def judge_answer(
    state: ConsultationState, runtime: Runtime[WorkflowContext]
) -> ConsultationStateUpdate:
    draft = state.get("draft_answer")
    if draft is None:
        raise InvalidWorkflowState("Rascunho de resposta ausente.")
    decision = runtime.context.answer_judge.judge(
        state["resolved_question"], draft, state["selected_evidence"]
    )
    return {"answer_decision": decision}


def validate_citations(
    state: ConsultationState, runtime: Runtime[WorkflowContext]
) -> ConsultationStateUpdate:
    draft = state.get("draft_answer")
    if draft is None:
        raise InvalidWorkflowState("Rascunho de resposta ausente.")
    validation = runtime.context.citation_validator.validate(
        draft, state["selected_evidence"]
    )
    if not validation.valid:
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
    del runtime
    answer_decision = state.get("answer_decision")
    relevance_decision = state.get("relevance_decision")
    reason = (
        answer_decision.reason
        if answer_decision is not None
        else relevance_decision.reason
        if relevance_decision is not None
        else "Limite seguro do workflow atingido."
    )
    return {
        "final_result": ConsultationResult(
            outcome=ConsultationOutcome.ABSTAINED,
            answer=ABSTENTION_MESSAGE,
            evidence=state["selected_evidence"],
            citations=(),
            reason=reason,
        )
    }


def finish(
    state: ConsultationState, runtime: Runtime[WorkflowContext]
) -> ConsultationStateUpdate:
    del state, runtime
    return {}


def _select_evidence(
    state: ConsultationState, selected_ids: tuple[str, ...]
) -> tuple[SelectedEvidence, ...]:
    candidates = {item.candidate_id: item for item in state["candidates"]}
    missing = tuple(item_id for item_id in selected_ids if item_id not in candidates)
    if missing:
        raise InvalidWorkflowState(
            f"Decisão selecionou candidatas inexistentes: {', '.join(missing)}"
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
