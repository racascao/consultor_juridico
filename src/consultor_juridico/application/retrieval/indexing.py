"""Construção idempotente somente das embeddings ausentes ou obsoletas."""

from collections.abc import Callable
from dataclasses import dataclass

from consultor_juridico.application.retrieval.ports import (
    EmbeddingProvider,
    RetrievalRepository,
)
from consultor_juridico.application.retrieval.types import EmbeddingMode


@dataclass(frozen=True, slots=True)
class IndexBuildResult:
    embedded: int
    model: str
    dimensions: int


class BuildRetrievalIndex:
    def __init__(
        self,
        repository: RetrievalRepository,
        provider: EmbeddingProvider,
        batch_size: int = 32,
        progress: Callable[[int, int], None] | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size deve ser positivo.")
        self._repository = repository
        self._provider = provider
        self._batch_size = batch_size
        self._progress = progress

    def execute(self) -> IndexBuildResult:
        with self._repository.index_build_lock():
            documents = self._repository.embedding_documents(
                self._provider.provider_name, self._provider.model_name
            )
            total = len(documents)
            completed = 0
            for start in range(0, total, self._batch_size):
                batch = documents[start : start + self._batch_size]
                vectors = self._provider.embed(
                    tuple(item.search_text for item in batch), EmbeddingMode.DOCUMENT
                )
                self._repository.save_embeddings(
                    batch,
                    vectors,
                    self._provider.provider_name,
                    self._provider.model_name,
                    self._provider.dimensions,
                )
                completed += len(batch)
                if self._progress is not None:
                    self._progress(completed, total)
            return IndexBuildResult(
                completed, self._provider.model_name, self._provider.dimensions
            )
