"""Portas externas necessárias pelo fluxo RAG."""

from typing import Protocol

from consultor_juridico.application.gold_evidence.ports import GoldEvidenceRepository
from consultor_juridico.application.gold_evidence.types import GoldEvidenceItem


class FrozenAnswerer(Protocol):
    def generate(self, *, system_prompt: str, user_prompt: str) -> str: ...


class StructuralEvidenceRepository(GoldEvidenceRepository, Protocol):
    def direct_children(
        self,
        version_hash: str,
        parent_keys: tuple[str, ...],
        *,
        max_children_per_parent: int,
    ) -> dict[str, tuple[GoldEvidenceItem, ...]]: ...
