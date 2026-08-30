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
    query_coverage: float = 1.0,
    marginal_coverage: float = 0.0,
    base_relevance: float = 1.0,
    selected_position: int = 1,
):
    return SimpleNamespace(
        evidence_code=code,
        text_snapshot=text,
        is_validated=validated,
        validation_metadata={
            "parent_context": parent_context,
            "identity_key": "CF88/@root/ARTICLE:5/INCISO:XLVII/ALINEA:B",
            "query_coverage": query_coverage,
            "marginal_coverage": marginal_coverage,
            "base_relevance": base_relevance,
            "selected_position": selected_position,
        },
    )


def _generator() -> EvidenceBoundControlledGenerator:
    return EvidenceBoundControlledGenerator()


def test_ebcg_generates_one_exact_core_claim_from_best_selected_evidence():
    evidence = _item("EV001", "de caráter perpétuo;")

    result = _generator().generate("prisão perpétua", (evidence,))

    assert not result.abstain
    assert result.answer == evidence.text_snapshot
    assert result.claims == (result.claims[0],)
    assert result.claims[0].claim_code == "C1"
    assert result.claims[0].text == evidence.text_snapshot
    assert result.claims[0].evidence_codes == ("EV001",)


def test_ebcg_prioritizes_existing_selection_signals_without_ev001_special_case():
    core = _item("EV002", "Texto central.", query_coverage=1.0, selected_position=2)
    result = _generator().generate(
        "Pergunta",
        (
            _item("EV001", "Texto lateral.", query_coverage=0.5),
            core,
            _item("EV003", "Outro.", query_coverage=0.5, selected_position=3),
        ),
    )

    assert len(result.claims) == 1
    assert result.claims[0].evidence_codes == ("EV002",)


def test_ebcg_never_composes_parent_context():
    core = _item("EV001", "de caráter perpétuo;", parent_context="não haverá penas:")

    result = _generator().generate("prisão perpétua", (core,))

    assert result.claims[0].text == "de caráter perpétuo;"
    assert "não haverá penas" not in result.claims[0].text


def test_ebcg_abstains_without_valid_or_diagnostic_core_evidence():
    for evidence in (
        (),
        (
            SimpleNamespace(
                evidence_code="EV002",
                text_snapshot="Texto.",
                is_validated=True,
                validation_metadata={},
            ),
        ),
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
    locator = validate_response_locators(
        attribution.response, (core,), generation_mode="EBCG_V2"
    )
    polarity = validate_response_polarity(attribution.response, (core,))

    assert not attribution.abstained
    assert attribution.response.claims[0].evidence_codes == ("EV001",)
    assert locator.valid
    assert polarity.results[0].is_safe


def test_ebcg_uses_marginal_coverage_before_base_relevance():
    first = _item("EV001", "Primeiro.", query_coverage=0.5, base_relevance=0.9)
    second = _item(
        "EV002",
        "Complementar.",
        query_coverage=0.5,
        marginal_coverage=0.5,
        base_relevance=0.6,
        selected_position=2,
    )

    result = _generator().generate("Pergunta", (first, second))

    assert result.claims[0].evidence_codes == ("EV002",)


def test_ebcg_breaks_ties_by_base_relevance_then_selected_position_then_code():
    lower_relevance = _item("EV001", "Menor.", base_relevance=0.7)
    higher_relevance = _item("EV002", "Maior.", base_relevance=0.8, selected_position=2)
    assert _generator().generate(
        "Pergunta", (lower_relevance, higher_relevance)
    ).claims[0].evidence_codes == ("EV002",)

    later = _item("EV002", "Posterior.", selected_position=2)
    earlier = _item("EV003", "Anterior.", selected_position=1)
    assert _generator().generate("Pergunta", (later, earlier)).claims[
        0
    ].evidence_codes == ("EV003",)

    higher_code = _item("EV002", "Segundo.")
    lower_code = _item("EV001", "Primeiro.")
    assert _generator().generate("Pergunta", (higher_code, lower_code)).claims[
        0
    ].evidence_codes == ("EV001",)
