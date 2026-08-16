"""Avaliação básica opt-in do retrieval no corpus real indexado."""

import os

import pytest

from consultor_juridico.config import settings
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.retrieval import (
    OllamaEmbeddingProvider,
    RetrievalFilters,
    hybrid_search,
    lexical_search,
)

pytestmark = pytest.mark.retrieval_integration


@pytest.mark.skipif(
    os.getenv("RUN_RETRIEVAL_INTEGRATION") != "1",
    reason="Defina RUN_RETRIEVAL_INTEGRATION=1 para avaliar o índice local.",
)
def test_reference_queries_retrieve_expected_provisions_read_only():
    provider = OllamaEmbeddingProvider(
        settings.ollama_base_url,
        settings.embedding_model,
        settings.embedding_timeout,
    )
    cases = (
        ("manifestação do pensamento", "ARTICLE:5/INCISO:IV"),
        ("educação direito de todos", "ARTICLE:205/CAPUT:@caput"),
        ("meio ambiente ecologicamente equilibrado", "ARTICLE:225/CAPUT:@caput"),
        ("voto direto e secreto", "ARTICLE:14/CAPUT:@caput"),
        ("poderes independentes e harmônicos", "ARTICLE:2/CAPUT:@caput"),
    )
    with SessionLocal() as session:
        for query, expected in cases:
            results = hybrid_search(
                session,
                query,
                provider,
                model_name=settings.embedding_model,
                limit=10,
                filters=RetrievalFilters(act="CF/88"),
            )
            assert results
            assert any(expected in item.identity_key for item in results), query
            assert all(item.legal_act == "CF/88" for item in results)

        lexical = lexical_search(
            session,
            "manifestação do pensamento",
            limit=5,
            filters=RetrievalFilters(act="CF/88", element_types=("INCISO",)),
        )
        assert lexical[0].identity_key.endswith("ARTICLE:5/INCISO:IV")
