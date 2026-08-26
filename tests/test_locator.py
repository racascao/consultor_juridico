from types import SimpleNamespace

from consultor_juridico.consultation.locator import validate_response_locators
from consultor_juridico.consultation.types import GeneratedClaim, GeneratedResponse


def item(identity: str):
    return SimpleNamespace(
        evidence_code="EV001",
        text_snapshot="",
        validation_metadata={"identity_key": identity},
    )


def test_locator_matching_roman_numeral_passes() -> None:
    response = GeneratedResponse(
        "x",
        (
            GeneratedClaim(
                "C1", "Conforme art. 5º, inciso XLVII, alínea a.", ("EV001",)
            ),
        ),
    )
    assert validate_response_locators(
        response, (item("CF88/ARTICLE:5/INCISO:XLVII/ALINEA:A"),)
    ).valid


def test_locator_mismatch_fails_closed() -> None:
    response = GeneratedResponse(
        "x",
        (
            GeneratedClaim(
                "C1", "Conforme art. 5º, inciso XLVIII, alínea a.", ("EV001",)
            ),
        ),
    )
    result = validate_response_locators(
        response, (item("CF88/ARTICLE:5/INCISO:XLVII/ALINEA:A"),)
    )
    assert not result.valid
    assert "LOCATOR_MISMATCH" in result.errors[0]


def test_locator_absence_is_not_a_failure() -> None:
    response = GeneratedResponse(
        "x", (GeneratedClaim("C1", "A liberdade é protegida.", ("EV001",)),)
    )
    assert validate_response_locators(
        response, (item("CF88/ARTICLE:5/INCISO:VI"),)
    ).valid


def test_ebcg_exact_snapshot_allows_internal_normative_reference() -> None:
    text = "de morte, salvo em caso de guerra declarada, nos termos do art. 84, XIX;"
    evidence = item("CF88/ARTICLE:5/INCISO:XLVII/ALINEA:A")
    evidence.text_snapshot = text
    response = GeneratedResponse("x", (GeneratedClaim("C1", text, ("EV001",)),))

    assert validate_response_locators(
        response, (evidence,), generation_mode="EBCG_V2"
    ).valid


def test_non_ebcg_conflicting_locator_remains_rejected() -> None:
    text = "de morte, salvo em caso de guerra declarada, nos termos do art. 84, XIX;"
    evidence = item("CF88/ARTICLE:5/INCISO:XLVII/ALINEA:A")
    evidence.text_snapshot = text
    response = GeneratedResponse("x", (GeneratedClaim("C1", text, ("EV001",)),))

    assert not validate_response_locators(response, (evidence,)).valid
