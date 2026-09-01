"""Porta de saída do retrieval lexical."""

from collections.abc import Mapping
from typing import Protocol

from consultor_juridico.domain.retrieval import (
    RetrievalCandidate,
    RetrievalContext,
    RetrievalRequest,
)


class SearchUnitRetriever(Protocol):
    @property
    def implementation_name(self) -> str: ...

    @property
    def retrieval_config(self) -> Mapping[str, str | int]: ...

    def search(self, request: RetrievalRequest) -> tuple[RetrievalCandidate, ...]: ...

    def context(self, version_hash: str) -> RetrievalContext: ...

    def provision_keys(self, version_hash: str) -> frozenset[str]: ...
