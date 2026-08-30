"""Métricas determinísticas de retrieval e decisão de abstenção."""

from consultor_juridico.evaluation.types import (
    DecisionMetrics,
    EvaluationCase,
    RetrievalCaseResult,
    RetrievalMetrics,
)


def reciprocal_rank(ranked: tuple[str, ...], relevant: set[str]) -> float:
    for rank, identity in enumerate(ranked, start=1):
        if identity in relevant:
            return 1.0 / rank
    return 0.0


def recall_at_k(ranked: tuple[str, ...], expected: set[str], k: int) -> float:
    if not expected:
        return 0.0
    return len(expected.intersection(ranked[:k])) / len(expected)


def aggregate_retrieval(
    mode: str, results: tuple[RetrievalCaseResult, ...]
) -> RetrievalMetrics:
    if not results:
        return RetrievalMetrics(mode, 0, 0, 0, 0, 0, 0, 0, ())

    def hit(k: int) -> float:
        return sum(
            bool(set(item.expected_provisions).intersection(item.ranked_provisions[:k]))
            for item in results
        ) / len(results)

    return RetrievalMetrics(
        mode=mode,
        cases=len(results),
        hit_at_1=hit(1),
        hit_at_3=hit(3),
        hit_at_5=hit(5),
        hit_at_10=hit(10),
        mrr=sum(item.reciprocal_rank for item in results) / len(results),
        recall_at_10=sum(item.recall_at_10 for item in results) / len(results),
        results=results,
    )


def aggregate_decisions(
    outcomes: tuple[tuple[EvaluationCase, bool], ...],
) -> DecisionMetrics:
    return DecisionMetrics(
        cases=len(outcomes),
        expected_answer_responded=sum(
            c.expect_answer and answered for c, answered in outcomes
        ),
        expected_answer_abstained=sum(
            c.expect_answer and not answered for c, answered in outcomes
        ),
        expected_abstain_responded=sum(
            not c.expect_answer and answered for c, answered in outcomes
        ),
        expected_abstain_abstained=sum(
            not c.expect_answer and not answered for c, answered in outcomes
        ),
    )
