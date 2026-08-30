"""Construção do corpus contextual v0.2."""

from consultor_juridico.application.corpus.builder import SearchUnitBuilder
from consultor_juridico.application.corpus.use_case import (
    BuildCorpusResult,
    BuildCorpusUseCase,
    CorpusBuildOutcome,
    MaterializeCorpusUseCase,
    RematerializeCorpusFromSnapshotUseCase,
)
from consultor_juridico.application.corpus.validation import (
    DuplicateProvisionStableKey,
    validate_unique_provision_keys,
)

__all__ = [
    "BuildCorpusResult",
    "BuildCorpusUseCase",
    "CorpusBuildOutcome",
    "DuplicateProvisionStableKey",
    "MaterializeCorpusUseCase",
    "RematerializeCorpusFromSnapshotUseCase",
    "SearchUnitBuilder",
    "validate_unique_provision_keys",
]
