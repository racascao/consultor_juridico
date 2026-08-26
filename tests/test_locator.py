from types import SimpleNamespace

from consultor_juridico.consultation.locator import validate_response_locators
from consultor_juridico.consultation.types import GeneratedClaim, GeneratedResponse


def item(identity: str):
    return SimpleNamespace(
        evidence_code="EV001", validation_metadata={"identity_key": identity}
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
