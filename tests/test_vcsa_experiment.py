"""Controles estruturais do experimento VCSA, sem pipeline de produção."""

import dataclasses
import uuid
from types import SimpleNamespace

import pytest

from consultor_juridico.consultation.support_slots import build_support_slots
from evaluation.vcsa_87 import VCSAStatus, build_vcsa


class FakeSession:
    def __init__(self, elements):
        self.elements = {element.id: element for element in elements}

    def get(self, _model, identifier):
        return self.elements.get(identifier)


def _fixture(
    *,
    parent_type="INCISO",
    target_type="ALINEA",
    parent_text="não haverá penas:",
    target_text="de caráter perpétuo;",
    parent_status="CURRENT",
    target_status="CURRENT",
    parent_role="NORMATIVE",
    target_role="NORMATIVE",
):
    version_id = uuid.uuid4()
    act_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    target_id = uuid.uuid4()
    target_identity = "CF88/ARTICLE:5/INCISO:XLVII/ALINEA:B"
    parent = SimpleNamespace(
        id=parent_id,
        parent_id=None,
        legal_version_id=version_id,
        legal_act_id=act_id,
        element_type=parent_type,
        text_status=parent_status,
        content_role=parent_role,
        normalized_text=parent_text,
        source_locator={"block_index": 10},
        path="CF88/ARTICLE:5/INCISO:XLVII",
        legal_provision=SimpleNamespace(identity_key="CF88/ARTICLE:5/INCISO:XLVII"),
    )
    target = SimpleNamespace(
        id=target_id,
        parent_id=parent_id,
        legal_version_id=version_id,
        legal_act_id=act_id,
        element_type=target_type,
        text_status=target_status,
        content_role=target_role,
        normalized_text=target_text,
        source_locator={"block_index": 11},
        path=target_identity,
        legal_provision=SimpleNamespace(identity_key=target_identity),
    )
    item = SimpleNamespace(
        id=uuid.uuid4(),
        evidence_set_id=uuid.uuid4(),
        evidence_code="EV001",
        legal_element_id=target_id,
        chunk_id=uuid.uuid4(),
        text_snapshot=f"CF/88 | {target_identity}\n{target_text}",
        validation_metadata={
            "identity_key": target_identity,
            "parent_context": parent_text,
        },
    )
    evidence_set = SimpleNamespace(id=item.evidence_set_id, items=[item])
    session = FakeSession((parent, target))
    slot = build_support_slots(session, (item,))[0]
    return session, evidence_set, slot, parent, target


@pytest.mark.parametrize(
    ("parent_type", "target_type"),
    (
        ("CAPUT", "INCISO"),
        ("PARAGRAPH", "INCISO"),
        ("INCISO", "ALINEA"),
        ("ALINEA", "ITEM"),
    ),
)
def test_valid_direct_dependent_relations_are_verified(parent_type, target_type):
    session, evidence_set, slot, *_ = _fixture(
        parent_type=parent_type, target_type=target_type
    )
    assertion = build_vcsa(session, evidence_set, slot)
    assert assertion.status is VCSAStatus.VERIFIED
    assert assertion.reconstructed_text == "não haverá penas: de caráter perpétuo;"
    assert assertion.composition_hash


def test_parent_without_continuation_marker_is_not_applicable():
    session, evidence_set, slot, *_ = _fixture(parent_text="não haverá penas.")
    assert build_vcsa(session, evidence_set, slot).status is VCSAStatus.NOT_APPLICABLE


def test_sibling_pollution_and_more_than_two_fragments_are_rejected():
    session, evidence_set, slot, *_ = _fixture()
    polluted = dataclasses.replace(slot, fragments=(*slot.fragments, slot.target))
    assertion = build_vcsa(session, evidence_set, polluted)
    assert assertion.status is VCSAStatus.NOT_APPLICABLE


def test_non_direct_ancestor_is_unresolved():
    session, evidence_set, slot, _parent, target = _fixture()
    target.parent_id = uuid.uuid4()
    assert build_vcsa(session, evidence_set, slot).status is VCSAStatus.UNRESOLVED


def test_alternative_or_independent_child_is_not_applicable():
    session, evidence_set, slot, *_ = _fixture(
        target_text="Facultativos para analfabetos;"
    )
    assert build_vcsa(session, evidence_set, slot).status is VCSAStatus.NOT_APPLICABLE


@pytest.mark.parametrize(
    ("target_role", "target_status"),
    (
        ("EDITORIAL_NOTE", "NOT_APPLICABLE"),
        ("NORMATIVE", "HISTORICAL"),
        ("NORMATIVE", "REVOKED"),
    ),
)
def test_notes_historical_and_revoked_text_are_not_applicable(
    target_role, target_status
):
    session, evidence_set, slot, *_ = _fixture(
        target_role=target_role, target_status=target_status
    )
    assert build_vcsa(session, evidence_set, slot).status is VCSAStatus.NOT_APPLICABLE


def test_qualifier_and_punctuation_are_preserved_literally():
    session, evidence_set, slot, *_ = _fixture(
        target_text="de morte, salvo em caso de guerra declarada;"
    )
    assertion = build_vcsa(session, evidence_set, slot)
    assert assertion.status is VCSAStatus.VERIFIED
    assert assertion.reconstructed_text == (
        "não haverá penas: de morte, salvo em caso de guerra declarada;"
    )


@pytest.mark.parametrize("fragment_index", (0, 1))
def test_invalid_target_or_parent_provenance_is_unresolved(fragment_index):
    session, evidence_set, slot, *_ = _fixture()
    fragments = list(slot.fragments)
    fragments[fragment_index] = dataclasses.replace(
        fragments[fragment_index], sha256="0" * 64
    )
    invalid = dataclasses.replace(slot, fragments=tuple(fragments))
    assert build_vcsa(session, evidence_set, invalid).status is VCSAStatus.UNRESOLVED


def test_unrelated_slot_is_unresolved():
    session, evidence_set, slot, *_ = _fixture()
    unrelated = SimpleNamespace(id=evidence_set.id, items=[])
    assert build_vcsa(session, unrelated, slot).status is VCSAStatus.UNRESOLVED


def test_state_of_siege_shape_has_no_valid_composition():
    session, evidence_set, slot, *_ = _fixture(
        parent_type="ARTICLE", target_type="INCISO", parent_text="Art. 21."
    )
    assert build_vcsa(session, evidence_set, slot).status is VCSAStatus.NOT_APPLICABLE
