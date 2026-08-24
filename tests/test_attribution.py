"""Testes do protótipo de atribuição determinística pós-geração."""

from types import SimpleNamespace

from consultor_juridico.consultation.attribution import deterministically_attribute
from consultor_juridico.consultation.types import GeneratedClaim, GeneratedResponse


def _item(code: str, text: str, parent: str | None = None):
    return SimpleNamespace(
        evidence_code=code,
        text_snapshot=text,
        validation_metadata={"parent_context": parent},
    )


def _response(text: str, evidence: tuple[str, ...]) -> GeneratedResponse:
    return GeneratedResponse(
        "resposta",
        (GeneratedClaim("C1", text, evidence),),
    )


def test_reassigns_claim_to_only_directly_supporting_evidence():
    result = deterministically_attribute(
        _response("O voto é obrigatório para maiores de dezoito anos.", ("EV001",)),
        (
            _item("EV001", "o voto direto e secreto"),
            _item(
                "EV002",
                "obrigatórios para os maiores de dezoito anos;",
                "O alistamento eleitoral e o voto são:",
            ),
        ),
    )
    assert not result.abstained
    assert result.response.claims[0].evidence_codes == ("EV002",)


def test_prefers_distinctive_term_over_thematically_close_evidence():
    result = deterministically_attribute(
        _response("Não haverá prisão perpétua.", ("EV001",)),
        (
            _item("EV001", "a prisão ilegal será imediatamente relaxada"),
            _item("EV002", "de caráter perpétuo;", "não haverá penas:"),
        ),
    )
    assert not result.abstained
    assert result.response.claims[0].evidence_codes == ("EV002",)


def test_morphological_prefix_distinguishes_repudio_from_thematic_match():
    result = deterministically_attribute(
        _response("O racismo é repudiado constitucionalmente.", ("EV001",)),
        (
            _item("EV001", "repúdio ao terrorismo e ao racismo"),
            _item("EV002", "a prática do racismo constitui crime"),
        ),
    )
    assert not result.abstained
    assert "EV001" in result.response.claims[0].evidence_codes


def test_composed_claim_can_use_two_evidence_items():
    result = deterministically_attribute(
        _response("A regra A vale e a exceção B também existe.", ("EV001",)),
        (
            _item("EV001", "a regra A vale"),
            _item("EV002", "a exceção B também existe"),
        ),
    )
    assert not result.abstained
    assert result.response.claims[0].evidence_codes == ("EV001", "EV002")


def test_fails_closed_when_no_evidence_is_sufficient():
    result = deterministically_attribute(
        _response("A idade mínima é trinta e cinco anos.", ("EV001",)),
        (_item("EV001", "o voto é secreto"),),
    )
    assert result.abstained
    assert result.response.claims == ()


def test_abstention_is_preserved():
    response = GeneratedResponse("não sei", (), abstain=True)
    result = deterministically_attribute(response, (_item("EV001", "texto"),))
    assert result.response == response
    assert not result.abstained
