"""Workflow CPU-first: uma chamada de chat por pergunta direta."""

from dataclasses import dataclass, field

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from consultor_juridico.application.workflow import (
    ProviderCall,
    WorkflowContext,
    WorkflowLimits,
    build_consultation_graph,
    initial_state,
)
from consultor_juridico.domain import (
    AbstainOutcome,
    AnswerOutcome,
    CitationValidation,
    ClarificationOutcome,
    ClarificationRequest,
    ConsultationOutcome,
    EvidenceCandidate,
    Interpretation,
    Question,
)

CANDIDATE = EvidenceCandidate(
    "E1",
    "Art. 143. O serviço militar é obrigatório nos termos da lei.",
    "CF88/ARTICLE:143",
    "block:143",
    stable_reference="CF88/ARTICLE:143",
    source_url="https://www.planalto.gov.br",
    source_snapshot_sha="a" * 64,
)


@dataclass
class FakeRetriever:
    calls: list[str] = field(default_factory=list)

    def retrieve(self, question: Question, limit: int):
        self.calls.append(question.text)
        return (CANDIDATE,)


@dataclass
class SequenceResponder:
    outcomes: list
    calls: int = 0

    def respond(self, question, candidates):
        self.calls += 1
        return self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]


@dataclass
class FakeCitationValidator:
    calls: int = 0
    valid: bool = True

    def validate(self, answer, evidence):
        self.calls += 1
        return CitationValidation(self.valid, "Resultado determinístico.")


def answer() -> AnswerOutcome:
    return AnswerOutcome(
        "A Constituição estabelece que o serviço militar é obrigatório "
        "nos termos da lei.",
        ("E1",),
    )


def clarify() -> ClarificationOutcome:
    interpretations = (
        Interpretation("interpretação A", ("E1",)),
        Interpretation("interpretação B", ("E1",)),
    )
    return ClarificationOutcome(
        ClarificationRequest(
            "Qual interpretação você deseja?",
            tuple(item.label for item in interpretations),
        ),
        interpretations,
    )


def context(outcomes, *, valid=True, limits=None):
    retriever = FakeRetriever()
    responder = SequenceResponder(list(outcomes))
    validator = FakeCitationValidator(valid=valid)
    workflow_context = WorkflowContext(
        retriever,
        responder,
        validator,
        limits or WorkflowLimits(),
    )
    return workflow_context, retriever, responder, validator


def invoke(workflow_context, question="Alistamento militar é obrigatório?"):
    graph = build_consultation_graph()
    return graph.invoke(initial_state(Question(question)), context=workflow_context)


def test_direct_answer_uses_one_chat_call_and_validates_citation():
    workflow_context, retriever, responder, validator = context([answer()])
    workflow_context.diagnostics.add_provider_call(
        ProviderCall("chat", "consultation_model", 1, 10, "VALID")
    )

    result = invoke(workflow_context)

    assert result["final_result"].outcome is ConsultationOutcome.ANSWERED
    assert len(retriever.calls) == responder.calls == validator.calls == 1
    assert workflow_context.diagnostics.chat_calls == 1
    assert workflow_context.diagnostics.route == [
        "START",
        "RETRIEVE",
        "CONSULTATION:ANSWER",
        "CITATION:PASS",
        "END",
    ]


def test_direct_abstain_uses_one_chat_call_without_validator():
    workflow_context, _, responder, validator = context([AbstainOutcome()])
    workflow_context.diagnostics.add_provider_call(
        ProviderCall("chat", "consultation_model", 1, 10, "VALID")
    )

    result = invoke(workflow_context)

    assert result["final_result"].outcome is ConsultationOutcome.ABSTAINED
    assert responder.calls == workflow_context.diagnostics.chat_calls == 1
    assert validator.calls == 0


@pytest.mark.parametrize(
    ("error_kind", "expected_cause"),
    [
        ("INVALID_STRUCTURED_OUTPUT", "CONSULTATION_OUTPUT_INVALID"),
        ("PROVIDER_TIMEOUT", "PROVIDER_FAILURE"),
    ],
)
def test_consultation_failure_fails_closed_without_retry(error_kind, expected_cause):
    workflow_context, _, responder, validator = context([AbstainOutcome()])
    workflow_context.diagnostics.add_provider_call(
        ProviderCall("chat", "consultation_model", 1, 10, "INVALID", error_kind)
    )

    result = invoke(workflow_context)

    assert result["final_result"].outcome is ConsultationOutcome.ABSTAINED
    assert responder.calls == workflow_context.diagnostics.chat_calls == 1
    assert validator.calls == 0
    assert workflow_context.diagnostics.abstention_cause.value == expected_cause
    expected_route = (
        "CONSULTATION:PROVIDER_FAILURE"
        if error_kind == "PROVIDER_TIMEOUT"
        else "CONSULTATION:OUTPUT_INVALID"
    )
    assert expected_route in workflow_context.diagnostics.route


def test_citation_failure_fails_closed_without_second_chat_call():
    workflow_context, _, responder, validator = context([answer()], valid=False)
    workflow_context.diagnostics.add_provider_call(
        ProviderCall("chat", "consultation_model", 1, 10, "VALID")
    )

    result = invoke(workflow_context)

    assert result["final_result"].outcome is ConsultationOutcome.ABSTAINED
    assert responder.calls == validator.calls == 1
    assert workflow_context.diagnostics.chat_calls == 1
    assert workflow_context.diagnostics.abstention_cause.value == (
        "CITATION_VALIDATION_FAILED"
    )


def test_clarification_interrupt_resume_retrieves_again_and_calls_model_twice():
    workflow_context, retriever, responder, _ = context([clarify(), answer()])
    graph = build_consultation_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "clarification-resume"}}

    interrupted = graph.invoke(
        initial_state(Question("Qual interpretação se aplica?")),
        context=workflow_context,
        config=config,
    )
    assert interrupted["__interrupt__"][0].value["type"] == "clarification"

    resumed = graph.invoke(
        Command(resume="interpretação B"), context=workflow_context, config=config
    )

    assert resumed["final_result"].outcome is ConsultationOutcome.ANSWERED
    assert resumed["clarification_attempts"] == 1
    assert len(retriever.calls) == responder.calls == 2
    assert "interpretação B" in resumed["resolved_question"].text


def test_persistent_ambiguity_abstains_at_two_clarifications():
    workflow_context, _, responder, _ = context(
        [clarify()], limits=WorkflowLimits(max_clarification_turns=2)
    )
    graph = build_consultation_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "clarification-limit"}}

    graph.invoke(
        initial_state(Question("Pergunta ambígua?")),
        context=workflow_context,
        config=config,
    )
    graph.invoke(Command(resume="opção 1"), context=workflow_context, config=config)
    result = graph.invoke(
        Command(resume="opção 2"), context=workflow_context, config=config
    )

    assert result["final_result"].outcome is ConsultationOutcome.ABSTAINED
    assert result["clarification_attempts"] == 2
    assert responder.calls == 3


def test_domain_outcomes_reject_impossible_shapes():
    with pytest.raises(ValueError, match="resposta não vazia"):
        AnswerOutcome("", ("E1",))
    with pytest.raises(ValueError, match="ao menos uma evidência"):
        AnswerOutcome("Resposta", ())
    with pytest.raises(ValueError, match="duas interpretações"):
        ClarificationOutcome(
            ClarificationRequest("Qual sentido?", ("A",)),
            (Interpretation("A", ("E1",)),),
        )
