"""Testes determinísticos da infraestrutura de avaliação."""

import json
import uuid

import pytest

from consultor_juridico.evaluation import (
    EvaluationDatasetError,
    aggregate_decisions,
    aggregate_retrieval,
    benchmark_semantic_judge,
    evaluate_evidence_quality,
    load_dataset,
    load_semantic_dataset,
    recall_at_k,
    reciprocal_rank,
    write_json_report,
)
from consultor_juridico.evaluation.types import (
    EvaluationCase,
    RetrievalCaseResult,
)

DATASET = "evaluation/datasets/mvp1_v1.json"
SEMANTIC_DATASET = "evaluation/datasets/semantic_support_v1.json"


def test_dataset_is_versioned_unique_and_representative():
    version, cases = load_dataset(DATASET)
    assert version == "mvp1-v1"
    assert 30 <= len(cases) <= 50
    assert len({case.id for case in cases}) == len(cases)
    categories = {case.category for case in cases}
    assert {
        "direct",
        "multi_provision",
        "adct",
        "outside_corpus",
        "adversarial",
    } <= categories


def test_dataset_rejects_duplicate_ids(tmp_path):
    case = {
        "id": "x",
        "category": "direct",
        "question": "Q?",
        "expected_act": "CF/88",
        "expected_provisions": ["p"],
        "expect_answer": True,
        "required_concepts": [],
        "rationale": "R",
        "tags": [],
    }
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"version": "v", "cases": [case, case]}))
    with pytest.raises(EvaluationDatasetError, match="únicos"):
        load_dataset(path)


def test_semantic_dataset_is_versioned_balanced_and_unique():
    version, cases = load_semantic_dataset(SEMANTIC_DATASET)
    assert version == "semantic-support-v1"
    assert 20 <= len(cases) <= 30
    assert len({case.case_id for case in cases}) == len(cases)
    assert {case.expected for case in cases} == {
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "UNSUPPORTED",
    }


def test_semantic_benchmark_measures_unsafe_acceptance_and_false_abstention():
    from consultor_juridico.consultation.types import (
        ClaimSupport,
        SemanticSupportReport,
        SemanticSupportStatus,
    )

    _, cases = load_semantic_dataset(SEMANTIC_DATASET)

    class FixedValidator:
        def validate(self, response, items):
            status = (
                SemanticSupportStatus.UNSUPPORTED
                if response.claims[0].text.startswith("São Poderes")
                else SemanticSupportStatus.SUPPORTED
            )
            return SemanticSupportReport(
                (
                    ClaimSupport(
                        "C1",
                        status,
                        tuple(item.evidence_code for item in items),
                        "resultado fixo",
                    ),
                )
            )

    metrics = benchmark_semantic_judge(cases[:2], FixedValidator())
    assert metrics["cases"] == 2
    assert metrics["false_abstention_potential"] == 1
    assert metrics["unsafe_acceptance"] == 0
    assert metrics["invalid_contracts"] == 0


def test_reciprocal_rank_and_recall_at_k():
    ranked = ("x", "expected", "other")
    assert reciprocal_rank(ranked, {"expected"}) == 0.5
    assert reciprocal_rank(ranked, {"missing"}) == 0
    assert recall_at_k(ranked, {"expected", "other"}, 2) == 0.5
    assert recall_at_k(ranked, {"expected", "other"}, 3) == 1


def test_retrieval_aggregation_is_deterministic():
    result = RetrievalCaseResult(
        "case", "direct", ("expected",), ("expected",), 1.0, 1.0
    )
    first = aggregate_retrieval("hybrid", (result,))
    second = aggregate_retrieval("hybrid", (result,))
    assert first == second
    assert first.hit_at_1 == first.hit_at_10 == first.mrr == 1


def test_decision_confusion_matrix():
    answer_case = _case(True)
    abstain_case = _case(False)
    metrics = aggregate_decisions(
        (
            (answer_case, True),
            (answer_case, False),
            (abstain_case, False),
            (abstain_case, True),
        )
    )
    assert metrics.expected_answer_responded == 1
    assert metrics.expected_answer_abstained == 1
    assert metrics.expected_abstain_abstained == 1
    assert metrics.expected_abstain_responded == 1
    assert metrics.correct_decision_rate == 0.5


def test_report_serialization_is_stable(tmp_path):
    target = tmp_path / "report.json"
    payload = {"z": 1, "dataset": "mvp1-v1"}
    write_json_report(target, payload)
    first = target.read_text()
    write_json_report(target, payload)
    assert target.read_text() == first
    assert json.loads(first) == payload


def test_evidence_quality_measures_safe_and_false_abstention():
    answer_case = _case(True)
    abstain_case = _case(False)

    calls = iter((True, False))

    def search(_question, _limit):
        from tests.test_quality_hardening import _candidate

        if next(calls):
            return (_candidate("answer"),)
        return (_candidate("weak", lexical=0.0, vector=0.0),)

    metrics = evaluate_evidence_quality((answer_case, abstain_case), search)
    assert metrics["false_abstention_rate"] == 0
    assert metrics["correct_abstention_rate"] == 1
    assert metrics["unsafe_answer_rate"] == 0


def _case(expect_answer: bool) -> EvaluationCase:
    return EvaluationCase(
        id=str(uuid.uuid4()),
        category="test",
        question="Pergunta",
        expected_act="CF/88" if expect_answer else None,
        expected_provisions=("p",) if expect_answer else (),
        acceptable_provisions=(),
        expect_answer=expect_answer,
        required_concepts=(),
        rationale="Teste",
        tags=(),
    )
