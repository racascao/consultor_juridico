"""Decisões tipadas produzidas pela única inferência de consulta."""

from dataclasses import dataclass
from enum import StrEnum

from consultor_juridico.domain.consultation import (
    ClarificationRequest,
    Interpretation,
)


class ConsultationDecisionKind(StrEnum):
    ANSWER = "ANSWER"
    CLARIFY = "CLARIFY"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True, slots=True)
class AnswerOutcome:
    answer: str
    evidence_ids: tuple[str, ...]
    kind: ConsultationDecisionKind = ConsultationDecisionKind.ANSWER

    def __post_init__(self) -> None:
        if self.kind is not ConsultationDecisionKind.ANSWER:
            raise ValueError("Tipo incompatível com ANSWER.")
        if not self.answer.strip():
            raise ValueError("ANSWER exige resposta não vazia.")
        if not self.evidence_ids:
            raise ValueError("ANSWER exige ao menos uma evidência.")


@dataclass(frozen=True, slots=True)
class ClarificationOutcome:
    request: ClarificationRequest
    interpretations: tuple[Interpretation, ...]
    kind: ConsultationDecisionKind = ConsultationDecisionKind.CLARIFY

    def __post_init__(self) -> None:
        if self.kind is not ConsultationDecisionKind.CLARIFY:
            raise ValueError("Tipo incompatível com CLARIFY.")
        if len(self.interpretations) < 2:
            raise ValueError("CLARIFY exige ao menos duas interpretações.")


@dataclass(frozen=True, slots=True)
class AbstainOutcome:
    kind: ConsultationDecisionKind = ConsultationDecisionKind.ABSTAIN

    def __post_init__(self) -> None:
        if self.kind is not ConsultationDecisionKind.ABSTAIN:
            raise ValueError("Tipo incompatível com ABSTAIN.")


type ConsultationModelOutcome = AnswerOutcome | ClarificationOutcome | AbstainOutcome


@dataclass(frozen=True, slots=True)
class CitationValidation:
    valid: bool
    reason: str
