"""Execução reproduzível do benchmark de retrieval."""

from collections.abc import Callable

from consultor_juridico.evaluation.metrics import (
    aggregate_retrieval,
    recall_at_k,
    reciprocal_rank,
)
from consultor_juridico.evaluation.types import (
    EvaluationCase,
    RetrievalCaseResult,
    RetrievalMetrics,
)
from consultor_juridico.retrieval import RetrievalCandidate

Search = Callable[[str, int], tuple[RetrievalCandidate, ...]]


def evaluate_retrieval(
    mode: str,
    cases: tuple[EvaluationCase, ...],
    search: Search,
    *,
    limit: int = 10,
) -> RetrievalMetrics:
    results = []
    for case in cases:
        if not case.expect_answer:
            continue
        candidates = search(case.question, limit)
        ranked = tuple(dict.fromkeys(item.identity_key for item in candidates))
        relevant = set(case.expected_provisions + case.acceptable_provisions)
        results.append(
            RetrievalCaseResult(
                case_id=case.id,
                category=case.category,
                ranked_provisions=ranked,
                # Hit/MRR aceitam fundamentos equivalentes anotados; Recall@10
                # continua medindo apenas as provisions primárias esperadas.
                expected_provisions=tuple(relevant),
                reciprocal_rank=reciprocal_rank(ranked, relevant),
                recall_at_10=recall_at_k(ranked, set(case.expected_provisions), 10),
            )
        )
    return aggregate_retrieval(mode, tuple(results))
