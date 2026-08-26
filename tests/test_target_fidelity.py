from consultor_juridico.consultation.core_evidence import select_core_evidence_v2
from consultor_juridico.evaluation.target_fidelity import assess_target_fidelity
from consultor_juridico.evaluation.types import EvaluationCase
from evaluation.audit_core_evidence_policy import (
    audit_core_evidence_policy,
)
from evaluation.audit_target_fidelity import audit_artifact


def _case(*, acceptable: tuple[str, ...] = ()) -> EvaluationCase:
    return EvaluationCase(
        id="case",
        category="test",
        question="pergunta",
        expected_act="CF/88",
        expected_provisions=("CF88/ARTICLE:5/INCISO:XLVII/ALINEA:B",),
        acceptable_provisions=acceptable,
        expect_answer=True,
        required_concepts=(),
        rationale="teste",
        tags=(),
    )


def _artifact(*, identity: str, outcome: str = "ANSWERED") -> dict:
    return {
        "results": [
            {
                "case_id": "case",
                "result": {"outcome": outcome, "classification": "CORRECT_ANSWER"},
                "generation": {
                    "claims": [{"ev": ["EV001"]}],
                    "citations": [
                        {
                            "code": "EV001",
                            "label": f"CF/88 (identidade: {identity})",
                        }
                    ],
                },
                "evidence_selection": {
                    "diagnostics": [
                        {
                            "identity_key": identity,
                            "query_coverage": 0.5,
                            "marginal_coverage": 0.0,
                            "base_relevance": 0.8,
                            "final_score": 0.8,
                            "selected_position": 1,
                        }
                    ]
                },
            }
        ]
    }


def test_target_fidelity_accepts_expected_or_acceptable_identity() -> None:
    expected = _case(acceptable=("CF88/ARTICLE:5/INCISO:XLVII",))

    assert assess_target_fidelity(expected, ("CF88/ARTICLE:5/INCISO:XLVII",)).passed
    assert assess_target_fidelity(
        expected, ("CF88/ARTICLE:5/INCISO:XLVII/ALINEA:B",)
    ).passed


def test_target_fidelity_rejects_related_but_off_target_identity() -> None:
    result = assess_target_fidelity(_case(), ("CF88/ARTICLE:5/INCISO:LXII",))

    assert not result.passed
    assert result.reason == "NO_CITED_EVIDENCE_IN_ALLOWED_TARGETS"


def test_audit_marks_answered_off_target_as_wrong_target() -> None:
    audited = audit_artifact(
        _artifact(identity="CF88/ARTICLE:5/INCISO:LXII"), {"case": _case()}
    )

    assert audited["correct_answers"] == 0
    assert audited["wrong_targets"] == 1
    assert audited["results"][0]["failure_stage"] == "TARGET_FIDELITY"


def test_audit_keeps_answered_allowed_target_correct() -> None:
    audited = audit_artifact(
        _artifact(identity="CF88/ARTICLE:5/INCISO:XLVII/ALINEA:B"),
        {"case": _case()},
    )

    assert audited["correct_answers"] == 1
    assert audited["wrong_targets"] == 0


def test_policy_a_and_b_are_evaluated_without_gold_data_in_selection_logic() -> None:
    artifact = _artifact(identity="CF88/ARTICLE:5/INCISO:LXII")
    artifact["results"][0]["evidence_selection"]["diagnostics"].append(
        {
            "identity_key": "CF88/ARTICLE:5/INCISO:XLVII/ALINEA:B",
            "query_coverage": 0.5,
            "marginal_coverage": 0.5,
            "base_relevance": 0.6,
            "final_score": 0.6,
            "selected_position": 2,
        }
    )

    audited = audit_core_evidence_policy(artifact, {"case": _case()})

    assert audited["core_evidence_v1_target_hits"] == 0
    assert audited["policy_a_target_hits"] == 0
    assert audited["policy_b_target_hits"] == 1


def test_core_evidence_policy_has_no_dataset_or_target_parameter() -> None:
    assert tuple(select_core_evidence_v2.__annotations__) == (
        "evidence_items",
        "return",
    )
