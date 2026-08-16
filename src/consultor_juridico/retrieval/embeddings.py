"""Cliente mínimo para embeddings locais via Ollama."""

from collections.abc import Sequence

import httpx


class EmbeddingProviderError(RuntimeError):
    """Falha explícita do provedor local de embeddings."""


class OllamaEmbeddingProvider:
    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        try:
            response = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": list(texts)},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            vectors = payload.get("embeddings")
            if not isinstance(vectors, list) or len(vectors) != len(texts):
                raise EmbeddingProviderError("Resposta de embeddings incompatível.")
            result = tuple(
                tuple(float(value) for value in vector) for vector in vectors
            )
            if not result or not result[0]:
                raise EmbeddingProviderError("Ollama retornou vetor vazio.")
            dimensions = len(result[0])
            if any(len(vector) != dimensions for vector in result):
                raise EmbeddingProviderError("Dimensões inconsistentes no lote.")
            return result
        except httpx.HTTPError as exc:
            raise EmbeddingProviderError(f"Falha no Ollama: {exc}") from exc
