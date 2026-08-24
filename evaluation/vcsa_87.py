"""Verified Core Support Assertion experimental, sem integração de produção."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from consultor_juridico.consultation.qualifiers import validate_material_qualifiers
from consultor_juridico.consultation.support_slots import (
    SupportFragment,
    SupportFragmentRole,
    SupportSlot,
    validate_support_slot,
)
from consultor_juridico.models import EvidenceSet, LegalElement


class VCSAStatus(StrEnum):
    VERIFIED = "VERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class VerifiedCoreSupportAssertion:
    """Projeção textual literal de um pai direto e seu filho dependente."""

    status: VCSAStatus
    reconstructed_text: str | None
    source_evidence_code: str
    fragments: tuple[SupportFragment, ...]
    reconstruction_rule: str | None
    composition_hash: str | None
    reason: str


_ALLOWED_RELATIONS = frozenset(
    {
        ("CAPUT", "INCISO"),
        ("PARAGRAPH", "INCISO"),
        ("INCISO", "ALINEA"),
        ("ALINEA", "ITEM"),
    }
)
_RULE = "DIRECT_PARENT_COLON_PLUS_DEPENDENT_CHILD_V1"


def build_vcsa(
    session: Session, evidence_set: EvidenceSet | Any, slot: SupportSlot
) -> VerifiedCoreSupportAssertion:
    """Constrói VCSA somente quando a composição literal é demonstrável."""
    provenance_errors = validate_support_slot(session, evidence_set, slot)
    if provenance_errors:
        return _unresolved(slot, "; ".join(provenance_errors))
    if len(slot.fragments) != 2 or slot.parent_context is None:
        return _not_applicable(
            slot, "VCSA inicial exige exatamente TARGET_SNAPSHOT e PARENT_CONTEXT."
        )

    target = session.get(LegalElement, slot.target.legal_element_id)
    parent = session.get(LegalElement, slot.parent_context.legal_element_id)
    if target is None or parent is None:
        return _unresolved(slot, "Elemento de proveniência não encontrado.")
    if target.parent_id != parent.id:
        return _unresolved(
            slot, "PARENT_CONTEXT não é o pai direto do TARGET_SNAPSHOT."
        )
    if target.legal_version_id != parent.legal_version_id:
        return _unresolved(slot, "Pai e filho pertencem a LegalVersions diferentes.")
    if target.legal_act_id != parent.legal_act_id:
        return _unresolved(slot, "Pai e filho pertencem a LegalActs diferentes.")
    if not _is_current_normative(parent) or not _is_current_normative(target):
        return _not_applicable(
            slot, "VCSA aceita somente elementos normativos CURRENT não editoriais."
        )
    if (parent.element_type, target.element_type) not in _ALLOWED_RELATIONS:
        return _not_applicable(
            slot,
            "Relação estrutural não permitida: "
            f"{parent.element_type} → {target.element_type}.",
        )

    parent_text = slot.parent_context.text
    target_text = _target_legal_text(slot.target, target.normalized_text)
    if target_text is None:
        return _unresolved(
            slot,
            "TARGET_SNAPSHOT não corresponde ao texto normalizado do elemento citado.",
        )
    if not parent_text.rstrip().endswith(":"):
        return _not_applicable(slot, "O pai direto não termina em marcador ':'.")
    if not target_text or not target_text[0].islower():
        return _not_applicable(
            slot, "O filho não inicia conteúdo textual dependente em minúscula."
        )

    reconstructed = f"{parent_text.rstrip()} {target_text.lstrip()}"
    qualifiers = validate_material_qualifiers(reconstructed, slot)
    if not qualifiers.is_valid:
        return _unresolved(slot, "; ".join(qualifiers.errors))
    return VerifiedCoreSupportAssertion(
        VCSAStatus.VERIFIED,
        reconstructed,
        slot.evidence_codes[0],
        slot.fragments,
        _RULE,
        _sha256(reconstructed),
        "Composição literal de pai direto e filho dependente verificada.",
    )


def _target_legal_text(fragment: SupportFragment, normalized_text: str) -> str | None:
    """Remove somente o prefixo técnico do snapshot quando ele é verificável."""
    target = normalized_text.strip()
    snapshot = fragment.text
    if snapshot == target:
        return target
    prefix, separator, body = snapshot.partition("\n")
    if separator and prefix.strip() and body == target:
        return target
    return None


def _is_current_normative(element: LegalElement | Any) -> bool:
    return (
        element.content_role == "NORMATIVE"
        and element.text_status == "CURRENT"
        and element.element_type != "NOTE"
    )


def _not_applicable(slot: SupportSlot, reason: str) -> VerifiedCoreSupportAssertion:
    return VerifiedCoreSupportAssertion(
        VCSAStatus.NOT_APPLICABLE,
        None,
        slot.evidence_codes[0],
        slot.fragments,
        None,
        None,
        reason,
    )


def _unresolved(slot: SupportSlot, reason: str) -> VerifiedCoreSupportAssertion:
    return VerifiedCoreSupportAssertion(
        VCSAStatus.UNRESOLVED,
        None,
        slot.evidence_codes[0],
        slot.fragments,
        None,
        None,
        reason,
    )


def assertion_manifest(assertion: VerifiedCoreSupportAssertion) -> dict[str, object]:
    """Serialização reproduzível e completa para o artefato offline."""
    return {
        "status": assertion.status.value,
        "reconstructed_text": assertion.reconstructed_text,
        "source_evidence_code": assertion.source_evidence_code,
        "fragments": [fragment.manifest() for fragment in assertion.fragments],
        "reconstruction_rule": assertion.reconstruction_rule,
        "composition_hash": assertion.composition_hash,
        "reason": assertion.reason,
    }


def slot_from_manifest(data: dict[str, Any]) -> SupportSlot:
    """Reidrata um SupportSlot congelado sem buscar ou criar evidências."""
    fragments = tuple(
        SupportFragment(
            SupportFragmentRole(fragment["role"]),
            fragment["text"],
            UUID(fragment["legal_element_id"]),
            fragment["identity"],
            json.dumps(
                fragment["source_locator"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            fragment["sha256"],
        )
        for fragment in data["fragments"]
    )
    return SupportSlot(
        data["slot_id"],
        UUID(data["evidence_set_id"]),
        UUID(data["evidence_item_id"]),
        tuple(data["evidence_codes"]),
        data["identity_key"],
        fragments,
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
