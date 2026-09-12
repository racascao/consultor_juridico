"""Caso de uso mínimo para materializar evidência declarada pelo dataset."""

from consultor_juridico.application.gold_evidence.ports import (
    GoldEvidenceRepository,
)
from consultor_juridico.application.gold_evidence.types import GoldEvidenceItem


class MaterializeGoldEvidence:
    def __init__(self, repository: GoldEvidenceRepository) -> None:
        self._repository = repository

    def execute(
        self, *, version_hash: str, stable_keys: tuple[str, ...]
    ) -> tuple[GoldEvidenceItem, ...]:
        self._repository.context(version_hash)
        evidence = self._repository.materialize(version_hash, stable_keys)
        found = {item.stable_key for item in evidence}
        missing = sorted(set(stable_keys) - found)
        if missing:
            raise LookupError(
                f"Provisions ausentes na ActVersion: {', '.join(missing)}"
            )
        return evidence
