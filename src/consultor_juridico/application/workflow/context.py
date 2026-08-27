"""Dependências e limites injetados sem integrarem o estado persistido."""

from dataclasses import dataclass

from consultor_juridico.application.ports import (
    AnswerGenerator,
    AnswerJudge,
    CandidateRetriever,
    CitationValidator,
    EvidenceRelevanceJudge,
)


@dataclass(frozen=True, slots=True)
class WorkflowLimits:
    max_retrieval_attempts: int = 2
    max_generation_attempts: int = 2
    max_clarification_turns: int = 2

    def __post_init__(self) -> None:
        if (
            min(
                self.max_retrieval_attempts,
                self.max_generation_attempts,
                self.max_clarification_turns,
            )
            < 1
        ):
            raise ValueError("Todos os limites do workflow devem ser positivos.")


@dataclass(frozen=True, slots=True)
class WorkflowContext:
    retriever: CandidateRetriever
    relevance_judge: EvidenceRelevanceJudge
    answer_generator: AnswerGenerator
    answer_judge: AnswerJudge
    citation_validator: CitationValidator
    limits: WorkflowLimits = WorkflowLimits()
    candidate_limit: int = 10

    def __post_init__(self) -> None:
        if self.candidate_limit < 1:
            raise ValueError("O limite de candidatas deve ser positivo.")
