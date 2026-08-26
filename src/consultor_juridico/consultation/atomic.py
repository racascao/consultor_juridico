"""Política pura de aceitação atômica para replay e futura integração."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AtomicClaim:
    code: str
    text: str
    on_target: bool
    core_answer: bool
    attributed: bool = True
    locator_valid: bool = True
    polarity_valid: bool = True
    semantic_valid: bool = True
    citation_valid: bool = True
    material_dependency: bool = False


@dataclass(frozen=True, slots=True)
class AtomicDecision:
    accepted: tuple[AtomicClaim, ...]
    rejected: tuple[tuple[AtomicClaim, str], ...]
    abstain: bool


def accept_atomic_claims(claims: tuple[AtomicClaim, ...]) -> AtomicDecision:
    rejected: list[tuple[AtomicClaim, str]] = []
    accepted: list[AtomicClaim] = []
    for claim in claims:
        reason = _rejection_reason(claim)
        if reason:
            rejected.append((claim, reason))
        else:
            accepted.append(claim)
    if any(claim.material_dependency for claim, _ in rejected):
        return AtomicDecision((), tuple(rejected), True)
    if not any(claim.on_target and claim.core_answer for claim in accepted):
        return AtomicDecision((), tuple(rejected), True)
    return AtomicDecision(tuple(accepted), tuple(rejected), False)


def _rejection_reason(claim: AtomicClaim) -> str | None:
    if not claim.attributed:
        return "ATTRIBUTION_REJECTION"
    if not claim.locator_valid:
        return "LOCATOR_REJECTION"
    if not claim.polarity_valid:
        return "POLARITY_REJECTION"
    if not claim.semantic_valid:
        return "SEMANTIC_REJECTION"
    if not claim.citation_valid:
        return "CITATION_REJECTION"
    if not claim.on_target:
        return "NOT_ON_TARGET"
    return None
