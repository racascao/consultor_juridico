"""Benchmark offline de cross-encoders para Query ↔ Core Assertion.

Este módulo é experimental e não é importado pelo pipeline de produção.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from evaluation.semantic_core_relevance_88 import controls, load_frozen_cases

PRIMARY = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
PRIMARY_REVISION = "1427fd652930e4ba29e8149678df786c240d8825"
CONTROL = "BAAI/bge-reranker-v2-m3"
CONTROL_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"


@dataclass(frozen=True, slots=True)
class Pair:
    name: str
    query: str
    assertion: str
    expected: str


def frozen_pairs() -> tuple[Pair, ...]:
    relevance = Path("evaluation/results/relevance_core_86.json")
    vcsa = Path("evaluation/results/vcsa_87.json")
    historical, main = load_frozen_cases(relevance, vcsa)
    base = [
        Pair(item.name, item.query, item.assertion, item.expected.value)
        for item in controls()
    ]
    base.extend(
        Pair(item.name, item.query, item.assertion, item.expected.value)
        for item in (*historical, *main)
    )
    return tuple(base)


class OnnxCrossEncoder:
    def __init__(
        self, model_id: str = PRIMARY, revision: str = PRIMARY_REVISION
    ) -> None:
        self.model_id = model_id
        self.revision = revision
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
        model_path = hf_hub_download(
            model_id,
            "onnx/model_quint8_avx2.onnx",
            revision=revision,
        )
        self.model_path = model_path
        self.session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"],
        )
        self.input_names = {item.name for item in self.session.get_inputs()}
        self.output_name = self.session.get_outputs()[0].name

    def score(self, pairs: list[tuple[str, str]]) -> tuple[list[float], float]:
        started = time.perf_counter()
        encoded = self.tokenizer(
            [query for query, _ in pairs],
            [assertion for _, assertion in pairs],
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="np",
        )
        inputs = {
            name: np.asarray(encoded[name], dtype=np.int64)
            for name in self.input_names
            if name in encoded
        }
        raw = self.session.run([self.output_name], inputs)[0]
        values = np.asarray(raw).reshape(-1)
        elapsed = (time.perf_counter() - started) * 1000
        return [float(value) for value in values], elapsed


class TorchCrossEncoder:
    def __init__(
        self, model_id: str = CONTROL, revision: str = CONTROL_REVISION
    ) -> None:
        import torch

        self.torch = torch
        self.model_id = model_id
        self.revision = revision
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_id, revision=revision
        ).eval()

    def score(self, pairs: list[tuple[str, str]]) -> tuple[list[float], float]:
        started = time.perf_counter()
        encoded = self.tokenizer(
            [query for query, _ in pairs],
            [assertion for _, assertion in pairs],
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        with self.torch.no_grad():
            values = self.model(**encoded).logits.reshape(-1).tolist()
        return [float(value) for value in values], (
            time.perf_counter() - started
        ) * 1000


def classify(score: float, low: float, high: float) -> str:
    if score >= high:
        return "RELEVANT"
    if score <= low:
        return "IRRELEVANT"
    return "UNRESOLVED"


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    relevant = [row for row in rows if row["expected"] == "RELEVANT"]
    irrelevant = [row for row in rows if row["expected"] == "IRRELEVANT"]
    return {
        "false_relevant": sum(row["decision"] == "RELEVANT" for row in irrelevant),
        "false_irrelevant": sum(row["decision"] == "IRRELEVANT" for row in relevant),
        "unresolved": sum(row["decision"] == "UNRESOLVED" for row in rows),
        "relevant_total": len(relevant),
        "irrelevant_total": len(irrelevant),
        "latency_mean_ms": statistics.mean(row["latency_ms"] for row in rows),
        "latency_p50_ms": statistics.median(row["latency_ms"] for row in rows),
        "latency_p95_ms": float(np.percentile([row["latency_ms"] for row in rows], 95)),
    }


def run(output: Path, model_id: str = PRIMARY) -> dict[str, Any]:
    pairs = frozen_pairs()
    model = OnnxCrossEncoder() if model_id == PRIMARY else TorchCrossEncoder()
    # Uma inferência única sobre todos os pares congela a distribuição antes da
    # classificação final; nenhum texto esperado é enviado ao modelo.
    scores, batch_ms = model.score([(item.query, item.assertion) for item in pairs])
    positives = [
        score
        for score, item in zip(scores, pairs, strict=True)
        if item.expected == "RELEVANT"
    ]
    negatives = [
        score
        for score, item in zip(scores, pairs, strict=True)
        if item.expected == "IRRELEVANT"
    ]
    low, high = max(negatives), min(positives)
    rows = []
    for item, score in zip(pairs, scores, strict=True):
        rows.append(
            {
                "name": item.name,
                "query": item.query,
                "assertion": item.assertion,
                "expected": item.expected,
                "score": score,
                "decision": classify(score, low, high),
                "latency_ms": batch_ms / len(pairs),
            }
        )
    result = {
        "phase": "controlled_relevance_model_benchmark_90",
        "model": {
            "id": model.model_id,
            "revision": model.revision,
            "runtime": "onnxruntime CPU" if model_id == PRIMARY else "torch CPU",
            "model_file": getattr(model, "model_path", "huggingface snapshot"),
            "providers": list(model.session.get_providers())
            if hasattr(model, "session")
            else ["CPU"],
            "input_names": sorted(model.input_names),
            "dtype": "quint8 ONNX AVX2" if model_id == PRIMARY else "float32",
        },
        "task": "Query ↔ Verified/Core Assertion relevance",
        "thresholds": {
            "low": low,
            "high": high,
            "method": "max_negative_vs_min_positive_frozen_pairs_v1",
            "separable": low < high,
        },
        "rows": rows,
        "metrics": metrics(rows),
        "gate": {
            "primary_gate": bool(
                low < high
                and metrics(rows)["false_relevant"] == 0
                and rows_by_name(rows)["rw-prisao-perpetua"]["decision"] == "RELEVANT"
                and rows_by_name(rows)["rw-pena-morte"]["decision"] == "RELEVANT"
            ),
            "production_integration": "NOT_ENABLED",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def rows_by_name(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["name"]: row for row in rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/relevance_model_benchmark_90_minilm.json"),
    )
    parser.add_argument("--model", choices=("primary", "control"), default="primary")
    args = parser.parse_args()
    model_id = PRIMARY if args.model == "primary" else CONTROL
    result = run(args.output, model_id)
    print(
        json.dumps(
            {
                "model": result["model"],
                "metrics": result["metrics"],
                "gate": result["gate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
