"""Testes unitários do ranking híbrido e provedor de embeddings."""

import uuid
from dataclasses import replace

import httpx
import pytest

from consultor_juridico.retrieval.embeddings import (
    EmbeddingProviderError,
    OllamaEmbeddingProvider,
)
from consultor_juridico.retrieval.search import (
    contextual_caput_rerank,
    lexical_query_text,
    reciprocal_rank_fusion,
)
from consultor_juridico.retrieval.types import RetrievalCandidate


def _candidate(label: str, *, lexical=None, vector=None):
    identifier = uuid.uuid5(uuid.NAMESPACE_DNS, label)
    return RetrievalCandidate(
        chunk_id=identifier,
        legal_element_id=uuid.uuid4(),
        legal_provision_id=uuid.uuid4(),
        legal_act="CF/88",
        element_type="CAPUT",
        number_label=label,
        identity_key=f"CF88/@root/ARTICLE:{label}/CAPUT:@caput",
        chunk_text=label,
        lexical_rank=lexical,
        vector_rank=vector,
    )


def test_rrf_preserves_component_ranks_and_is_deterministic():
    lexical = (_candidate("5", lexical=1), _candidate("6", lexical=2))
    vector = (_candidate("6", vector=1), _candidate("7", vector=2))
    first = reciprocal_rank_fusion(lexical, vector, limit=3)
    second = reciprocal_rank_fusion(lexical, vector, limit=3)
    assert first == second
    assert first[0].number_label == "6"
    assert first[0].lexical_rank == 2
    assert first[0].vector_rank == 1
    assert first[0].rrf_score == pytest.approx(1 / 62 + 1 / 61)


def test_ollama_provider_validates_batch(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: Response())
    provider = OllamaEmbeddingProvider("http://ollama:11434", "model", 10)
    assert provider.embed(["a", "b"]) == ((0.1, 0.2), (0.3, 0.4))


def test_ollama_provider_rejects_incompatible_response(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": []}

    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: Response())
    provider = OllamaEmbeddingProvider("http://ollama:11434", "model", 10)
    with pytest.raises(EmbeddingProviderError, match="incompatível"):
        provider.embed(["a"])


def test_lexical_query_uses_or_without_injecting_tsquery_syntax():
    assert lexical_query_text("Quais são os poderes da União?") == (
        "quais OR são OR poderes OR união"
    )
    assert lexical_query_text("art. 5º, igualdade") == "art OR igualdade"


def test_contextual_rerank_promotes_caput_from_strong_article_descendant():
    unrelated = _candidate("100", lexical=1, vector=1)
    descendant = replace(
        _candidate("5-desc", lexical=2, vector=2),
        identity_key="CF88/@root/ARTICLE:5/INCISO:XXIV",
    )
    caput = replace(
        _candidate("5", lexical=21),
        identity_key="CF88/@root/ARTICLE:5/CAPUT:@caput",
    )
    intervening = _candidate("200", lexical=3, vector=3)
    candidates = tuple(
        replace(item, rrf_score=0.03 - index / 1000)
        for index, item in enumerate((unrelated, descendant, intervening, caput))
    )
    ranked = contextual_caput_rerank(candidates, limit=4)
    assert (
        next(
            index
            for index, item in enumerate(ranked)
            if item.identity_key == caput.identity_key
        )
        < 3
    )
    assert ranked[1].contextual_score is not None


def test_contextual_rerank_does_not_promote_weak_or_unrelated_caput():
    descendant = replace(
        _candidate("60-desc", lexical=1, vector=1),
        identity_key="CF88/@root/ARTICLE:60/PARAGRAPH:1",
    )
    weak_caput = replace(
        _candidate("60", lexical=31),
        identity_key="CF88/@root/ARTICLE:60/CAPUT:@caput",
    )
    candidates = (
        replace(descendant, rrf_score=0.03),
        replace(weak_caput, rrf_score=0.01),
    )
    assert contextual_caput_rerank(candidates, limit=2)[1].contextual_score == 0.01
