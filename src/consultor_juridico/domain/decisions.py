"""Decisões explícitas que controlam as transições do workflow."""

from dataclasses import dataclass
from enum import StrEnum

from consultor_juridico.domain.consultation import (
    ClarificationRequest,
    Interpretation,
)


class RelevanceDecisionKind(StrEnum):
    CLEAR = "CLEAR"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class RelevanceDecision:
    kind: RelevanceDecisionKind
    reason: str
    selected_candidate_ids: tuple[str, ...] = ()
    interpretations: tuple[Interpretation, ...] = ()
    clarification: ClarificationRequest | None = None

    def __post_init__(self) -> None:
        match self.kind:
            case RelevanceDecisionKind.CLEAR:
                self._validate_clear()
            case RelevanceDecisionKind.AMBIGUOUS:
                self._validate_ambiguous()
            case RelevanceDecisionKind.UNSUPPORTED:
                self._validate_unsupported()

    def _validate_clear(self) -> None:
        if not self.selected_candidate_ids:
            raise ValueError("Decisão CLEAR exige candidatas selecionadas.")
        if self.interpretations or self.clarification is not None:
            raise ValueError("Decisão CLEAR não admite dados de ambiguidade.")

    def _validate_ambiguous(self) -> None:
        if len(self.interpretations) < 2 or self.clarification is None:
            raise ValueError("Decisão AMBIGUOUS exige interpretações e clarificação.")
        if self.selected_candidate_ids:
            raise ValueError("Decisão AMBIGUOUS não seleciona evidência final.")

    def _validate_unsupported(self) -> None:
        if (
            self.selected_candidate_ids
            or self.interpretations
            or self.clarification is not None
        ):
            raise ValueError("Decisão UNSUPPORTED não admite evidência selecionada.")


class AnswerDecisionKind(StrEnum):
    ACCEPT = "ACCEPT"
    REWRITE = "REWRITE"
    RETRIEVE_AGAIN = "RETRIEVE_AGAIN"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True, slots=True)
class AnswerDecision:
    kind: AnswerDecisionKind
    reason: str


@dataclass(frozen=True, slots=True)
class CitationValidation:
    valid: bool
    reason: str
