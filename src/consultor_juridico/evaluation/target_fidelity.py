"""Medição determinística de fidelidade ao alvo jurídico congelado."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from consultor_juridico.evaluation.types import EvaluationCase


@dataclass(frozen=True, slots=True)
class TargetFidelityResult:
    passed: bool | None
    allowed_targets: tuple[str, ...]
    used_evidence_identity_keys: tuple[str, ...]
    reason: str


def allowed_targets(case: EvaluationCase) -> tuple[str, ...]:
    """Retorna o contrato de alvo do dataset, sem alterar o caso original."""
    return tuple(dict.fromkeys(case.expected_provisions + case.acceptable_provisions))


def assess_target_fidelity(
    case: EvaluationCase,
    identity_keys: Iterable[str],
) -> TargetFidelityResult:
    """Compara identidades efetivamente citadas com o contrato do caso."""
    used = tuple(dict.fromkeys(identity for identity in identity_keys if identity))
    allowed = allowed_targets(case)
    if not case.expect_answer:
        return TargetFidelityResult(None, allowed, used, "NOT_APPLICABLE")
    if any(identity in allowed for identity in used):
        return TargetFidelityResult(True, allowed, used, "ALLOWED_TARGET_CITED")
    return TargetFidelityResult(
        False, allowed, used, "NO_CITED_EVIDENCE_IN_ALLOWED_TARGETS"
    )
