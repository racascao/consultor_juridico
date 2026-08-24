"""Fronteiras determinísticas da Evidence-Bound Atomic Generation."""

import dataclasses
import uuid
from types import SimpleNamespace

import pytest

from consultor_juridico.consultation.completeness import (
    QueryScope,
    classify_query_scope,
)
from consultor_juridico.consultation.errors import LLMResponseError
from consultor_juridico.consultation.evidence_bound import (
    run_evidence_bound_downstream,
)
from consultor_juridico.consultation.llm import (
    build_scoped_prompt,
    parse_scoped_generation,
)
from consultor_juridico.consultation.qualifiers import validate_material_qualifiers
from consultor_juridico.consultation.support_slots import (
    SupportFragmentRole,
    SupportSlotError,
    build_support_slots,
    support_slot_manifest,
    validate_support_slot,
)
from consultor_juridico.consultation.types import (
    ClaimSupport,
    ConsultationOutcome,
    ScopedGeneration,
    SemanticSupportReport,
    SemanticSupportStatus,
    ValidationReport,
)
from consultor_juridico.models import LegalElement
from evaluation.evidence_bound_12 import (
    _grounded_assessment,
    _structurally_related,
)


class FakeSession:
    def __init__(self, elements):
        self.elements = {element.id: element for element in elements}

    def get(self, model, identifier):
        assert model is LegalElement
        return self.elements.get(identifier)


def _fixture(*, parent_text="não haverá medidas", recorded_parent=None):
    set_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    target_id = uuid.uuid4()
    parent = SimpleNamespace(
        id=parent_id,
        parent_id=None,
        legal_version_id=uuid.uuid4(),
        normalized_text=parent_text,
        source_locator={"block_index": 10},
        path="/parent",
        legal_provision=SimpleNamespace(identity_key="CF88/PARENT"),
    )
    target = SimpleNamespace(
        id=target_id,
        parent_id=parent_id,
        legal_version_id=parent.legal_version_id,
        normalized_text="medida permitida salvo condição",
        source_locator={"block_index": 11},
        path="/target",
        legal_provision=SimpleNamespace(identity_key="CF88/TARGET"),
    )
    item = SimpleNamespace(
        id=uuid.uuid4(),
        evidence_set_id=set_id,
        evidence_code="EV001",
        legal_element_id=target_id,
        chunk_id=uuid.uuid4(),
        text_snapshot="A medida é permitida, salvo condição expressa.",
        validation_metadata={
            "identity_key": "CF88/TARGET",
            "parent_context": (
                parent_text if recorded_parent is None else recorded_parent
            ),
        },
    )
    evidence_set = SimpleNamespace(id=set_id, items=[item])
    return FakeSession((parent, target)), evidence_set, item, parent, target


def test_one_item_builds_one_deterministic_slot_with_verified_parent():
    session, _set, item, parent, target = _fixture()
    first = build_support_slots(session, (item,))
    second = build_support_slots(session, (item,))
    assert first == second
    assert len(first) == 1
    assert first[0].evidence_codes == ("EV001",)
    assert tuple(fragment.role for fragment in first[0].fragments) == (
        SupportFragmentRole.TARGET_SNAPSHOT,
        SupportFragmentRole.PARENT_CONTEXT,
    )
    assert first[0].target.legal_element_id == target.id
    assert first[0].parent_context.legal_element_id == parent.id


def test_slot_order_and_manifest_hash_are_deterministic():
    session, _set, item, *_ = _fixture()
    other = SimpleNamespace(**vars(item))
    other.id = uuid.uuid4()
    other.evidence_code = "EV002"
    slots = build_support_slots(session, (item, other))
    assert tuple(slot.evidence_codes[0] for slot in slots) == ("EV001", "EV002")
    assert support_slot_manifest("pergunta", slots) == support_slot_manifest(
        "pergunta", slots
    )


