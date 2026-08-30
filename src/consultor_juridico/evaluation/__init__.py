"""Infraestrutura de avaliação sistemática do MVP1."""

from consultor_juridico.evaluation.dataset import (
    EvaluationDatasetError,
    load_dataset,
)
from consultor_juridico.evaluation.metrics import (
    aggregate_decisions,
    aggregate_retrieval,
    recall_at_k,
    reciprocal_rank,
)
from consultor_juridico.evaluation.quality import evaluate_evidence_quality
from consultor_juridico.evaluation.report import write_json_report
from consultor_juridico.evaluation.runner import evaluate_retrieval
from consultor_juridico.evaluation.semantic_judge import (
    benchmark_semantic_judge,
    load_semantic_dataset,
)

__all__ = [
    "EvaluationDatasetError",
    "aggregate_decisions",
    "aggregate_retrieval",
    "evaluate_retrieval",
    "evaluate_evidence_quality",
    "benchmark_semantic_judge",
    "load_dataset",
    "load_semantic_dataset",
    "recall_at_k",
    "reciprocal_rank",
    "write_json_report",
]
