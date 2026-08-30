"""Tipos imutáveis do pipeline de indexação e retrieval."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class IndexingOutcome(StrEnum):
    CREATED = "CREATED"
    ALREADY_INDEXED = "ALREADY_INDEXED"


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    act: str | None = None
    element_types: tuple[str, ...] = ()
    text_status: str = "CURRENT"
    content_role: str = "NORMATIVE"


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    chunk_id: UUID
    legal_element_id: UUID
    legal_provision_id: UUID
    legal_act: str
    element_type: str
    number_label: str | None
    identity_key: str
    chunk_text: str
    lexical_rank: int | None = None
    lexical_score: float | None = None
    vector_rank: int | None = None
    vector_score: float | None = None
    rrf_score: float | None = None
    contextual_score: float | None = None
    parent_context: str | None = None


@dataclass(frozen=True, slots=True)
class IndexingResult:
    outcome: IndexingOutcome
    chunks: int
    embeddings: int
    dimensions: int
    strategy_name: str
    provider_name: str
    model_name: str
    model_version: str
