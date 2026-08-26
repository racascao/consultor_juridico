from consultor_juridico.consultation.atomic import AtomicClaim, accept_atomic_claims


def claim(**overrides):
    values = {"code": "C1", "text": "core", "on_target": True, "core_answer": True}
    values.update(overrides)
    return AtomicClaim(**values)


def test_core_survives_lateral_invalid_claim():
    result = accept_atomic_claims(
        (claim(), claim(code="C2", on_target=False, attributed=False))
    )
    assert not result.abstain and [c.code for c in result.accepted] == ["C1"]


def test_material_exception_forces_abstention():
    result = accept_atomic_claims(
        (claim(), claim(code="C2", material_dependency=True, semantic_valid=False))
    )
    assert result.abstain and not result.accepted


def test_core_locator_or_polarity_failure_abstains():
    assert accept_atomic_claims((claim(locator_valid=False),)).abstain
    assert accept_atomic_claims((claim(polarity_valid=False),)).abstain


def test_only_auxiliary_claim_abstains():
    result = accept_atomic_claims((claim(on_target=False, core_answer=False),))
    assert result.abstain
