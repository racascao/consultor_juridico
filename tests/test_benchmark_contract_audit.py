from types import SimpleNamespace

from evaluation.audit_benchmark_contract import audit_artifact


def _case(**kwargs):
    defaults = dict(
        id="case",
        question="tema",
        expect_answer=True,
        expected_provisions=("CF88/A",),
        acceptable_provisions=(),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _record(**kwargs):
    defaults = {
        "case_id": "case",
        "result": {"classification": "CORRECT_ANSWER", "failure_stage": None},
        "retrieval": {"hit": True, "ranks": {}},
        "evidence_selection": {"items": [], "diagnostics": []},
        "generation": {
            "claims": [],
            "citations": [],
            "attribution": [],
            "validation_errors": [],
        },
        "target_fidelity": {"passed": True},
    }
    defaults.update(kwargs)
    return defaults


def _audit(record, case=None, structural=None):
    return audit_artifact({"results": [record]}, {"case": case or _case()}, structural)[
        "cases"
    ][0]


def test_classifies_pass_and_expected_abstention():
    assert _audit(_record())["primary_attribution"] == "PASS"
    record = _record(
        result={"classification": "CORRECT_ABSTENTION", "failure_stage": None}
    )
    assert (
        _audit(record, _case(expect_answer=False, expected_provisions=()))[
            "primary_attribution"
        ]
        == "EXPECTED_ABSTENTION"
    )


def test_classifies_retrieval_miss_when_targets_are_valid():
    record = _record(
        result={"classification": "WRONG_TARGET", "failure_stage": "TARGET_FIDELITY"},
        retrieval={"hit": False, "ranks": {}},
    )
    assert (
        _audit(record, structural={"CF88/A": {}})["primary_attribution"]
        == "RETRIEVAL_MISS"
    )


def test_classifies_selection_error_when_target_is_selected_but_not_core():
    record = _record(
        result={"classification": "WRONG_TARGET", "failure_stage": "TARGET_FIDELITY"},
        evidence_selection={
            "items": [{"identity_key": "CF88/A"}, {"identity_key": "CF88/B"}],
            "diagnostics": [],
        },
        generation={
            "claims": [{"ev": ["EV002"]}],
            "citations": [{"code": "EV002", "label": "(identidade: CF88/B)"}],
            "attribution": [{"evidence_codes": ["EV002"]}],
            "validation_errors": [],
        },
    )
    assert _audit(record)["primary_attribution"] == "CORE_EVIDENCE_SELECTION_ERROR"


def test_classifies_structural_context_and_stage_taxonomy_error():
    record = _record(
        result={
            "classification": "FALSE_ABSTENTION",
            "failure_stage": "GENERATOR_ABSTENTION",
        },
        evidence_selection={"items": [{"identity_key": "CF88/A"}], "diagnostics": []},
        generation={
            "claims": [],
            "citations": [],
            "attribution": [{"evidence_codes": ["EV001"]}],
            "validation_errors": ["UNRESOLVED — polaridade"],
        },
    )
    result = _audit(record)
    assert result["primary_attribution"] == "STRUCTURAL_CONTEXT_REQUIRED_FOR_VALIDATION"
    assert result["recommended_failure_stage"] == "POLARITY_VALIDATION"


def test_classifies_missing_leaf_with_selected_ancestor_as_dataset_error():
    record = _record(
        result={"classification": "WRONG_TARGET", "failure_stage": "TARGET_FIDELITY"},
        evidence_selection={
            "items": [{"identity_key": "CF88/ARTICLE:1/INCISO:I"}],
            "diagnostics": [],
        },
    )
    case = _case(expected_provisions=("CF88/ARTICLE:1/INCISO:I/ALINEA:A",))
    assert (
        _audit(record, case, {"CF88/ARTICLE:1/INCISO:I": {}})["primary_attribution"]
        == "DATASET_TARGET_ERROR"
    )


def test_classifies_ambiguity_when_allowed_and_other_full_coverage_are_selected():
    record = _record(
        result={"classification": "WRONG_TARGET", "failure_stage": "TARGET_FIDELITY"},
        evidence_selection={
            "items": [{"identity_key": "CF88/A"}, {"identity_key": "CF88/B"}],
            "diagnostics": [
                {"identity_key": "CF88/A", "query_coverage": 1.0},
                {"identity_key": "CF88/B", "query_coverage": 1.0},
            ],
        },
    )
    result = _audit(record)
    assert result["primary_attribution"] == "QUERY_AMBIGUITY"
    assert "ACCEPTABLE_TARGETS_INCOMPLETE" in result["secondary_attributions"]


def test_classifies_inconclusive_without_structured_signal():
    record = _record(
        result={"classification": "TECHNICAL_FAILURE", "failure_stage": None}
    )
    assert _audit(record)["primary_attribution"] == "INCONCLUSIVE"
