"""Ports estritamente necessários ao retrieval."""

from contextlib import AbstractContextManager
from typing import Protocol

from consultor_juridico.application.retrieval.types import (
    EmbeddingDocument,
    EmbeddingMode,
    RankedSearchUnit,
)


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimensions: int

    def embed(
        self, texts: tuple[str, ...], mode: EmbeddingMode
    ) -> tuple[tuple[float, ...], ...]: ...


class RetrievalRepository(Protocol):
    def index_build_lock(self) -> AbstractContextManager[None]: ...

    def lexical(self, query: str, limit: int) -> tuple[RankedSearchUnit, ...]: ...

    def vector(
        self, query_vector: tuple[float, ...], model: str, limit: int
    ) -> tuple[RankedSearchUnit, ...]: ...

    def embedding_documents(
        self, provider: str, model: str
    ) -> tuple[EmbeddingDocument, ...]: ...

    def save_embeddings(
        self,
        documents: tuple[EmbeddingDocument, ...],
        vectors: tuple[tuple[float, ...], ...],
        provider: str,
        model: str,
        dimensions: int,
    ) -> None: ...
