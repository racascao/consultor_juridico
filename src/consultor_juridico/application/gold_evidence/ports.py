"""Porta de leitura das Provisions autorizadas como Gold Evidence."""

from typing import Protocol

from consultor_juridico.application.gold_evidence.types import (
    GoldEvidenceContext,
    GoldEvidenceItem,
)


class GoldEvidenceRepository(Protocol):
    def context(self, version_hash: str) -> GoldEvidenceContext: ...

    def materialize(
        self, version_hash: str, stable_keys: tuple[str, ...]
    ) -> tuple[GoldEvidenceItem, ...]: ...

    def provision_keys(self, version_hash: str) -> frozenset[str]: ...

    def validate_citation_namespace(self, citations: frozenset[str]) -> None:
        """Garante que citações podem ser classificadas sem ambiguidade."""
        ...
