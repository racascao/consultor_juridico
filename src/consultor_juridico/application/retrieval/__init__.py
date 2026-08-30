"""Serviços de candidate retrieval do MVP2."""

from consultor_juridico.application.retrieval.evaluation import (
    RetrievalCandidateObservation,
    RetrievalCase,
    RetrievalCaseResult,
    RetrievalEvaluation,
    evaluate_retrieval,
    load_retrieval_dataset,
    write_evaluation,
)
from consultor_juridico.application.retrieval.indexing import (
    BuildRetrievalIndex,
    IndexBuildResult,
)
from consultor_juridico.application.retrieval.ports import (
    EmbeddingProvider,
    RetrievalRepository,
)
from consultor_juridico.application.retrieval.rrf import (
    diversify_article_families,
    reciprocal_rank_fusion,
)
from consultor_juridico.application.retrieval.service import HybridCandidateRetriever
from consultor_juridico.application.retrieval.types import (
    EmbeddingDocument,
    EmbeddingMode,
    RankedSearchUnit,
)

__all__ = [
    "BuildRetrievalIndex",
    "EmbeddingDocument",
    "EmbeddingMode",
    "EmbeddingProvider",
    "HybridCandidateRetriever",
    "IndexBuildResult",
    "RankedSearchUnit",
    "RetrievalCase",
    "RetrievalCandidateObservation",
    "RetrievalCaseResult",
    "RetrievalEvaluation",
    "RetrievalRepository",
    "diversify_article_families",
    "reciprocal_rank_fusion",
    "evaluate_retrieval",
    "load_retrieval_dataset",
    "write_evaluation",
]
