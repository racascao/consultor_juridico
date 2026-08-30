"""Métricas determinísticas de selection e sufficiency."""

from collections.abc import Callable
from typing import Any

from consultor_juridico.consultation.selection import select_evidence_candidates
from consultor_juridico.consultation.sufficiency import assess_evidence_sufficiency
from consultor_juridico.evaluation.types import EvaluationCase
from consultor_juridico.retrieval import RetrievalCandidate

Search = Callable[[str, int], tuple[RetrievalCandidate, ...]]


def evaluate_evidence_quality(
    cases: tuple[EvaluationCase, ...],
    search: Search,
    *,
    retrieval_limit: int = 10,
    evidence_limit: int = 3,
) -> dict[str, Any]:
    results = []
    answerable = false_abstentions = correct_abstentions = unsafe_answers = 0
    selected_total = retrieved_total = duplicates_total = expected_selected = 0
    for case in cases:
        candidates = search(case.question, retrieval_limit)
        selected = select_evidence_candidates(
            candidates, limit=evidence_limit, question=case.question
        )
        report = assess_evidence_sufficiency(case.question, selected)
        selected_ids = {item.identity_key for item in selected}
        expected = set(case.expected_provisions + case.acceptable_provisions)
        if case.expect_answer:
            answerable += 1
            false_abstentions += not report.is_sufficient
            expected_selected += bool(expected.intersection(selected_ids))
        else:
            correct_abstentions += not report.is_sufficient
            unsafe_answers += report.is_sufficient
        retrieved_total += len(candidates)
        selected_total += len(selected)
        duplicates_total += len(candidates) - len(
            {item.legal_provision_id for item in candidates}
        )
        results.append(
            {
                "case_id": case.id,
                "expect_answer": case.expect_answer,
                "decision": report.decision.value,
                "reasons": list(report.reasons),
                "retrieved": len(candidates),
                "selected": len(selected),
                "expected_in_selected": bool(expected.intersection(selected_ids)),
                "lexical_score": report.lexical_score,
                "vector_score": report.vector_score,
                "retriever_agreement": report.retriever_agreement,
            }
        )
    abstention_cases = len(cases) - answerable
    return {
        "cases": len(cases),
        "answerable_cases": answerable,
        "abstention_cases": abstention_cases,
        "expected_provision_in_selected_rate": (
            expected_selected / answerable if answerable else 0.0
        ),
        "average_retrieved": retrieved_total / len(cases) if cases else 0.0,
        "average_selected": selected_total / len(cases) if cases else 0.0,
        "average_duplicate_provisions": (
            duplicates_total / len(cases) if cases else 0.0
        ),
        "correct_abstention_rate": (
            correct_abstentions / abstention_cases if abstention_cases else 0.0
        ),
        "unsafe_answer_rate": (
            unsafe_answers / abstention_cases if abstention_cases else 0.0
        ),
        "false_abstention_rate": (
            false_abstentions / answerable if answerable else 0.0
        ),
        "results": results,
    }
