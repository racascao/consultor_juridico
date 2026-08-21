"""Integração opt-in e somente leitura do benchmark de retrieval."""

import os

import pytest

from consultor_juridico.config import settings
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.evaluation import evaluate_retrieval, load_dataset
from consultor_juridico.retrieval import OllamaEmbeddingProvider, hybrid_search

pytestmark = [
    pytest.mark.evaluation_integration,
    pytest.mark.skipif(
        os.getenv("RUN_EVALUATION_INTEGRATION") != "1",
        reason="benchmark de avaliação é opt-in",
    ),
]


def test_versioned_dataset_runs_against_materialized_corpus():
    version, cases = load_dataset("evaluation/datasets/mvp1_v1.json")
    provider = OllamaEmbeddingProvider(
        settings.ollama_base_url, settings.embedding_model, settings.embedding_timeout
    )
    with SessionLocal() as session:
        metrics = evaluate_retrieval(
            "hybrid",
            cases,
            lambda query, limit: hybrid_search(
                session,
                query,
                provider,
                model_name=settings.embedding_model,
                limit=limit,
            ),
        )
    assert version == "mvp1-v1"
    assert metrics.cases == 21
    assert 0 <= metrics.hit_at_10 <= 1
    assert 0 <= metrics.recall_at_10 <= 1
