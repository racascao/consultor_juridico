"""Screen E2E da configuração single-LLM usando o serviço real de consulta."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from consultor_juridico.config import settings
from consultor_juridico.consultation import (
    OllamaLegalGenerator,
    OllamaSemanticSupportValidator,
)
from consultor_juridico.evaluation.dataset import load_dataset
from consultor_juridico.evaluation.real_world import evaluate_real_world
from consultor_juridico.retrieval.embeddings import OllamaEmbeddingProvider

DATASET = Path("evaluation/datasets/real_world_short_v1.json")
EXPECTED_HASH = "c6b496d20dd9b7b5952f7abecca92e64c0179ce134794f5e3b39e579025f441f"
OUTPUT = Path("evaluation/results/model_benchmark_91_1/e2e_single_model_screen.json")


def main() -> None:
    digest = hashlib.sha256(DATASET.read_bytes()).hexdigest()
    if digest != EXPECTED_HASH:
        raise RuntimeError(f"hash do dataset divergente: {digest}")
    _version, cases = load_dataset(DATASET)
    provider = OllamaEmbeddingProvider(
        settings.ollama_base_url, settings.embedding_model, settings.embedding_timeout
    )
    generator = OllamaLegalGenerator(
        settings.ollama_base_url,
        settings.ollama_model,
        settings.consultation_timeout,
        settings.consultation_max_tokens,
    )
    semantic = OllamaSemanticSupportValidator(
        settings.ollama_base_url,
        settings.semantic_judge_model or settings.ollama_model,
        settings.consultation_timeout,
    )
    result = evaluate_real_world(
        cases,
        provider,
        generator,
        semantic,
        settings.ollama_model,
        settings.embedding_model,
    )
    payload = {
        "phase": "91.1",
        "dataset": DATASET.name,
        "dataset_sha256": digest,
        "configuration": {
            "generator_model": settings.ollama_model,
            "generator_num_predict": settings.consultation_max_tokens,
            "generator_think": False,
            "semantic_model": settings.semantic_judge_model or settings.ollama_model,
            "semantic_num_predict": 500,
            "semantic_think": False,
            "relevance_mode": "DETERMINISTIC",
            "relevance_model": None,
            "embedding_model": settings.embedding_model,
        },
        "timestamp": datetime.now(UTC).isoformat(),
        **result,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
