"""Contratos puros do retrieval lexical e do evaluator da Fase 1."""

import json
from pathlib import Path
from uuid import UUID

import pytest

from consultor_juridico.domain.retrieval import (
    RetrievalCandidate,
    RetrievalContext,
    RetrievalRequest,
)
from consultor_juridico.evaluation.retrieval_baseline import (
    RetrievalCase,
    aggregate_results,
    evaluate_ranking,
    load_dataset,
    run_retrieval_baseline,
)

VERSION_HASH = "a" * 64


def _dataset(tmp_path: Path, cases: list[dict]) -> Path:
    path = tmp_path / "dataset.json"
    path.write_text(
        json.dumps(
            {
                "dataset_id": "test_v1",
                "legal_act_code": "ACT",
                "cases": cases,
            }
        ),
        encoding="utf-8",
    )
    return path


def _case(**changes) -> dict:
    value = {
        "case_id": "DEV-001",
        "category": "DIRECT_RULE",
        "question": "Qual é a regra aplicável?",
        "expected_provisions": ["ARTICLE:1/CAPUT"],
    }
    value.update(changes)
    return value


def _candidate(rank: int, *keys: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        rank=rank,
        search_unit_id=UUID(int=rank),
        unit_key=f"UNIT:{rank}",
        score=1.0 / rank,
        provision_stable_keys=tuple(keys),
        search_text=f"texto {rank}",
    )


def test_dataset_parsing_preserves_multiple_expected_provisions(tmp_path):
    path = _dataset(
        tmp_path,
        [_case(expected_provisions=["ARTICLE:1/CAPUT", "ARTICLE:1/PARAGRAPH:1"])],
    )
    dataset = load_dataset(path)
    assert dataset.dataset_id == "test_v1"
    assert dataset.cases[0].expected_provisions == (
        "ARTICLE:1/CAPUT",
        "ARTICLE:1/PARAGRAPH:1",
    )


def test_dataset_rejects_duplicate_case_id(tmp_path):
    with pytest.raises(ValueError, match="case_id deve ser único"):
        load_dataset(_dataset(tmp_path, [_case(), _case()]))


def test_dataset_rejects_unknown_category(tmp_path):
    with pytest.raises(ValueError, match="Categoria inválida"):
        load_dataset(_dataset(tmp_path, [_case(category="UNKNOWN")]))


@pytest.mark.parametrize("expected", [[], [""]])
def test_dataset_requires_expected_provisions(tmp_path, expected):
    with pytest.raises(ValueError, match="expected_provisions inválido"):
        load_dataset(_dataset(tmp_path, [_case(expected_provisions=expected)]))


def test_retrieval_request_rejects_empty_question():
    with pytest.raises(ValueError, match="não pode ser vazia"):
        RetrievalRequest("  ", VERSION_HASH)


@pytest.mark.parametrize("limit", [0, 101])
def test_retrieval_request_validates_limit(limit):
    with pytest.raises(ValueError, match="entre 1 e 100"):
        RetrievalRequest("pergunta", VERSION_HASH, limit)


@pytest.mark.parametrize(
    ("rank", "expected_hits", "expected_rr"),
    [
        (1, (True, True, True, True), 1.0),
        (3, (False, True, True, True), 1 / 3),
        (5, (False, False, True, True), 1 / 5),
        (10, (False, False, False, True), 0.1),
        (11, (False, False, False, False), 0.0),
    ],
)
def test_hit_at_k_and_mrr(rank, expected_hits, expected_rr):
    case = RetrievalCase("DEV-001", "DIRECT_RULE", "pergunta", ("EXPECTED",))
    candidates = tuple(
        _candidate(position, "EXPECTED" if position == rank else f"OTHER:{position}")
        for position in range(1, 12)
    )
    result = evaluate_ranking(case, candidates)
    assert (
        result["hit_at_1"],
        result["hit_at_3"],
        result["hit_at_5"],
        result["hit_at_10"],
    ) == expected_hits
    assert result["reciprocal_rank"] == pytest.approx(expected_rr)


def test_any_explicit_expected_provision_is_a_hit():
    case = RetrievalCase("DEV-001", "DIRECT_RULE", "q", ("A", "B"))
    result = evaluate_ranking(case, (_candidate(1, "B"),))
    assert result["first_target_rank"] == 1


def test_aggregate_calculates_metrics_without_composite_score():
    results = [
        {
            "hit_at_1": True,
            "hit_at_3": True,
            "hit_at_5": True,
            "hit_at_10": True,
            "reciprocal_rank": 1.0,
        },
        {
            "hit_at_1": False,
            "hit_at_3": False,
            "hit_at_5": False,
            "hit_at_10": False,
            "reciprocal_rank": 0.0,
        },
    ]
    aggregate = aggregate_results(results)
    assert aggregate == {
        "case_count": 2,
        "hit_at_1": 0.5,
        "hit_at_3": 0.5,
        "hit_at_5": 0.5,
        "hit_at_10": 0.5,
        "mrr": 0.5,
    }
    assert "score" not in aggregate


def test_evaluator_groups_categories_and_writes_new_artifact(tmp_path):
    dataset_path = _dataset(
        tmp_path,
        [
            _case(),
            _case(
                case_id="DEV-002",
                category="PARAPHRASE",
                question="Como a regra é expressa?",
            ),
        ],
    )
    output_path = tmp_path / "result.json"

    class FakeRetriever:
        implementation_name = "POSTGRESQL_FTS_TEST"
        retrieval_config = {
            "text_search_config": "portuguese",
            "query_function": "websearch_to_tsquery",
            "rank_function": "ts_rank_cd",
            "max_rank": 10,
            "tie_break": "unit_key ASC",
        }

        def search(self, request):
            return (_candidate(1, "ARTICLE:1/CAPUT"),)

        def context(self, version_hash):
            return RetrievalContext(
                legal_act_code="ACT",
                act_version_id=UUID(int=42),
                version_hash=version_hash,
                source_snapshot_sha256="b" * 64,
                parser_name="parser",
                parser_version="1",
                projection_name="projection",
                projection_version="1",
            )

        def provision_keys(self, version_hash):
            return frozenset({"ARTICLE:1/CAPUT"})

    result = run_retrieval_baseline(
        FakeRetriever(),
        dataset_path=dataset_path,
        version_hash=VERSION_HASH,
        output_path=output_path,
    )
    assert output_path.exists()
    assert result["overall"]["hit_at_10"] == 1.0
    assert set(result["by_category"]) == {"DIRECT_RULE", "PARAPHRASE"}
    assert result["metadata"]["retrieval_config"]["max_rank"] == 10
    assert result["metadata"]["retrieval_implementation"] == "POSTGRESQL_FTS_TEST"
    with pytest.raises(FileExistsError, match="não pode ser sobrescrito"):
        run_retrieval_baseline(
            FakeRetriever(),
            dataset_path=dataset_path,
            version_hash=VERSION_HASH,
            output_path=output_path,
        )
