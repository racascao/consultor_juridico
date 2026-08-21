"""Tipos imutáveis do benchmark do MVP1."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    id: str
    category: str
    question: str
    expected_act: str | None
    expected_provisions: tuple[str, ...]
    acceptable_provisions: tuple[str, ...]
    expect_answer: bool
    required_concepts: tuple[str, ...]
    rationale: str
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalCaseResult:
    case_id: str
    category: str
    ranked_provisions: tuple[str, ...]
    expected_provisions: tuple[str, ...]
    reciprocal_rank: float
    recall_at_10: float


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    mode: str
    cases: int
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    hit_at_10: float
    mrr: float
    recall_at_10: float
    results: tuple[RetrievalCaseResult, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DecisionMetrics:
    cases: int
    expected_answer_responded: int
    expected_answer_abstained: int
    expected_abstain_responded: int
    expected_abstain_abstained: int

    @property
    def correct_decision_rate(self) -> float:
        if not self.cases:
            return 0.0
        correct = self.expected_answer_responded + self.expected_abstain_abstained
        return correct / self.cases
