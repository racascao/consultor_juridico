"""Verified Composite Structural Answer, estritamente parent direto + child."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

ALLOWED = {
    ("CAPUT", "INCISO"),
    ("PARAGRAPH", "INCISO"),
    ("INCISO", "ALINEA"),
    ("ALINEA", "ITEM"),
}


@dataclass(frozen=True, slots=True)
class StructuralFragment:
    element_id: str
    identity: str
    text: str
    element_type: str
    parent_id: str | None
    legal_act_id: str
    legal_version_id: str
    text_status: str = "CURRENT"
    content_role: str = "NORMATIVE"


@dataclass(frozen=True, slots=True)
class VCSAResult:
    applicable: bool
    text: str | None = None
    composition_hash: str | None = None
    reason: str | None = None


def compose(parent: StructuralFragment, child: StructuralFragment) -> VCSAResult:
    if child.parent_id != parent.element_id:
        return VCSAResult(False, reason="DIRECT_PARENT_REQUIRED")
    if (parent.element_type, child.element_type) not in ALLOWED:
        return VCSAResult(False, reason="RELATION_NOT_ALLOWED")
    if (
        parent.legal_act_id != child.legal_act_id
        or parent.legal_version_id != child.legal_version_id
    ):
        return VCSAResult(False, reason="CROSS_DOCUMENT_SCOPE")
    if parent.text_status != "CURRENT" or child.text_status != "CURRENT":
        return VCSAResult(False, reason="NON_CURRENT")
    if parent.content_role != "NORMATIVE" or child.content_role != "NORMATIVE":
        return VCSAResult(False, reason="NON_NORMATIVE")
    if not re.search(r":\s*$", parent.text):
        return VCSAResult(False, reason="PARENT_NOT_STRUCTURALLY_INCOMPLETE")
    text = f"{parent.text.strip()} {child.text.strip()}"
    digest = hashlib.sha256(
        f"{parent.element_id}|{child.element_id}|{text}".encode()
    ).hexdigest()
    return VCSAResult(True, text=text, composition_hash=digest)
