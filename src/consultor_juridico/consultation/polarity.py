"""Guard determinístico contra inversões de polaridade em claims.

O guard não valida a verdade completa de uma claim. Ele apenas procura uma
contradição explícita entre sinais normativos presentes na claim e no snapshot
das evidências autorizadas. Na dúvida, retorna ``UNRESOLVED`` (fail-closed no
serviço) e nunca promove uma claim para ``SUPPORTED``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from consultor_juridico.consultation.types import GeneratedClaim, GeneratedResponse


class PolarityStatus(StrEnum):
    CONSISTENT = "CONSISTENT"
    CONTRADICTED = "CONTRADICTED"
    UNRESOLVED = "UNRESOLVED"


class PolarityReason(StrEnum):
    NO_POLARITY_RELATION = "NO_POLARITY_RELATION"
    EXCEPTION_SCOPE_AMBIGUITY = "EXCEPTION_SCOPE_AMBIGUITY"
    MISSING_EVIDENCE_SIGNAL = "MISSING_EVIDENCE_SIGNAL"
    MISSING_CLAIM_SIGNAL = "MISSING_CLAIM_SIGNAL"


@dataclass(frozen=True, slots=True)
class PolarityValidationResult:
    status: PolarityStatus
    claim_code: str
    evidence_codes: tuple[str, ...]
    reason: str
    evidence_polarities: tuple[str, ...] = ()
    claim_polarities: tuple[str, ...] = ()
    reason_code: PolarityReason | None = None

    @property
    def is_safe(self) -> bool:
        return self.status is PolarityStatus.CONSISTENT


@dataclass(frozen=True, slots=True)
class ResponsePolarityResult:
    results: tuple[PolarityValidationResult, ...]

    @property
    def is_valid(self) -> bool:
        return bool(self.results) and all(item.is_safe for item in self.results)

    @property
    def errors(self) -> tuple[str, ...]:
        return tuple(
            f"Claim {item.claim_code}: {item.status.value} — {item.reason}"
            for item in self.results
            if not item.is_safe
        )


def can_route_to_semantic(result: PolarityValidationResult) -> bool:
    """Define a fronteira fail-closed entre o guard e o juiz semântico."""
    if result.status is PolarityStatus.CONTRADICTED:
        return False
    if result.status is PolarityStatus.UNRESOLVED:
        return result.reason_code is PolarityReason.NO_POLARITY_RELATION
    return True


WORD_RE = re.compile(r"[^\W\d_]{2,}", re.UNICODE)
_NEGATION_RE = re.compile(
    r"\b(?:não|nao|nunca|jamais|proib(?:ido|ida)|vedad[oa]|impedid[oa])\b"
    r"|\bnão\s+(?:haverá|havera|poderá|podera|é|e|será|sera)\b",
    re.IGNORECASE,
)
_OBLIGATION_RE = re.compile(r"\b(?:obrigat\w*|dever\w*|exigid\w*)\b", re.IGNORECASE)
_OPTIONAL_RE = re.compile(r"\b(?:facultativ\w*|opcional\w*)\b", re.IGNORECASE)
_PERMISSION_RE = re.compile(
    r"\b(?:permitid\w*|admitid\w*|autorizad\w*|facultad\w*|pode|podem|poderá|podera)\b",
    re.IGNORECASE,
)
_EXCEPTION_RE = re.compile(
    r"\b(?:salvo|exceto|excepto|ressalvad\w*|ressalva|em\s+caso\s+de)\b",
    re.IGNORECASE,
)
_AFFIRMATIVE_RE = re.compile(
    r"\b(?:garantid\w*|assegurad\w*|inviol[aá]vel|inviolabil\w*|protege\w*|estabelec\w*|"
    r"reafirm\w*|reconhec\w*)\b",
    re.IGNORECASE,
)
_FUNCTIONAL = {
    "a",
    "ao",
    "as",
    "aos",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "é",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "para",
    "pela",
    "pelas",
    "pelo",
    "pelos",
    "por",
    "que",
    "se",
    "um",
    "uma",
    "uns",
    "umas",
    "não",
    "nao",
}


def validate_polarity(
    claim: GeneratedClaim, evidence_items: tuple[Any, ...]
) -> PolarityValidationResult:
    """Valida uma claim apenas contra os EvidenceItems que ela cita."""

    by_code = {getattr(item, "evidence_code", None): item for item in evidence_items}
    cited = tuple(code for code in claim.evidence_codes if code in by_code)
    if not cited:
        return PolarityValidationResult(
            PolarityStatus.UNRESOLVED,
            claim.claim_code,
            (),
            "Nenhuma evidência autorizada foi encontrada para a claim.",
            reason_code=PolarityReason.MISSING_EVIDENCE_SIGNAL,
        )

    evidence_text = " ".join(_evidence_text(by_code[code]) for code in cited)
    claim_profile = _profile(claim.text)
    evidence_profile = _profile(evidence_text)
    claim_targets = _targets(claim.text)
    evidence_targets = _targets(evidence_text)
    overlap = claim_targets & evidence_targets

    if not overlap or not claim_profile or not evidence_profile:
        if "EXCEPTION" in evidence_profile and "EXCEPTION" not in claim_profile:
            reason_code = PolarityReason.EXCEPTION_SCOPE_AMBIGUITY
        elif not claim_profile and evidence_profile:
            reason_code = PolarityReason.MISSING_CLAIM_SIGNAL
        else:
            reason_code = PolarityReason.NO_POLARITY_RELATION
        return PolarityValidationResult(
            PolarityStatus.UNRESOLVED,
            claim.claim_code,
            cited,
            "Não há sinais normativos e alvo textual suficientes "
            "para comparar polaridade.",
            tuple(sorted(evidence_profile)),
            tuple(sorted(claim_profile)),
            reason_code,
        )

    contradictions = _contradictions(claim_profile, evidence_profile)
    if contradictions:
        return PolarityValidationResult(
            PolarityStatus.CONTRADICTED,
            claim.claim_code,
            cited,
            "Sinais normativos explícitos da claim contradizem a evidência: "
            + ", ".join(contradictions),
            tuple(sorted(evidence_profile)),
            tuple(sorted(claim_profile)),
            None,
        )

    # Omissão de exceção é perigosa, mas não é uma contradição textual segura.
    if "EXCEPTION" in evidence_profile and "EXCEPTION" not in claim_profile:
        status = PolarityStatus.UNRESOLVED
        reason = (
            "A evidência contém exceção normativa não refletida "
            "explicitamente na claim."
        )
    elif evidence_profile & claim_profile:
        status = PolarityStatus.CONSISTENT
        reason = "Nenhuma inversão explícita de polaridade foi detectada."
    else:
        status = PolarityStatus.UNRESOLVED
        reason = "Os sinais normativos não são comparáveis com segurança."
    return PolarityValidationResult(
        status,
        claim.claim_code,
        cited,
        reason,
        tuple(sorted(evidence_profile)),
        tuple(sorted(claim_profile)),
        PolarityReason.EXCEPTION_SCOPE_AMBIGUITY
        if status is PolarityStatus.UNRESOLVED
        else None,
    )


def validate_response_polarity(
    response: GeneratedResponse, evidence_items: tuple[Any, ...]
) -> ResponsePolarityResult:
    if response.abstain:
        return ResponsePolarityResult(())
    return ResponsePolarityResult(
        tuple(validate_polarity(claim, evidence_items) for claim in response.claims)
    )


def _evidence_text(item: Any) -> str:
    metadata = getattr(item, "validation_metadata", None) or {}
    parent = metadata.get("parent_context")
    text = getattr(item, "text_snapshot", "")
    return " ".join(part for part in (text, parent) if isinstance(part, str))


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFD", text.casefold())
    return "".join(char for char in value if not unicodedata.combining(char))


def _profile(text: str) -> set[str]:
    normalized = _normalize(text)
    profile: set[str] = set()
    if _NEGATION_RE.search(normalized):
        profile.add("PROHIBITIVE")
    if _OBLIGATION_RE.search(normalized) and "PROHIBITIVE" not in profile:
        profile.add("OBLIGATORY")
    if _OPTIONAL_RE.search(normalized):
        profile.add("OPTIONAL")
    if _PERMISSION_RE.search(normalized) and "PROHIBITIVE" not in profile:
        profile.add("PERMISSIVE")
    if _EXCEPTION_RE.search(normalized):
        profile.add("EXCEPTION")
    if _AFFIRMATIVE_RE.search(normalized) and "PROHIBITIVE" not in profile:
        profile.add("AFFIRMATIVE")
    return profile


def _targets(text: str) -> set[str]:
    return {
        token[:7]
        for token in WORD_RE.findall(_normalize(text))
        if token not in _FUNCTIONAL and len(token) >= 4
    }


def _contradictions(claim: set[str], evidence: set[str]) -> tuple[str, ...]:
    pairs = (
        ("PROHIBITIVE", "PERMISSIVE", "proibição versus permissão"),
        ("OBLIGATORY", "OPTIONAL", "obrigação versus facultatividade"),
    )
    found = []
    for left, right, label in pairs:
        if (left in claim and right in evidence) or (
            right in claim and left in evidence
        ):
            found.append(label)
    return tuple(found)
