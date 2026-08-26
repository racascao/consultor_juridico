from types import SimpleNamespace

from consultor_juridico.consultation.materialization import materialize, vcsa_metadata
from consultor_juridico.consultation.polarity import PolarityStatus, validate_polarity
from consultor_juridico.consultation.types import GeneratedClaim


def test_vcsa_effective_text_is_literal_and_snapshot_is_immutable():
    parent = SimpleNamespace(
        identity="CF/INCISO:XLVII",
        element_id="parent",
        text="não haverá penas:",
        legal_act_id="act",
        legal_version_id="version",
    )
    target = SimpleNamespace(
        identity="CF/INCISO:XLVII/ALINEA:B",
        element_id="child",
        text="de caráter perpétuo;",
        legal_act_id="act",
        legal_version_id="version",
    )
    item = SimpleNamespace(
        evidence_code="EV001",
        text_snapshot="de caráter perpétuo;",
        validation_metadata={
            "vcsa": vcsa_metadata(
                target=target,
                parent=parent,
                effective_text="não haverá penas: de caráter perpétuo;",
            )
        },
    )
    result = materialize(item)
    assert result.text_snapshot == "não haverá penas: de caráter perpétuo;"
    assert item.text_snapshot == "de caráter perpétuo;"
    assert materialize(item).effective_text == result.effective_text


def test_vcsa_effective_text_reaches_polarity_guard():
    item = SimpleNamespace(
        evidence_code="EV001",
        text_snapshot="de caráter perpétuo;",
        validation_metadata={
            "vcsa": {"effective_text": "não haverá penas: de caráter perpétuo;"}
        },
    )
    result = validate_polarity(
        GeneratedClaim(
            "C1", "É permitido aplicar penas de caráter perpétuo.", ("EV001",)
        ),
        (materialize(item),),
    )
    assert result.status is PolarityStatus.CONTRADICTED


def test_non_vcsa_materialization_preserves_legacy_context():
    item = SimpleNamespace(
        evidence_code="EV001",
        text_snapshot="filho",
        validation_metadata={"parent_context": "pai:"},
    )
    assert materialize(item).effective_text == "filho pai:"
