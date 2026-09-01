"""Evaluator filesystem-only do baseline lexical da Lei nº 9.784/1999."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

from consultor_juridico.application.retrieval.ports import SearchUnitRetriever
from consultor_juridico.domain.retrieval import RetrievalCandidate, RetrievalRequest

ALLOWED_CATEGORIES = frozenset(
    {
        "DIRECT_RULE",
        "PARAPHRASE",
        "NEGATIVE",
        "DEADLINE",
        "COMPETENCE",
        "ENUMERATION",
        "EXCEPTION",
        "PROCEDURE",
    }
)


@dataclass(frozen=True, slots=True)
class RetrievalCase:
    case_id: str
    category: str
    question: str
    expected_provisions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalDataset:
    dataset_id: str
    legal_act_code: str
    cases: tuple[RetrievalCase, ...]


def load_dataset(path: Path) -> RetrievalDataset:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = tuple(
        RetrievalCase(
            case_id=item["case_id"],
            category=item["category"],
            question=item["question"],
            expected_provisions=tuple(item["expected_provisions"]),
        )
        for item in payload["cases"]
    )
    if not payload["dataset_id"].strip() or not payload["legal_act_code"].strip():
        raise ValueError("dataset_id e legal_act_code são obrigatórios")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("case_id deve ser único")
    for case in cases:
        if case.category not in ALLOWED_CATEGORIES:
            raise ValueError(f"Categoria inválida: {case.category}")
        if not case.question.strip():
            raise ValueError(f"Pergunta vazia: {case.case_id}")
        if not case.expected_provisions or any(
            not key.strip() for key in case.expected_provisions
        ):
            raise ValueError(f"expected_provisions inválido: {case.case_id}")
    return RetrievalDataset(payload["dataset_id"], payload["legal_act_code"], cases)


def evaluate_ranking(
    case: RetrievalCase, candidates: tuple[RetrievalCandidate, ...]
) -> dict[str, Any]:
    expected = frozenset(case.expected_provisions)
    first_rank = next(
        (
            candidate.rank
            for candidate in candidates[:10]
            if expected.intersection(candidate.provision_stable_keys)
        ),
        None,
    )
    reciprocal_rank = 0.0 if first_rank is None else 1.0 / first_rank
    return {
        "case_id": case.case_id,
        "category": case.category,
        "question": case.question,
        "expected_provisions": list(case.expected_provisions),
        "first_target_rank": first_rank,
        "reciprocal_rank": reciprocal_rank,
        "hit_at_1": first_rank is not None and first_rank <= 1,
        "hit_at_3": first_rank is not None and first_rank <= 3,
        "hit_at_5": first_rank is not None and first_rank <= 5,
        "hit_at_10": first_rank is not None and first_rank <= 10,
        "top_candidates": [
            {
                "rank": candidate.rank,
                "score": candidate.score,
                "unit_key": candidate.unit_key,
                "provision_stable_keys": list(candidate.provision_stable_keys),
            }
            for candidate in candidates[:10]
        ],
    }


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, float | int]:
    count = len(results)
    if count == 0:
        return {
            "case_count": 0,
            "hit_at_1": 0.0,
            "hit_at_3": 0.0,
            "hit_at_5": 0.0,
            "hit_at_10": 0.0,
            "mrr": 0.0,
        }
    return {
        "case_count": count,
        "hit_at_1": sum(item["hit_at_1"] for item in results) / count,
        "hit_at_3": sum(item["hit_at_3"] for item in results) / count,
        "hit_at_5": sum(item["hit_at_5"] for item in results) / count,
        "hit_at_10": sum(item["hit_at_10"] for item in results) / count,
        "mrr": sum(item["reciprocal_rank"] for item in results) / count,
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * percentile) - 1))
    return ordered[index]


def run_retrieval_baseline(
    retriever: SearchUnitRetriever,
    *,
    dataset_path: Path,
    version_hash: str,
    output_path: Path,
) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"O resultado não pode ser sobrescrito: {output_path}")
    raw_dataset = dataset_path.read_bytes()
    dataset = load_dataset(dataset_path)
    context = retriever.context(version_hash)
    if context.legal_act_code != dataset.legal_act_code:
        raise ValueError(
            "ActVersion não pertence ao ato jurídico declarado pelo dataset"
        )
    available = retriever.provision_keys(version_hash)
    missing = sorted(
        {
            key
            for case in dataset.cases
            for key in case.expected_provisions
            if key not in available
        }
    )
    if missing:
        raise ValueError(f"Targets ausentes na ActVersion: {', '.join(missing)}")

    case_results: list[dict[str, Any]] = []
    latencies_ms: list[float] = []
    for case in dataset.cases:
        started = perf_counter()
        candidates = retriever.search(
            RetrievalRequest(case.question, version_hash, limit=10)
        )
        latencies_ms.append((perf_counter() - started) * 1000)
        case_results.append(evaluate_ranking(case, candidates))

    by_category = {
        category: aggregate_results(
            [item for item in case_results if item["category"] == category]
        )
        for category in sorted({case.category for case in dataset.cases})
    }
    result = {
        "metadata": {
            "dataset_id": dataset.dataset_id,
            "dataset_sha256": sha256(raw_dataset).hexdigest(),
            "legal_act_code": dataset.legal_act_code,
            "version_hash": context.version_hash,
            "act_version_id": str(context.act_version_id),
            "source_snapshot_sha256": context.source_snapshot_sha256,
            "parser_name": context.parser_name,
            "parser_version": context.parser_version,
            "projection_name": context.projection_name,
            "projection_version": context.projection_version,
            "retrieval_implementation": retriever.implementation_name,
            "retrieval_config": dict(retriever.retrieval_config),
            "executed_at": datetime.now(UTC).isoformat(),
            "case_count": len(dataset.cases),
            "category_counts": dict(
                sorted(Counter(case.category for case in dataset.cases).items())
            ),
        },
        "overall": aggregate_results(case_results),
        "by_category": by_category,
        "latency_ms": {
            "p50": median(latencies_ms) if latencies_ms else 0.0,
            "p95": _percentile(latencies_ms, 0.95),
        },
        "cases": case_results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result
