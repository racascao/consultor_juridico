from types import SimpleNamespace

import httpx

from consultor_juridico.consultation.attribution import deterministically_attribute
from consultor_juridico.consultation.llm import EvidenceBoundControlledGenerator
from consultor_juridico.consultation.locator import validate_response_locators
from consultor_juridico.consultation.polarity import validate_response_polarity


def _item(
    code: str,
    text: str,
    *,
    validated: bool = True,
    parent_context: str | None = None,
):
    return SimpleNamespace(
        evidence_code=code,
        text_snapshot=text,
        is_validated=validated,
        validation_metadata={
            "parent_context": parent_context,
            "identity_key": "CF88/@root/ARTICLE:5/INCISO:XLVII/ALINEA:B",
        },
    )


def _generator() -> EvidenceBoundControlledGenerator:
    return EvidenceBoundControlledGenerator()


def test_ebcg_generates_one_exact_core_claim_from_ev001():
    evidence = _item("EV001", "de caráter perpétuo;")

    result = _generator().generate("prisão perpétua", (evidence,))

    assert not result.abstain
    assert result.answer == evidence.text_snapshot
    assert result.claims == (result.claims[0],)
    assert result.claims[0].claim_code == "C1"
    assert result.claims[0].text == evidence.text_snapshot
    assert result.claims[0].evidence_codes == ("EV001",)


def test_ebcg_ignores_additional_evidence_items():
    core = _item("EV001", "Texto central.")
    result = _generator().generate(
        "Pergunta", (core, _item("EV002", "Texto lateral."), _item("EV003", "Outro."))
    )

    assert len(result.claims) == 1
    assert result.claims[0].evidence_codes == ("EV001",)


def test_ebcg_never_composes_parent_context():
    core = _item("EV001", "de caráter perpétuo;", parent_context="não haverá penas:")

    result = _generator().generate("prisão perpétua", (core,))

    assert result.claims[0].text == "de caráter perpétuo;"
    assert "não haverá penas" not in result.claims[0].text


def test_ebcg_abstains_without_valid_ev001():
    for evidence in (
        (),
        (_item("EV002", "Texto."),),
        (_item("EV001", "", validated=True),),
        (_item("EV001", "  \t", validated=True),),
        (_item("EV001", "Texto.", validated=False),),
    ):
        result = _generator().generate("Pergunta", evidence)
        assert result.abstain
        assert result.claims == ()


def test_ebcg_does_not_call_ollama(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Ollama")),
    )

    result = _generator().generate("Pergunta", (_item("EV001", "Texto."),))

    assert result.claims[0].text == "Texto."


def test_ebcg_output_remains_compatible_with_attribution_locator_and_polarity():
    core = _item("EV001", "não haverá penas de caráter perpétuo;")
    response = _generator().generate("prisão perpétua", (core,))

    attribution = deterministically_attribute(response, (core,))
    locator = validate_response_locators(attribution.response, (core,))
    polarity = validate_response_polarity(attribution.response, (core,))

    assert not attribution.abstained
    assert attribution.response.claims[0].evidence_codes == ("EV001",)
    assert locator.valid
    assert polarity.results[0].is_safe
