"""Validação determinística de localizadores jurídicos explícitos."""

from __future__ import annotations

import re
from dataclasses import dataclass

from consultor_juridico.consultation.types import GeneratedResponse
from consultor_juridico.models import EvidenceItem

_LOCATOR = re.compile(
    r"\bart\.?\s*(?P<article>\d+)[ºo]?"
    r"(?:\s*,?\s*(?:inciso|§)\s*(?P<sub>[IVXLCDM]+|\d+))?"
    r"(?:\s*,?\s*alínea\s*[\"']?(?P<letter>[a-z]))?",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class LocatorResult:
    valid: bool
    applicable: bool
    errors: tuple[str, ...] = ()


def validate_response_locators(
    response: GeneratedResponse,
    items: tuple[EvidenceItem, ...],
    *,
    generation_mode: str | None = None,
) -> LocatorResult:
    errors: list[str] = []
    for claim in response.claims:
        if _is_exact_ebcg_snapshot(
            claim.text, claim.evidence_codes, items, generation_mode
        ):
            # Em EBCG, o locator autoritativo é o do EvidenceItem ligado à
            # claim. Remissões normativas dentro do excerto não são locators
            # declarados pelo sistema.
            continue
        matches = list(_LOCATOR.finditer(claim.text))
        if not matches:
            continue
        cited = {
            item.evidence_code: _identity(item)
            for item in items
            if item.evidence_code in claim.evidence_codes
        }
        if not any(
            _matches(match, identity)
            for match in matches
            for identity in cited.values()
        ):
            errors.append(f"LOCATOR_MISMATCH: {claim.claim_code}")
    return LocatorResult(not errors, bool(response.claims), tuple(errors))


def _is_exact_ebcg_snapshot(
    claim_text: str,
    evidence_codes: tuple[str, ...],
    items: tuple[EvidenceItem, ...],
    generation_mode: str | None,
) -> bool:
    if generation_mode not in {"EBCG_V1", "EBCG_V2"} or len(evidence_codes) != 1:
        return False
    code = evidence_codes[0]
    return any(
        item.evidence_code == code and claim_text == item.text_snapshot
        for item in items
    )


def _identity(item: EvidenceItem) -> str:
    return str((item.validation_metadata or {}).get("identity_key", "")).upper()


def _matches(match: re.Match[str], identity: str) -> bool:
    if f"ARTICLE:{match.group('article')}" not in identity:
        return False
    sub = match.group("sub")
    letter = match.group("letter")
    if sub and f":{sub.upper()}" not in identity:
        return False
    if letter and f"ALINEA:{letter.upper()}" not in identity:
        return False
    return True