def test_support_slot_is_immutable():
    session, _set, item, *_ = _fixture()
    slot = build_support_slots(session, (item,))[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        slot.slot_id = "alterado"


def test_parent_context_tampering_and_missing_parent_are_rejected():
    session, _set, item, _parent, target = _fixture(recorded_parent="adulterado")
    with pytest.raises(SupportSlotError, match="adulterado"):
        build_support_slots(session, (item,))
    item.validation_metadata["parent_context"] = "não haverá medidas"
    target.parent_id = None
    with pytest.raises(SupportSlotError, match="sem elemento pai"):
        build_support_slots(session, (item,))


def test_only_parent_not_sibling_is_included():
    session, _set, item, *_ = _fixture()
    sibling = SimpleNamespace(
        id=uuid.uuid4(),
        parent_id=item.legal_element_id,
        legal_version_id=uuid.uuid4(),
        normalized_text="conteúdo irmão",
        source_locator={"block_index": 12},
        path="/sibling",
        legal_provision=None,
    )
    session.elements[sibling.id] = sibling
    slot = build_support_slots(session, (item,))[0]
    assert all(fragment.text != "conteúdo irmão" for fragment in slot.fragments)


def test_slot_validation_rejects_external_item_and_invalid_hash():
    session, evidence_set, item, *_ = _fixture()
    slot = build_support_slots(session, (item,))[0]
    assert validate_support_slot(session, evidence_set, slot) == ()
    external_set = SimpleNamespace(id=evidence_set.id, items=[])
    assert "externo" in validate_support_slot(session, external_set, slot)[0]
    altered = dataclasses.replace(
        slot,
        fragments=(
            dataclasses.replace(slot.target, sha256="0" * 64),
            *slot.fragments[1:],
        ),
    )
    assert any(
        "alterado" in value
        for value in validate_support_slot(session, evidence_set, altered)
    )


def test_slot_validation_rejects_parent_from_another_element():
    session, evidence_set, item, *_ = _fixture()
    slot = build_support_slots(session, (item,))[0]
    foreign_parent = dataclasses.replace(
        slot.parent_context, legal_element_id=uuid.uuid4()
    )
    altered = dataclasses.replace(slot, fragments=(slot.target, foreign_parent))
    assert any(
        "PARENT_CONTEXT inválida" in value
        for value in validate_support_slot(session, evidence_set, altered)
    )


def test_slot_validation_rejects_missing_parent_and_divergent_identity():
    session, evidence_set, item, *_ = _fixture()
    slot = build_support_slots(session, (item,))[0]
    without_parent = dataclasses.replace(slot, fragments=(slot.target,))
    assert any(
        "PARENT_CONTEXT ausente" in value
        for value in validate_support_slot(session, evidence_set, without_parent)
    )
    wrong_identity = dataclasses.replace(
        slot,
        fragments=(
            dataclasses.replace(slot.target, identity="CF88/OUTRO"),
            *slot.fragments[1:],
        ),
    )
    assert any(
        "Identidade TARGET divergente" in value
        for value in validate_support_slot(session, evidence_set, wrong_identity)
    )


def test_scoped_prompt_contains_fragments_but_no_binding_identifiers():
    session, _set, item, *_ = _fixture()
    slot = build_support_slots(session, (item,))[0]
    prompt = build_scoped_prompt("pergunta", slot)
    assert "TRECHO ALVO" in prompt
    assert "CONTEXTO ESTRUTURAL PAI" in prompt
    assert "EV001" not in prompt
    assert slot.slot_id not in prompt


@pytest.mark.parametrize(
    "payload",
    (
        {"claim": "A medida é permitida.", "abstain": False, "evidence_id": "EV001"},
        {"claim": "A medida é permitida.", "abstain": False, "slot_id": "SS"},
        {"claim": "", "abstain": False},
        {"claim": "texto", "abstain": True},
        {"claim": 1, "abstain": False},
        {"claim": "Conforme EV001, a medida vale.", "abstain": False},
    ),
)
def test_scoped_contract_rejects_ids_and_inconsistent_payloads(payload):
    with pytest.raises(LLMResponseError):
        parse_scoped_generation(payload)


def test_scoped_contract_accepts_claim_and_clean_abstention():
    assert parse_scoped_generation(
        {"claim": "A medida é permitida.", "abstain": False}
    ).claim
    assert parse_scoped_generation({"claim": "", "abstain": True}).abstain


def test_scoped_prompt_redacts_binding_identifiers_from_retry_diagnostics():
    session, _set, item, *_ = _fixture()
    slot = build_support_slots(session, (item,))[0]
    prompt = build_scoped_prompt(
        "pergunta",
        slot,
        correction=(f"Slot {slot.slot_id} divergiu de EV001.",),
    )
    assert slot.slot_id not in prompt
    assert "EV001" not in prompt
    assert "IDENTIFICADOR REDIGIDO" in prompt


def test_material_exception_and_condition_must_be_preserved():
    session, _set, item, *_ = _fixture()
    slot = build_support_slots(session, (item,))[0]
    assert not validate_material_qualifiers("A medida é permitida.", slot).is_valid
    assert validate_material_qualifiers(
        "A medida é permitida, salvo condição expressa.", slot
    ).is_valid
    conditioned = dataclasses.replace(
        slot,
        fragments=(
            dataclasses.replace(
                slot.target,
                text="A medida é válida quando ocorrer o fato.",
            ),
        ),
    )
    assert not validate_material_qualifiers("A medida é válida.", conditioned).is_valid


def test_query_scope_is_conservative_and_does_not_treat_quais_alone_as_exhaustive():
    assert (
        classify_query_scope("Liste todos os requisitos completos")
        is QueryScope.EXPLICITLY_EXHAUSTIVE
    )
    assert classify_query_scope("Dê um exemplo") is QueryScope.EXPLICITLY_NON_EXHAUSTIVE
    assert (
        classify_query_scope("quais direitos fundamentais")
        is QueryScope.TOPICAL_LIMITED
    )
    assert classify_query_scope("liberdade de expressão") is QueryScope.TOPICAL_LIMITED
    assert classify_query_scope("isso?") is QueryScope.UNRESOLVED


class FixedGenerator:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate_scoped(self, question, slot, *, correction=()):
        self.calls.append((question, slot.slot_id, correction))
        return self.result


class FixedSemantic:
    def __init__(self, supported=True):
        self.supported = supported
        self.calls = []

    def validate(self, response, items):
        self.calls.append((response, items))
        status = (
            SemanticSupportStatus.SUPPORTED
            if self.supported
            else SemanticSupportStatus.UNSUPPORTED
        )
        return SemanticSupportReport(
            (
                ClaimSupport(
                    response.claims[0].claim_code,
                    status,
                    response.claims[0].evidence_codes,
                    "teste",
                ),
            )
        )


def test_bound_pipeline_binds_current_slot_without_attribution(monkeypatch):
    session, evidence_set, _item, *_ = _fixture(parent_text="A medida é permitida")
    generator = FixedGenerator(
        ScopedGeneration("A medida é permitida, salvo condição expressa.", False)
    )
    semantic = FixedSemantic()
    monkeypatch.setattr(
        "consultor_juridico.consultation.evidence_bound.validate_citations",
        lambda *_args, **_kwargs: ValidationReport(True, (), 1, 1),
    )
    result = run_evidence_bound_downstream(
        session,
        "medida permitida",
        evidence_set,
        generator=generator,
        semantic_validator=semantic,
        max_generation_attempts=1,
    )
    assert result.outcome is ConsultationOutcome.ANSWERED
    assert result.claims[0].evidence_codes == ("EV001",)
    assert (
        semantic.calls[0][1][0].validation_metadata["parent_context"]
        == "A medida é permitida"
    )


def test_rejected_claim_is_not_materialized(monkeypatch):
    session, evidence_set, _item, *_ = _fixture()
    generator = FixedGenerator(ScopedGeneration("A medida é permitida.", False))
    semantic = FixedSemantic()
    monkeypatch.setattr(
        "consultor_juridico.consultation.evidence_bound.validate_citations",
        lambda *_args, **_kwargs: ValidationReport(True, (), 1, 1),
    )
    result = run_evidence_bound_downstream(
        session,
        "medida permitida",
        evidence_set,
        generator=generator,
        semantic_validator=semantic,
        max_generation_attempts=1,
    )
    assert result.outcome is ConsultationOutcome.ABSTAINED
    assert result.claims == ()
    assert semantic.calls == []


def test_semantically_unsupported_scoped_claim_fails_closed(monkeypatch):
    session, evidence_set, item, *_ = _fixture()
    item.validation_metadata["parent_context"] = None
    item.text_snapshot = "A matéria trata de orçamento público."
    generator = FixedGenerator(ScopedGeneration("A liberdade é absoluta.", False))
    semantic = FixedSemantic(supported=False)
    monkeypatch.setattr(
        "consultor_juridico.consultation.evidence_bound.validate_citations",
        lambda *_args, **_kwargs: ValidationReport(True, (), 1, 1),
    )
    result = run_evidence_bound_downstream(
        session,
        "liberdade",
        evidence_set,
        generator=generator,
        semantic_validator=semantic,
        max_generation_attempts=1,
    )
    assert result.outcome is ConsultationOutcome.ABSTAINED
    assert result.claims == ()
    assert len(semantic.calls) == 1


def test_explicit_polarity_inversion_is_rejected_before_semantic(monkeypatch):
    session, evidence_set, item, *_ = _fixture()
    item.validation_metadata["parent_context"] = None
    item.text_snapshot = "A medida é proibida."
    generator = FixedGenerator(ScopedGeneration("A medida é permitida.", False))
    semantic = FixedSemantic()
    monkeypatch.setattr(
        "consultor_juridico.consultation.evidence_bound.validate_citations",
        lambda *_args, **_kwargs: ValidationReport(True, (), 1, 1),
    )
    result = run_evidence_bound_downstream(
        session,
        "medida",
        evidence_set,
        generator=generator,
        semantic_validator=semantic,
        max_generation_attempts=1,
    )
    assert result.outcome is ConsultationOutcome.ABSTAINED
    assert result.diagnostics[0].polarity_status == "CONTRADICTED"
    assert semantic.calls == []


def test_exhaustive_question_fails_before_generator():
    session, evidence_set, _item, *_ = _fixture()
    generator = FixedGenerator(ScopedGeneration("texto", False))
    result = run_evidence_bound_downstream(
        session,
        "Liste todos os requisitos completos",
        evidence_set,
        generator=generator,
        semantic_validator=FixedSemantic(),
    )
    assert result.outcome is ConsultationOutcome.ABSTAINED
    assert generator.calls == []


def test_benchmark_accepts_only_exact_or_direct_parent_child_provenance():
    article = "CF88/@root/TITLE:V/CHAPTER:I/SECTION:II/ARTICLE:137"
    caput = f"{article}/CAPUT:@caput"
    chapter = "CF88/@root/TITLE:V/CHAPTER:I"
    assert _structurally_related(caput, caput)
    assert _structurally_related(article, caput)
    assert not _structurally_related(chapter, caput)


def test_benchmark_does_not_count_off_target_answer_as_correct():
    case = SimpleNamespace(
        expect_answer=True,
        expected_provisions=("CF88/ARTICLE:5/INCISO:XLVII/ALINEA:B",),
        acceptable_provisions=(),
    )
    arm = {
        "outcome": "ANSWERED",
        "claims": [
            {
                "claim_code": "C1",
                "evidence_codes": ["EV001"],
            }
        ],
    }
    frozen = {
        "items": [
            {
                "evidence_code": "EV001",
                "validation_metadata": {"identity_key": "CF88/ARTICLE:53"},
            }
        ]
    }
    assessment = _grounded_assessment(case, arm, frozen)
    assert not assessment["correct"]
    assert assessment["reason"] == "OFF_TARGET_ANSWER"
