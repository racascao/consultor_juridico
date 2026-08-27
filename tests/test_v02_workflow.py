"""Testes rápidos da fundação LangGraph sem banco, rede ou modelos."""

from dataclasses import dataclass, field

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from consultor_juridico.application.workflow import (
    WorkflowContext,
    WorkflowLimits,
    build_consultation_graph,
    initial_state,
)
from consultor_juridico.domain import (
    AnswerDecision,
    AnswerDecisionKind,
    AnswerDraft,
    Citation,
    CitationValidation,
    ClarificationRequest,
    ConsultationOutcome,
    EvidenceCandidate,
    Interpretation,
    Question,
    RelevanceDecision,
    RelevanceDecisionKind,
)

CANDIDATE = EvidenceCandidate("ev-1", "Texto oficial.", "CF, art. 1º", "p:1")


@dataclass
class FakeRetriever:
    calls: list[str] = field(default_factory=list)

    def retrieve(self, question: Question, limit: int) -> tuple[EvidenceCandidate, ...]:
        self.calls.append(question.text)
        return (CANDIDATE,)


@dataclass
class SequenceRelevanceJudge:
    decisions: list[RelevanceDecision]

    def judge(self, question, candidates):
        return self.decisions.pop(0) if len(self.decisions) > 1 else self.decisions[0]


@dataclass
class FakeGenerator:
    calls: int = 0
    feedback: list[str | None] = field(default_factory=list)

    def generate(self, question, evidence, feedback=None):
        self.calls += 1
        self.feedback.append(feedback)
        citation = Citation(
            evidence[0].candidate_id,
            evidence[0].citation_label,
            evidence[0].source_locator,
        )
        return AnswerDraft(f"Resposta {self.calls}.", (citation,))


@dataclass
class SequenceAnswerJudge:
    decisions: list[AnswerDecision]

    def judge(self, question, answer, evidence):
        return self.decisions.pop(0) if len(self.decisions) > 1 else self.decisions[0]


@dataclass
class FakeCitationValidator:
    calls: int = 0

    def validate(self, answer, evidence):
        self.calls += 1
        return CitationValidation(True, "Citações válidas.")


def clear_decision() -> RelevanceDecision:
    return RelevanceDecision(
        RelevanceDecisionKind.CLEAR,
        "Uma interpretação responde diretamente.",
        selected_candidate_ids=(CANDIDATE.candidate_id,),
    )


def ambiguous_decision() -> RelevanceDecision:
    interpretations = (
        Interpretation("interpretação A", (CANDIDATE.candidate_id,)),
        Interpretation("interpretação B", (CANDIDATE.candidate_id,)),
    )
    return RelevanceDecision(
        RelevanceDecisionKind.AMBIGUOUS,
        "Duas interpretações plausíveis.",
        interpretations=interpretations,
        clarification=ClarificationRequest(
            "Qual interpretação você deseja?",
            tuple(item.label for item in interpretations),
        ),
    )


def context(
    relevance: list[RelevanceDecision],
    answers: list[AnswerDecision],
    *,
    limits: WorkflowLimits | None = None,
):
    retriever = FakeRetriever()
    generator = FakeGenerator()
    validator = FakeCitationValidator()
    workflow_context = WorkflowContext(
        retriever,
        SequenceRelevanceJudge(relevance),
        generator,
        SequenceAnswerJudge(answers),
        validator,
        limits or WorkflowLimits(),
    )
    return workflow_context, retriever, generator, validator


def invoke(workflow_context, question="Qual é a regra aplicável?"):
    graph = build_consultation_graph()
    return graph.invoke(initial_state(Question(question)), context=workflow_context)


def test_happy_path_answers_with_validated_citation():
    workflow_context, retriever, generator, validator = context(
        [clear_decision()],
        [AnswerDecision(AnswerDecisionKind.ACCEPT, "Resposta adequada.")],
    )

    result = invoke(workflow_context)

    assert result["final_result"].outcome is ConsultationOutcome.ANSWERED
    assert result["retrieval_attempts"] == 1
    assert result["generation_attempts"] == 1
    assert len(retriever.calls) == generator.calls == validator.calls == 1


def test_rewrite_returns_to_generator_and_respects_attempt_counter():
    workflow_context, _, generator, _ = context(
        [clear_decision()],
        [
            AnswerDecision(AnswerDecisionKind.REWRITE, "Reformular diretamente."),
            AnswerDecision(AnswerDecisionKind.ACCEPT, "Resposta adequada."),
        ],
    )

    result = invoke(workflow_context)

    assert result["final_result"].outcome is ConsultationOutcome.ANSWERED
    assert result["generation_attempts"] == 2
    assert generator.feedback == [None, "Reformular diretamente."]


