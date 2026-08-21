"""Indexação e retrieval jurídico híbrido."""

from consultor_juridico.retrieval.chunking import CHUNK_STRATEGY, build_chunk_drafts
from consultor_juridico.retrieval.embeddings import (
    EmbeddingProviderError,
    OllamaEmbeddingProvider,
)
from consultor_juridico.retrieval.indexing import build_search_index
from consultor_juridico.retrieval.search import (
    contextual_caput_rerank,
    hybrid_search,
    lexical_search,
    reciprocal_rank_fusion,
    vector_search,
)
from consultor_juridico.retrieval.types import (
    IndexingOutcome,
    IndexingResult,
    RetrievalCandidate,
    RetrievalFilters,
)

__all__ = [
    "CHUNK_STRATEGY",
    "EmbeddingProviderError",
    "IndexingOutcome",
    "IndexingResult",
    "OllamaEmbeddingProvider",
    "RetrievalCandidate",
    "RetrievalFilters",
    "build_chunk_drafts",
    "build_search_index",
    "hybrid_search",
    "contextual_caput_rerank",
    "lexical_search",
    "reciprocal_rank_fusion",
    "vector_search",
]
