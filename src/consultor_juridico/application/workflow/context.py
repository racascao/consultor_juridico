"""Dependências e limites injetados sem integrarem o estado persistido."""

from dataclasses import dataclass, field

from consultor_juridico.application.ports import (
    CandidateRetriever,
    CitationValidator,
    ConsultationResponder,
)
from consultor_juridico.application.workflow.diagnostics import WorkflowDiagnostics


@dataclass(frozen=True, slots=True)
class WorkflowLimits:
    max_clarification_turns: int = 2

    def __post_init__(self) -> None:
        if self.max_clarification_turns < 1:
            raise ValueError("O limite de clarificações deve ser positivo.")


@dataclass(frozen=True, slots=True)
class WorkflowContext:
    retriever: CandidateRetriever
    consultation_responder: ConsultationResponder
    citation_validator: CitationValidator
    limits: WorkflowLimits = WorkflowLimits()
    candidate_limit: int = 10
    diagnostics: WorkflowDiagnostics = field(default_factory=WorkflowDiagnostics)

    def __post_init__(self) -> None:
        if self.candidate_limit < 1:
            raise ValueError("O limite de candidatas deve ser positivo.")
