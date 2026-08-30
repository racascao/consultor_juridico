"""Política determinística para escolher a Core Evidence já autorizada."""

from __future__ import annotations

import re
from typing import Protocol

CORE_EVIDENCE_POLICY_V1 = "EV001"
CORE_EVIDENCE_POLICY_A = "QUERY_COVERAGE_BASE_RELEVANCE_SELECTED_POSITION"
CORE_EVIDENCE_POLICY_V2 = (
    "QUERY_COVERAGE_MARGINAL_COVERAGE_BASE_RELEVANCE_SELECTED_POSITION"
)

_EVIDENCE_CODE_RE = re.compile(r"^EV(?P<number>\d+)$", re.IGNORECASE)


class CoreEvidenceItem(Protocol):
    """Superfície mínima de um EvidenceItem para a política pura."""

    evidence_code: str
    validation_metadata: dict[str, object] | None


def select_core_evidence_v2(
    evidence_items: tuple[CoreEvidenceItem, ...],
) -> CoreEvidenceItem | None:
    """Seleciona uma evidência autorizada pelos diagnostics já existentes.

    Não recebe pergunta, dataset, caso nem rótulo dourado: a política somente
    ordena os itens já selecionados. A ausência de qualquer signal obrigatório
    torna a seleção inconclusiva para manter o caminho fail-closed.
    """
    if not evidence_items:
        return None
    ranked: list[tuple[CoreEvidenceItem, tuple[float, float, float, int, int]]] = []
    for item in evidence_items:
        metadata = item.validation_metadata or {}
        try:
            query_coverage = float(metadata["query_coverage"])
            marginal_coverage = float(metadata["marginal_coverage"])
            base_relevance = float(metadata["base_relevance"])
            selected_position = int(metadata["selected_position"])
        except (KeyError, TypeError, ValueError):
            return None
        code_number = _evidence_code_number(item.evidence_code)
        if selected_position < 1 or code_number is None:
            return None
        ranked.append(
            (
                item,
                (
                    query_coverage,
                    marginal_coverage,
                    base_relevance,
                    -selected_position,
                    -code_number,
                ),
            )
        )
    return max(ranked, key=lambda value: value[1])[0]


def _evidence_code_number(evidence_code: str) -> int | None:
    match = _EVIDENCE_CODE_RE.fullmatch(evidence_code)
    return int(match.group("number")) if match else None
