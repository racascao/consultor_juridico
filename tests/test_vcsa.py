from consultor_juridico.consultation.vcsa import StructuralFragment, compose


def frag(id, typ, text, parent=None, **kw):
    return StructuralFragment(
        id,
        id,
        text,
        typ,
        parent,
        kw.get("act", "CF"),
        kw.get("version", "V"),
        kw.get("status", "CURRENT"),
        kw.get("role", "NORMATIVE"),
    )


def test_direct_parent_colon_child_composes_deterministically():
    parent = frag("p", "INCISO", "não haverá penas:")
    child = frag("c", "ALINEA", "b) de caráter perpétuo", parent="p")
    first = compose(parent, child)
    second = compose(parent, child)
    assert first.applicable and first.text == "não haverá penas: b) de caráter perpétuo"
    assert first.composition_hash == second.composition_hash


def test_all_allowed_structural_relations_are_supported():
    cases = [("CAPUT", "INCISO"), ("PARAGRAPH", "INCISO"), ("ALINEA", "ITEM")]
    for index, (parent_type, child_type) in enumerate(cases):
        parent = frag(f"p{index}", parent_type, "condições:")
        child = frag(f"c{index}", child_type, "conteúdo", parent=f"p{index}")
        assert compose(parent, child).applicable


def test_sibling_cross_scope_and_non_normative_rejected():
    parent = frag("p", "INCISO", "condições:")
    assert not compose(parent, frag("c", "INCISO", "II", parent="other")).applicable
    assert not compose(
        parent, frag("c", "ALINEA", "a)", parent="p", act="ADCT")
    ).applicable
    assert not compose(
        parent, frag("c", "ALINEA", "a)", parent="p", role="NOTE")
    ).applicable


def test_non_current_and_non_colon_parent_rejected():
    assert not compose(
        frag("p", "INCISO", "regra", status="HISTORICAL"),
        frag("c", "ALINEA", "a)", parent="p"),
    ).applicable
    assert not compose(
        frag("p", "INCISO", "regra"), frag("c", "ALINEA", "a)", parent="p")
    ).applicable


def test_result_is_immutable():
    result = compose(
        frag("p", "INCISO", "regra:"), frag("c", "ALINEA", "a)", parent="p")
    )
    assert result.applicable
    try:
        result.text = "alterado"
    except AttributeError:
        pass
    else:
        raise AssertionError("VCSA result must be immutable")
