from types import SimpleNamespace

from consultor_juridico.retrieval.structural_budget import apply_structural_reserve


def promotion(identity, score, source="STRUCTURAL_EXPANSION"):
    return SimpleNamespace(
        candidate=SimpleNamespace(identity_key=identity),
        retrieval_source=source,
        structural_score=score,
        structural_child_identity=identity,
    )


def test_reserve_preserves_primary_and_uses_deterministic_order():
    primary = (SimpleNamespace(identity_key="P1"), SimpleNamespace(identity_key="P2"))
    result = apply_structural_reserve(
        primary, (promotion("B", 0.4), promotion("A", 0.4)), reserve_k=1
    )
    assert tuple(x.identity_key for x in result.primary) == ("P1", "P2")
    assert tuple(x.identity_key for x in result.reserve) == ("A",)


def test_reserve_deduplicates_and_rejects_non_structural():
    primary = (SimpleNamespace(identity_key="P1"),)
    result = apply_structural_reserve(
        primary,
        (promotion("P1", 0.9), promotion("X", 0.8, "OTHER"), promotion("Y", 0.7)),
        reserve_k=2,
    )
    assert tuple(x.identity_key for x in result.reserve) == ("Y",)
