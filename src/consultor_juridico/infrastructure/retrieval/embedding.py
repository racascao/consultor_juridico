"""Embeddings Ollama com modos document/query centralizados."""

from collections.abc import Callable
from time import perf_counter, sleep

import httpx

from consultor_juridico.application.retrieval.types import EmbeddingMode
from consultor_juridico.application.workflow.diagnostics import (
    ProviderCall,
    WorkflowDiagnostics,
)


class EmbeddingProviderError(RuntimeError):
    pass


class OllamaEmbeddingProvider:
    provider_name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float,
        dimensions: int = 768,
        client: httpx.Client | None = None,
        max_attempts: int = 2,
        retry_backoff_seconds: float = 0.25,
        sleeper: Callable[[float], None] = sleep,
        diagnostics: WorkflowDiagnostics | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts deve ser positivo.")
        self.model_name = model
        self.dimensions = dimensions
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._max_attempts = max_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._sleeper = sleeper
        self._diagnostics = diagnostics

    def embed(
        self, texts: tuple[str, ...], mode: EmbeddingMode
    ) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        prefixed = tuple(self._prefix(text, mode) for text in texts)
        started = perf_counter()
        try:
            response = self._request(prefixed)
        except EmbeddingProviderError:
            self._record_call(started, prefixed, "PROVIDER_ERROR")
            raise
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            self._record_call(started, prefixed, "PROVIDER_ERROR")
            raise EmbeddingProviderError(f"Falha no embedding Ollama: {exc}") from exc
        vectors = payload.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            self._record_call(started, prefixed, "INVALID_STRUCTURED_OUTPUT")
            raise EmbeddingProviderError("Resposta de embeddings incompatível.")
        result = tuple(tuple(float(value) for value in vector) for vector in vectors)
        if any(len(vector) != self.dimensions for vector in result):
            self._record_call(started, prefixed, "INVALID_STRUCTURED_OUTPUT")
            raise EmbeddingProviderError(
                f"Dimensão inválida; esperado {self.dimensions}."
            )
        self._record_call(started, prefixed)
        return result

    def _record_call(
        self,
        started: float,
        texts: tuple[str, ...],
        error_kind: str | None = None,
    ) -> None:
        if self._diagnostics is not None:
            self._diagnostics.add_provider_call(
                ProviderCall(
                    operation="embedding",
                    role="query_embedding",
                    model=self.model_name,
                    duration_ms=(perf_counter() - started) * 1000,
                    request_chars=sum(len(item) for item in texts),
                    output_validation="INVALID" if error_kind else "VALID",
                    error_kind=error_kind,
                )
            )

    def _request(self, prefixed: tuple[str, ...]) -> httpx.Response:
        for attempt in range(1, self._max_attempts + 1):
            try:
                client = self._client or httpx
                return client.post(
                    f"{self._base_url}/api/embed",
                    json={"model": self.model_name, "input": list(prefixed)},
                    timeout=self._timeout,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == self._max_attempts:
                    raise EmbeddingProviderError(
                        f"Falha transitória no embedding Ollama após "
                        f"{attempt} tentativas: {exc}"
                    ) from exc
                self._sleeper(self._retry_backoff_seconds * attempt)
        raise AssertionError("Loop de retry terminou sem resposta.")

    @staticmethod
    def _prefix(text: str, mode: EmbeddingMode) -> str:
        prefix = "search_document" if mode is EmbeddingMode.DOCUMENT else "search_query"
        return f"{prefix}: {text}"
