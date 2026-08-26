"""Fonte única de texto efetivo para evidências runtime."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from consultor_juridico.consultation.vcsa import StructuralFragment, compose
from consultor_juridico.models import LegalElement, LegalProvision


@dataclass(frozen=True, slots=True)
class MaterializedEvidence:
    evidence_item: Any
    effective_text: str
    materialization_type: str = "LEGACY"
    provenance: dict[str, str] | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.evidence_item, name)

    @property
    def text_snapshot(self) -> str:
        return self.effective_text


def materialize(item: Any) -> MaterializedEvidence:
    """Retorna a única projeção textual permitida aos consumidores runtime."""
    metadata = getattr(item, "validation_metadata", None) or {}
    vcsa = metadata.get("vcsa")
    if isinstance(vcsa, dict) and isinstance(vcsa.get("effective_text"), str):
        return MaterializedEvidence(item, vcsa["effective_text"], "VCSA")
    parent = metadata.get("parent_context")
    text = " ".join(
        value.strip()
        for value in (getattr(item, "text_snapshot", ""), parent)
        if isinstance(value, str) and value.strip()
    )
    return MaterializedEvidence(item, text)


def materialize_for_consultation(
    session: Session, items: tuple[Any, ...]
) -> tuple[MaterializedEvidence, ...]:
    """Única resolução VCSA runtime; falha sempre para a evidência legacy."""
    result = []
    for item in items:
        target = session.get(LegalElement, item.legal_element_id)
        parent = (
            session.get(LegalElement, target.parent_id)
            if target and target.parent_id
            else None
        )
        if target is None or parent is None:
            result.append(materialize(item))
            continue
        target_provision = session.get(LegalProvision, target.legal_provision_id)
        parent_provision = session.get(LegalProvision, parent.legal_provision_id)
        if target_provision is None or parent_provision is None:
            result.append(materialize(item))
            continue
        parent_fragment = StructuralFragment(
            str(parent.id),
            parent_provision.identity_key,
            parent.normalized_text or "",
            parent.element_type,
            None,
            str(parent.legal_act_id),
            str(parent.legal_version_id),
            parent.text_status,
            parent.content_role,
        )
        child_fragment = StructuralFragment(
            str(target.id),
            target_provision.identity_key,
            target.normalized_text or "",
            target.element_type,
            str(parent.id),
            str(target.legal_act_id),
            str(target.legal_version_id),
            target.text_status,
            target.content_role,
        )
        composed = compose(parent_fragment, child_fragment)
        if not composed.applicable or not composed.text:
            result.append(materialize(item))
            continue
        result.append(
            MaterializedEvidence(
                item,
                composed.text,
                "VCSA",
                vcsa_metadata(
                    target=child_fragment,
                    parent=parent_fragment,
                    effective_text=composed.text,
                ),
            )
        )
    return tuple(result)


def materialize_all(items: tuple[Any, ...]) -> tuple[MaterializedEvidence, ...]:
    return tuple(materialize(item) for item in items)


def vcsa_metadata(*, target: Any, parent: Any, effective_text: str) -> dict[str, str]:
    """Metadata auditável, sem sobrescrever o snapshot original."""
    return {
        "materialization_type": "VCSA",
        "target_identity": target.identity,
        "target_element_id": target.element_id,
        "target_text_hash": hashlib.sha256(target.text.encode()).hexdigest(),
        "parent_identity": parent.identity,
        "parent_element_id": parent.element_id,
        "parent_text_hash": hashlib.sha256(parent.text.encode()).hexdigest(),
        "legal_act_id": target.legal_act_id,
        "legal_version_id": target.legal_version_id,
        "composition_rule": "DIRECT_PARENT_CURRENT_NORMATIVE_LITERAL",
        "composition_hash": hashlib.sha256(
            f"{parent.element_id}|{target.element_id}|{effective_text}".encode()
        ).hexdigest(),
        "effective_text": effective_text,
    }
