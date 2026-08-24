"""Reconstrução determinística de contexto normativo para EvidenceItems."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from consultor_juridico.models import EvidenceItem, LegalElement

_TEXTUAL_CONTEXT_TYPES = {"CAPUT", "PARAGRAPH", "INCISO", "ALINEA"}
_HIERARCHY_TYPES = {
    "TITLE",
    "CHAPTER",
    "SECTION",
    "SUBSECTION",
    "ARTICLE",
    "PARAGRAPH",
    "INCISO",
    "ALINEA",
    "ITEM",
}


@dataclass(frozen=True, slots=True)
class StructuredSourcePart:
    element_id: UUID
    element_type: str
    number_label: str | None
    identity_key: str | None
    text: str
    relation: str
    document_order: int


@dataclass(frozen=True, slots=True)
class StructuredEvidenceUnit:
    evidence_code: str
    source_element_ids: tuple[UUID, ...]
    identity_key: str | None
    hierarchy: tuple[str, ...]
    original_snapshot: str
    original_parent_context: str | None
    structured_text: str
    parts: tuple[StructuredSourcePart, ...]
    sha256: str


def build_structured_evidence(
    item: Any,
    target: StructuredSourcePart,
    *,
    ancestors: tuple[StructuredSourcePart, ...] = (),
    siblings: tuple[StructuredSourcePart, ...] = (),
) -> StructuredEvidenceUnit:
    """Organiza texto factual já existente, sem resumo ou paráfrase."""

    ordered_ancestors = tuple(sorted(ancestors, key=lambda part: part.document_order))
    hierarchy = tuple(
        _label(part)
        for part in (*ordered_ancestors, target)
        if part.element_type in _HIERARCHY_TYPES
    )
    textual_ancestors = tuple(
        part
        for part in ordered_ancestors
        if part.element_type in _TEXTUAL_CONTEXT_TYPES and part.text.strip()
    )
    contextual_siblings = tuple(
        part
        for part in sorted(siblings, key=lambda part: part.document_order)
        if _needs_enumeration_context(textual_ancestors, siblings)
    )
    parts = _deduplicate_parts((*textual_ancestors, target, *contextual_siblings))
    lines = [" > ".join(hierarchy)] if hierarchy else []
    lines.extend(part.text.strip() for part in parts if part.text.strip())
    structured_text = "\n".join(lines)
    source_ids = tuple(part.element_id for part in parts)
    digest = hashlib.sha256(structured_text.encode("utf-8")).hexdigest()
    metadata = getattr(item, "validation_metadata", None) or {}
    return StructuredEvidenceUnit(
        evidence_code=item.evidence_code,
        source_element_ids=source_ids,
        identity_key=metadata.get("identity_key") or target.identity_key,
        hierarchy=hierarchy,
        original_snapshot=item.text_snapshot,
        original_parent_context=metadata.get("parent_context"),
        structured_text=structured_text,
        parts=parts,
        sha256=digest,
    )


def load_structured_evidence(
    session: Session, item: EvidenceItem
) -> StructuredEvidenceUnit:
    """Carrega somente a estrutura da mesma versão/ato do elemento citado."""

    element = session.get(LegalElement, item.legal_element_id)
    if element is None:
        raise ValueError("LegalElement da evidência não encontrado.")
    ancestors: list[LegalElement] = []
    cursor = element.parent
    while cursor is not None:
        ancestors.append(cursor)
        cursor = cursor.parent
    ancestors.reverse()
    siblings: tuple[LegalElement, ...] = ()
    if element.parent is not None and _parent_introduces_enumeration(element.parent):
        siblings = tuple(
            child
            for child in element.parent.children
            if child.id != element.id
            and child.element_type == element.element_type
            and child.text_status == "CURRENT"
            and child.content_role == "NORMATIVE"
        )
    return build_structured_evidence(
        item,
        _part(element, "TARGET"),
        ancestors=tuple(_part(value, "ANCESTOR") for value in ancestors),
        siblings=tuple(_part(value, "SIBLING") for value in siblings),
    )


def _part(element: LegalElement, relation: str) -> StructuredSourcePart:
    provision = element.legal_provision
    return StructuredSourcePart(
        element.id,
        element.element_type,
        element.number_label,
        provision.identity_key if provision else element.path,
        element.normalized_text,
        relation,
        element.document_order,
    )


def _label(part: StructuredSourcePart) -> str:
    suffix = f" {part.number_label}" if part.number_label else ""
    return f"{part.element_type}{suffix}"


def _parent_introduces_enumeration(parent: LegalElement) -> bool:
    text = parent.normalized_text.strip()
    return text.endswith(":") and 1 < len(parent.children) <= 12


def _needs_enumeration_context(
    ancestors: tuple[StructuredSourcePart, ...],
    siblings: tuple[StructuredSourcePart, ...],
) -> bool:
    return bool(ancestors and ancestors[-1].text.strip().endswith(":") and siblings)


def _deduplicate_parts(
    parts: tuple[StructuredSourcePart, ...],
) -> tuple[StructuredSourcePart, ...]:
    seen: set[UUID] = set()
    result = []
    for part in sorted(parts, key=lambda value: value.document_order):
        if part.element_id not in seen:
            seen.add(part.element_id)
            result.append(part)
    return tuple(result)
