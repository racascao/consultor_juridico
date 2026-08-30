"""Benchmark reproduzível do Semantic Support Validator local."""

import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from consultor_juridico.consultation.semantic import SemanticSupportValidator
from consultor_juridico.consultation.types import GeneratedClaim, GeneratedResponse


@dataclass(frozen=True, slots=True)
class SemanticJudgeCase:
    case_id: str
    claim: str
    evidence: tuple[str, ...]
    expected: str
    category: str


def load_semantic_dataset(
    path: str | Path,
) -> tuple[str, tuple[SemanticJudgeCase, ...]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = tuple(
        SemanticJudgeCase(
            case_id=value["id"],
            claim=value["claim"],
            evidence=tuple(value["evidence"]),
            expected=value["expected"],
            category=value["category"],
        )
        for value in payload["cases"]
    )
    if not cases or len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Dataset semântico vazio ou com IDs duplicados.")
    if any(
        case.expected not in {"SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"}
        for case in cases
    ):
        raise ValueError("Status esperado inválido no dataset semântico.")
    return payload["version"], cases


def benchmark_semantic_judge(
    cases: tuple[SemanticJudgeCase, ...],
    validator: SemanticSupportValidator,
) -> dict[str, Any]:
    results = []
    latencies = []
    for case in cases:
        items = tuple(
            SimpleNamespace(evidence_code=f"EV{index:03d}", text_snapshot=text)
            for index, text in enumerate(case.evidence, start=1)
        )
        response = GeneratedResponse(
            "",
            (
                GeneratedClaim(
                    "C1", case.claim, tuple(item.evidence_code for item in items)
                ),
            ),
        )
        started = time.perf_counter()
        report = validator.validate(response, items)
        elapsed = time.perf_counter() - started
        latencies.append(elapsed)
        actual = report.claims[0].status.value if report.claims else "TECHNICAL_ERROR"
        results.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "expected": case.expected,
                "actual": actual,
                "correct": actual == case.expected,
                "latency_seconds": elapsed,
                "technical_error": report.technical_error,
                "reason": report.claims[0].reason if report.claims else None,
            }
        )
    supported = [item for item in results if item["expected"] == "SUPPORTED"]
    predicted_supported = [item for item in results if item["actual"] == "SUPPORTED"]
    true_supported = sum(item["correct"] for item in supported)
    unsafe = sum(
        item["actual"] == "SUPPORTED" and item["expected"] != "SUPPORTED"
        for item in results
    )
    ordered = sorted(latencies)
    return {
        "cases": len(results),
        "accuracy": sum(item["correct"] for item in results) / len(results),
        "supported_precision": (
            (len(predicted_supported) - unsafe) / len(predicted_supported)
            if predicted_supported
            else 0.0
        ),
        "supported_recall": true_supported / len(supported) if supported else 0.0,
        "unsafe_acceptance": unsafe,
        "false_abstention_potential": sum(
            item["expected"] == "SUPPORTED" and item["actual"] != "SUPPORTED"
            for item in results
        ),
        "invalid_contracts": sum(
            item["actual"] == "TECHNICAL_ERROR" for item in results
        ),
        "latency_mean_seconds": statistics.fmean(latencies),
        "latency_p50_seconds": statistics.median(latencies),
        "latency_p95_observed_seconds": ordered[max(0, int(len(ordered) * 0.95) - 1)],
        "results": results,
    }
