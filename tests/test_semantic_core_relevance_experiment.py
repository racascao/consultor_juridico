"""Testes puros do experimento offline Semantic Core Relevance."""

from __future__ import annotations

import json

from evaluation.semantic_core_relevance_88 import (
    Decision,
    EmbeddingRelevanceJudge,
    EmbeddingThresholds,
    LLMRelevanceJudge,
    RelevanceStatus,
    _cosine_similarity,
    controls,
    derive_embedding_thresholds,
)


class FakeEmbeddingProvider:
    def __init__(self, vectors):
        self.vectors = vectors

    def embed(self, texts):
        return tuple(self.vectors[text] for text in texts)


def test_thresholds_are_derived_only_from_general_controls():
    fixtures = controls()
    scores = {
        fixture.name: 0.9 if fixture.expected is RelevanceStatus.RELEVANT else 0.2
        for fixture in fixtures
    }
    thresholds = derive_embedding_thresholds(scores, fixtures)

    assert thresholds.separable is True
    assert thresholds.irrelevant_at_or_below == 0.2
    assert thresholds.relevant_at_or_above == 0.9


def test_overlapping_control_distribution_is_fail_closed():
    fixtures = controls()
    scores = {
        fixture.name: 0.5 if fixture.expected is RelevanceStatus.RELEVANT else 0.6
        for fixture in fixtures
    }
    thresholds = derive_embedding_thresholds(scores, fixtures)
    judge = EmbeddingRelevanceJudge(
        FakeEmbeddingProvider({"q": (1.0, 0.0), "a": (1.0, 0.0)}), thresholds
    )

    assert thresholds.separable is False
    assert judge.evaluate("q", "a").status is RelevanceStatus.UNRESOLVED


def test_embedding_judge_uses_frozen_uncertainty_zone():
    thresholds = EmbeddingThresholds(0.3, 0.8, True, "test")
    provider = FakeEmbeddingProvider(
        {
            "low-q": (1.0, 0.0),
            "low-a": (0.0, 1.0),
            "middle-q": (1.0, 0.0),
            "middle-a": (0.5, 0.8660254),
            "high-q": (1.0, 0.0),
            "high-a": (1.0, 0.0),
        }
    )
    judge = EmbeddingRelevanceJudge(provider, thresholds)

    assert judge.evaluate("low-q", "low-a").status is RelevanceStatus.IRRELEVANT
    assert judge.evaluate("middle-q", "middle-a").status is RelevanceStatus.UNRESOLVED
    assert judge.evaluate("high-q", "high-a").status is RelevanceStatus.RELEVANT


def test_cosine_rejects_incompatible_vectors():
    try:
        _cosine_similarity((1.0,), (1.0, 2.0))
    except ValueError as exc:
        assert "incompatíveis" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Vetores incompatíveis devem falhar.")


def test_llm_judge_contract_is_minimal_and_fail_closed(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "message": {
                    "content": json.dumps({"status": "RELEVANT", "reason": "direta"})
                }
            }

    def fake_post(url, *, json, timeout):
        captured.update({"url": url, "payload": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("evaluation.semantic_core_relevance_88.httpx.post", fake_post)
    decision = LLMRelevanceJudge(
        base_url="http://local", model="local", timeout=3
    ).evaluate("pergunta", "assertion")

    assert decision == Decision(
        RelevanceStatus.RELEVANT,
        "direta",
        decision.latency_ms,
        None,
        {"message": {"content": '{"status": "RELEVANT", "reason": "direta"}'}},
    )
    assert captured["payload"]["messages"][1]["content"] == (
        "QUERY:\npergunta\n\nCORE ASSERTION NORMATIVA VERIFICADA:\nassertion\n\n"
        "A assertion responde materialmente à proposição principal da query?"
    )
    assert "expected" not in str(captured["payload"]).casefold()
