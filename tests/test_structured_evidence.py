from types import SimpleNamespace
from uuid import UUID

from consultor_juridico.consultation.structured_evidence import (
    StructuredSourcePart,
    build_structured_evidence,
)


def part(number, kind, text, order, relation="ANCESTOR", label=None):
    return StructuredSourcePart(
        UUID(int=number),
        kind,
        label,
        f"CF88/{kind}:{label or number}",
        text,
        relation,
        order,
    )


def item(snapshot="fragmento", parent=None):
    return SimpleNamespace(
        evidence_code="EV001",
        text_snapshot=snapshot,
        validation_metadata={
            "identity_key": "CF88/ARTICLE:1",
            "parent_context": parent,
        },
    )


def test_independent_element_preserves_snapshot_and_provenance():
    target = part(1, "CAPUT", "Texto normativo completo.", 2, "TARGET")
    unit = build_structured_evidence(item("Texto normativo completo."), target)
    assert unit.original_snapshot == "Texto normativo completo."
    assert unit.source_element_ids == (target.element_id,)
    assert "Texto normativo completo." in unit.structured_text


def test_ancestor_negation_and_alinea_are_reconstructed_without_paraphrase():
    article = part(1, "ARTICLE", "Art. 5º", 1, label="5")
    inciso = part(2, "INCISO", "não haverá penas:", 2, label="XLVII")
    target = part(3, "ALINEA", "de caráter perpétuo;", 3, "TARGET", "b")
    unit = build_structured_evidence(
        item("de caráter perpétuo;"), target, ancestors=(article, inciso)
    )
    assert "não haverá penas:" in unit.structured_text
    assert "de caráter perpétuo;" in unit.structured_text
    assert unit.hierarchy == ("ARTICLE 5", "INCISO XLVII", "ALINEA b")


def test_enumeration_includes_siblings_in_document_order():
    parent = part(1, "CAPUT", "O alistamento e o voto são:", 1)
    target = part(
        3, "INCISO", "obrigatórios para maiores de dezoito anos;", 3, "TARGET", "I"
    )
    sibling = part(4, "INCISO", "facultativos para analfabetos;", 4, "SIBLING", "II")
    unit = build_structured_evidence(
        item(), target, ancestors=(parent,), siblings=(sibling,)
    )
    assert unit.structured_text.index("obrigatórios") < unit.structured_text.index(
        "facultativos"
    )
    assert unit.source_element_ids == (
        parent.element_id,
        target.element_id,
        sibling.element_id,
    )


def test_exception_and_parent_context_are_preserved_factually():
    parent = part(1, "CAPUT", "A regra aplica-se, salvo em emergência:", 1)
    target = part(2, "INCISO", "a medida será adotada;", 2, "TARGET", "I")
    unit = build_structured_evidence(
        item(parent="contexto original"), target, ancestors=(parent,)
    )
    assert "salvo em emergência" in unit.structured_text
    assert unit.original_parent_context == "contexto original"


def test_same_inputs_are_deterministic_and_do_not_mutate_snapshot():
    evidence = item("snapshot imutável")
    target = part(1, "CAPUT", "snapshot imutável", 1, "TARGET")
    first = build_structured_evidence(evidence, target)
    second = build_structured_evidence(evidence, target)
    assert first == second
    assert evidence.text_snapshot == "snapshot imutável"
    assert first.sha256 == second.sha256
