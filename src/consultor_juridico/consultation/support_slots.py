"""SupportSlots determinísticos com fragmentos de proveniência verificável."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType, SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from consultor_juridico.models import EvidenceItem, LegalElement


class SupportSlotError(ValueError):
    """Indica que um slot não pode ser reconstruído com segurança."""


class SupportFragmentRole(StrEnum):
    TARGET_SNAPSHOT = "TARGET_SNAPSHOT"
    PARENT_CONTEXT = "PARENT_CONTEXT"


@dataclass(frozen=True, slots=True)
class SupportFragment:
    role: SupportFragmentRole
    text: str
    legal_element_id: UUID
    identity: str
    source_locator_json: str
    sha256: str

    def manifest(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "text": self.text,
            "legal_element_id": str(self.legal_element_id),
            "identity": self.identity,
            "source_locator": json.loads(self.source_locator_json),
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class SupportSlot:
    slot_id: str
    evidence_set_id: UUID
    evidence_item_id: UUID
    evidence_codes: tuple[str, ...]
    identity_key: str
    fragments: tuple[SupportFragment, ...]

    @property
    def target(self) -> SupportFragment:
        return self.fragments[0]

    @property
    def parent_context(self) -> SupportFragment | None:
        return next(
            (
                fragment
                for fragment in self.fragments
                if fragment.role is SupportFragmentRole.PARENT_CONTEXT
            ),
            None,
        )

    def manifest(self) -> dict[str, object]:
        return {
            "slot_id": self.slot_id,
            "evidence_set_id": str(self.evidence_set_id),
            "evidence_item_id": str(self.evidence_item_id),
            "evidence_codes": list(self.evidence_codes),
            "identity_key": self.identity_key,
            "fragments": [fragment.manifest() for fragment in self.fragments],
        }

    def evidence_view(self) -> SimpleNamespace:
        """Expõe exatamente os mesmos fragmentos aos validators downstream."""
        parent = self.parent_context
        metadata = MappingProxyType(
            {
                "identity_key": self.identity_key,
                "parent_context": parent.text if parent else None,
                "support_slot_id": self.slot_id,
                "support_fragments": tuple(
                    fragment.manifest() for fragment in self.fragments
                ),
            }
        )
        return SimpleNamespace(
            evidence_code=self.evidence_codes[0],
            text_snapshot=self.target.text,
            validation_metadata=metadata,
        )


def build_support_slots(
    session: Session, evidence_items: tuple[EvidenceItem, ...]
) -> tuple[SupportSlot, ...]:
    """Cria um slot por EvidenceItem, preservando a ordem do snapshot."""
    return tuple(_build_slot(session, item) for item in evidence_items)


def support_slot_manifest(
    question: str, slots: tuple[SupportSlot, ...]
) -> dict[str, object]:
    return {
        "query": question,
        "slots": [slot.manifest() for slot in slots],
        "manifest_sha256": _sha256(
            json.dumps(
                [slot.manifest() for slot in slots],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        ),
    }


def validate_support_slot(
    session: Session, evidence_set: Any, slot: SupportSlot
) -> tuple[str, ...]:
    """Valida fragmentos contra EvidenceItem e LegalElements persistidos."""
    errors: list[str] = []
    items = {item.evidence_code: item for item in evidence_set.items}
    if len(slot.evidence_codes) != 1:
        return (f"Slot {slot.slot_id} não possui binding unitário.",)
    code = slot.evidence_codes[0]
    item = items.get(code)
    if item is None or item.id != slot.evidence_item_id:
        return (f"Slot {slot.slot_id} referencia EvidenceItem externo.",)
    if (
        item.evidence_set_id != slot.evidence_set_id
        or evidence_set.id != slot.evidence_set_id
    ):
        errors.append(f"Slot {slot.slot_id} diverge do EvidenceSet autorizado.")
    if (
        not slot.fragments
        or slot.target.role is not SupportFragmentRole.TARGET_SNAPSHOT
    ):
        errors.append(f"Slot {slot.slot_id} não possui TARGET_SNAPSHOT válido.")
        return tuple(errors)
    target = session.get(LegalElement, item.legal_element_id)
    if target is None or target.id != slot.target.legal_element_id:
        errors.append(f"Origem TARGET inválida no slot {slot.slot_id}.")
        return tuple(errors)
    if slot.target.identity != slot.identity_key:
        errors.append(f"Identidade TARGET divergente no slot {slot.slot_id}.")
    errors.extend(_validate_fragment(slot.target, item.text_snapshot, target))
    parent_fragment = slot.parent_context
    metadata = item.validation_metadata or {}
    recorded_parent = metadata.get("parent_context")
    expects_parent = isinstance(recorded_parent, str) and bool(recorded_parent.strip())
    if expects_parent and parent_fragment is None:
        errors.append(f"PARENT_CONTEXT ausente no slot {slot.slot_id}.")
    if not expects_parent and parent_fragment is not None:
        errors.append(f"PARENT_CONTEXT não autorizado no slot {slot.slot_id}.")
    if parent_fragment is not None:
        parent = (
            session.get(LegalElement, target.parent_id) if target.parent_id else None
        )
        if parent is None or parent.id != parent_fragment.legal_element_id:
            errors.append(f"Origem PARENT_CONTEXT inválida no slot {slot.slot_id}.")
        else:
            if parent_fragment.identity != _element_identity(parent):
                errors.append(
                    f"Identidade PARENT_CONTEXT divergente no slot {slot.slot_id}."
                )
            errors.extend(
                _validate_fragment(
                    parent_fragment, parent.normalized_text.strip(), parent
                )
            )
    return tuple(dict.fromkeys(errors))


def _build_slot(session: Session, item: EvidenceItem) -> SupportSlot:
    if not item.id or not item.evidence_set_id or not item.evidence_code:
        raise SupportSlotError("EvidenceItem ainda não possui identidade persistida.")
    element = session.get(LegalElement, item.legal_element_id)
    if element is None:
        raise SupportSlotError(
            f"LegalElement de {item.evidence_code} não foi encontrado."
        )
    metadata = item.validation_metadata or {}
    identity_key = str(
        metadata.get("identity_key")
        or (
            element.legal_provision.identity_key
            if element.legal_provision is not None
            else element.path
        )
        or element.id
    )
    target = _fragment(
        SupportFragmentRole.TARGET_SNAPSHOT,
        item.text_snapshot,
        element,
        identity_key,
    )
    fragments = [target]
    recorded_parent = metadata.get("parent_context")
    if isinstance(recorded_parent, str) and recorded_parent.strip():
        if element.parent_id is None:
            raise SupportSlotError(
                f"{item.evidence_code} declara parent_context sem elemento pai."
            )
        parent = session.get(LegalElement, element.parent_id)
        if parent is None or parent.legal_version_id != element.legal_version_id:
            raise SupportSlotError(
                f"Pai estrutural inválido para {item.evidence_code}."
            )
        parent_text = parent.normalized_text.strip()
        if recorded_parent.strip() != parent_text:
            raise SupportSlotError(
                f"parent_context adulterado em {item.evidence_code}."
            )
        parent_identity = _element_identity(parent)
        fragments.append(
            _fragment(
                SupportFragmentRole.PARENT_CONTEXT,
                parent_text,
                parent,
                parent_identity,
            )
        )
    fingerprint = _sha256(
        "|".join(
            (
                str(item.evidence_set_id),
                str(item.id),
                item.evidence_code,
                *(fragment.sha256 for fragment in fragments),
            )
        )
    )
    slot_uuid = uuid.uuid5(uuid.NAMESPACE_URL, fingerprint)
    return SupportSlot(
        slot_id=f"SS-{slot_uuid.hex}",
        evidence_set_id=item.evidence_set_id,
        evidence_item_id=item.id,
        evidence_codes=(item.evidence_code,),
        identity_key=identity_key,
        fragments=tuple(fragments),
    )


def _fragment(
    role: SupportFragmentRole,
    text: str,
    element: LegalElement,
    identity: str,
) -> SupportFragment:
    if not text.strip():
        raise SupportSlotError(f"Fragmento {role.value} vazio.")
    locator = json.dumps(
        element.source_locator,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return SupportFragment(
        role=role,
        text=text,
        legal_element_id=element.id,
        identity=identity,
        source_locator_json=locator,
        sha256=_sha256(text),
    )


def _element_identity(element: LegalElement) -> str:
    return str(
        element.legal_provision.identity_key
        if element.legal_provision is not None
        else element.path or element.id
    )


def _validate_fragment(
    fragment: SupportFragment, expected_text: str, element: LegalElement
) -> tuple[str, ...]:
    errors = []
    if fragment.text != expected_text or fragment.sha256 != _sha256(expected_text):
        errors.append(f"Fragmento {fragment.role.value} alterado.")
    expected_locator = json.dumps(
        element.source_locator,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if fragment.source_locator_json != expected_locator:
        errors.append(f"Locator de {fragment.role.value} divergente.")
    return tuple(errors)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
