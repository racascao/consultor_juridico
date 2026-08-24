"""Testes do experimento offline de adequação Query -> Claim."""

from evaluation.relevance_core_86 import (
    AnswerRole,
    RelevanceStatus,
    _run_controls,
    evaluate_claim_relevance,
)


def test_controls_are_deterministic_and_pass():
    assert all(control["passed"] for control in _run_controls())
    assert _run_controls() == _run_controls()


def test_query_coverage_uses_authorized_fragments_without_synonyms():
    decision = evaluate_claim_relevance(
        "liberdade religiosa",
        "A liberdade de consciência e de crença é inviolável.",
        ("É assegurado o livre exercício dos cultos religiosos.",),
    )
    assert decision.status is RelevanceStatus.RELEVANT
    assert decision.role is AnswerRole.CENTRAL


def test_ungrounded_capitalized_actor_is_fail_closed():
    decision = evaluate_claim_relevance(
        "estado de sítio",
        "O Congresso pode decretar o estado de sítio.",
        ("decretar o estado de sítio.",),
    )
    assert decision.status is RelevanceStatus.UNRESOLVED
    assert decision.role is AnswerRole.UNRESOLVED


def test_subordinate_focus_is_auxiliary_not_core():
    decision = evaluate_claim_relevance(
        "estado de sítio",
        "Após o término do estado de sítio, haverá relatório.",
        ("Após o término do estado de sítio, haverá relatório.",),
    )
    assert decision.status is RelevanceStatus.RELEVANT
    assert decision.role is AnswerRole.AUXILIARY