def test_retrieve_again_returns_to_retrieval_instead_of_generator():
    workflow_context, retriever, generator, _ = context(
        [clear_decision(), clear_decision()],
        [
            AnswerDecision(AnswerDecisionKind.RETRIEVE_AGAIN, "Evidência inadequada."),
            AnswerDecision(AnswerDecisionKind.ACCEPT, "Resposta adequada."),
        ],
    )

    result = invoke(workflow_context)

    assert result["final_result"].outcome is ConsultationOutcome.ANSWERED
    assert result["retrieval_attempts"] == 2
    assert len(retriever.calls) == 2
    assert generator.calls == 2


def test_unsupported_abstains_without_calling_generator():
    unsupported = RelevanceDecision(
        RelevanceDecisionKind.UNSUPPORTED, "Corpus insuficiente."
    )
    workflow_context, _, generator, validator = context(
        [unsupported],
        [AnswerDecision(AnswerDecisionKind.ACCEPT, "Não utilizada.")],
    )

    result = invoke(workflow_context)

    assert result["final_result"].outcome is ConsultationOutcome.ABSTAINED
    assert generator.calls == validator.calls == 0


def test_answer_judge_can_abstain_directly():
    workflow_context, _, generator, validator = context(
        [clear_decision()],
        [AnswerDecision(AnswerDecisionKind.ABSTAIN, "Resposta insegura.")],
    )

    result = invoke(workflow_context)

    assert result["final_result"].outcome is ConsultationOutcome.ABSTAINED
    assert generator.calls == 1
    assert validator.calls == 0


def test_ambiguity_interrupts_and_command_resume_retrieves_again():
    workflow_context, retriever, generator, _ = context(
        [ambiguous_decision(), clear_decision()],
        [AnswerDecision(AnswerDecisionKind.ACCEPT, "Resposta adequada.")],
    )
    graph = build_consultation_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "clarification-resume"}}

    interrupted = graph.invoke(
        initial_state(Question("Qual interpretação se aplica?")),
        context=workflow_context,
        config=config,
    )
    assert interrupted["__interrupt__"][0].value["type"] == "clarification"
    assert generator.calls == 0

    resumed = graph.invoke(
        Command(resume="interpretação B"), context=workflow_context, config=config
    )

    assert resumed["final_result"].outcome is ConsultationOutcome.ANSWERED
    assert resumed["original_question"].text == "Qual interpretação se aplica?"
    assert "interpretação B" in resumed["resolved_question"].text
    assert resumed["clarification_attempts"] == 1
    assert len(retriever.calls) == 2


def test_persistent_ambiguity_abstains_at_clarification_limit():
    workflow_context, _, generator, _ = context(
        [ambiguous_decision()],
        [AnswerDecision(AnswerDecisionKind.ACCEPT, "Não utilizada.")],
        limits=WorkflowLimits(max_clarification_turns=2),
    )
    graph = build_consultation_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "clarification-limit"}}

    graph.invoke(
        initial_state(Question("Pergunta ambígua?")),
        context=workflow_context,
        config=config,
    )
    graph.invoke(
        Command(resume="primeira opção"), context=workflow_context, config=config
    )
    result = graph.invoke(
        Command(resume="segunda opção"), context=workflow_context, config=config
    )

    assert result["final_result"].outcome is ConsultationOutcome.ABSTAINED
    assert result["clarification_attempts"] == 2
    assert generator.calls == 0


def test_rewrite_limit_abstains_without_infinite_loop():
    rewrite = AnswerDecision(AnswerDecisionKind.REWRITE, "Ainda inadequada.")
    workflow_context, _, generator, _ = context(
        [clear_decision()], [rewrite], limits=WorkflowLimits(max_generation_attempts=2)
    )

    result = invoke(workflow_context)

    assert result["final_result"].outcome is ConsultationOutcome.ABSTAINED
    assert result["generation_attempts"] == generator.calls == 2


def test_retrieval_limit_abstains_without_infinite_loop():
    retry = AnswerDecision(AnswerDecisionKind.RETRIEVE_AGAIN, "Buscar novamente.")
    workflow_context, retriever, _, _ = context(
        [clear_decision()], [retry], limits=WorkflowLimits(max_retrieval_attempts=2)
    )

    result = invoke(workflow_context)

    assert result["final_result"].outcome is ConsultationOutcome.ABSTAINED
    assert result["retrieval_attempts"] == len(retriever.calls) == 2
