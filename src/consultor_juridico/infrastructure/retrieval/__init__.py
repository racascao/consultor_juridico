"""Adapters PostgreSQL e Ollama do retrieval MVP2."""

from consultor_juridico.infrastructure.retrieval.embedding import (
    OllamaEmbeddingProvider,
)
from consultor_juridico.infrastructure.retrieval.repository import (
    PostgresRetrievalRepository,
)

__all__ = ["OllamaEmbeddingProvider", "PostgresRetrievalRepository"]
