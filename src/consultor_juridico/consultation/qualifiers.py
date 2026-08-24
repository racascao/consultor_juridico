"""Preservação determinística de qualificadores materiais do slot."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from consultor_juridico.consultation.support_slots import SupportSlot


@dataclass(frozen=True, slots=True)
class MaterialQualifierReport:
    is_valid: bool
    required: tuple[str, ...]
    preserved: tuple[str, ...]
    errors: tuple[str, ...]


_PATTERNS = {
    "EXCEPTION": re.compile(
        r"\b(?:salvo|exceto|excepto|ressalvad\w*)\b|\b(?:a|à)\s+excecao\s+de\b"
    ),
    "CONDITION": re.compile(r"\b(?:desde\s+que|contanto\s+que|quando)\b"),
    "LIMITATION": re.compile(r"\b(?:somente|apenas)\b"),
}


def validate_material_qualifiers(
    claim_text: str, slot: SupportSlot
) -> MaterialQualifierReport:
    evidence = " ".join(fragment.text for fragment in slot.fragments)
    required = _classes(evidence)
    preserved = _classes(claim_text)
    missing = tuple(sorted(required - preserved))
    return MaterialQualifierReport(
        is_valid=not missing,
        required=tuple(sorted(required)),
        preserved=tuple(sorted(preserved)),
        errors=tuple(
            f"Claim omitiu qualificador material {value} presente no slot."
            for value in missing
        ),
    )


def _classes(value: str) -> set[str]:
    normalized = _normalize(value)
    return {name for name, pattern in _PATTERNS.items() if pattern.search(normalized)}


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))
