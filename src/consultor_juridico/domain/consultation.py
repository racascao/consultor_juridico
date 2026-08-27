"""Objetos imutáveis que atravessam o workflow de consulta."""

from dataclasses import dataclass
from enum import StrEnum

from consultor_juridico.domain.evidence import SelectedEvidence


@dataclass(frozen=True, slots=True)
class Question:
    text: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("A pergunta não pode ser vazia.")


@dataclass(frozen=True, slots=True)
class Interpretation:
    label: str
    candidate_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClarificationRequest:
    question: str
    options: tuple[str, ...] = ()

    def as_payload(self) -> dict[str, str | list[str]]:
        return {
            "type": "clarification",
            "question": self.question,
            "options": list(self.options),
        }


@dataclass(frozen=True, slots=True)
class ClarificationTurn:
    request: ClarificationRequest
    answer: str


@dataclass(frozen=True, slots=True)
class Citation:
    candidate_id: str
    citation_label: str
    source_locator: str


@dataclass(frozen=True, slots=True)
class AnswerDraft:
    text: str
    citations: tuple[Citation, ...]


class ConsultationOutcome(StrEnum):
    ANSWERED = "ANSWERED"
    ABSTAINED = "ABSTAINED"


@dataclass(frozen=True, slots=True)
class ConsultationResult:
    outcome: ConsultationOutcome
    answer: str
    evidence: tuple[SelectedEvidence, ...]
    citations: tuple[Citation, ...]
    reason: str | None = None
