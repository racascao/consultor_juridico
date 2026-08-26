"""Orçamento explícito para candidatos de expansão estrutural, sem reranking."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StructuralBudgetResult:
    primary: tuple[Any, ...]
    reserve: tuple[Any, ...]

    @property
    def pool(self) -> tuple[Any, ...]:
        return self.primary + self.reserve


def apply_structural_reserve(
    primary: tuple[Any, ...], promotions: tuple[Any, ...], *, reserve_k: int
) -> StructuralBudgetResult:
    """Mantém o top-K primário intacto e anexa reserve estrutural auditável."""
    if reserve_k < 0:
        raise ValueError("reserve_k não pode ser negativo")
    seen = {item.identity_key for item in primary}
    eligible = [
        item
        for item in promotions
        if getattr(item, "retrieval_source", None) == "STRUCTURAL_EXPANSION"
        and item.candidate.identity_key not in seen
    ]
    ordered = sorted(
        eligible,
        key=lambda item: (
            -float(item.structural_score),
            item.structural_child_identity,
        ),
    )
    return StructuralBudgetResult(
        primary, tuple(item.candidate for item in ordered[:reserve_k])
    )
