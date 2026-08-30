"""Tipos imutáveis internos do retrieval."""

from dataclasses import dataclass
from enum import StrEnum

from consultor_juridico.domain import CitationItem


class EmbeddingMode(StrEnum):
    DOCUMENT = "DOCUMENT"
    QUERY = "QUERY"


@dataclass(frozen=True, slots=True)
class EmbeddingDocument:
    search_unit_id: str
    search_text: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class RankedSearchUnit:
    search_unit_id: str
    search_unit_type: str
    legal_act_code: str
    stable_reference: str
    article_reference: str | None
    search_text: str
    citation_items: tuple[CitationItem, ...]
    source_locator: str
    source_url: str
    source_snapshot_sha: str
    lexical_rank: int | None = None
    vector_rank: int | None = None
    fused_score: float = 0.0
