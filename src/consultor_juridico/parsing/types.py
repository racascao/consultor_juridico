"""Tipos imutáveis produzidos pelo decoder e pelo carregador de DOM."""

from dataclasses import dataclass
from uuid import UUID

from bs4 import BeautifulSoup


@dataclass(frozen=True, slots=True)
class DecodedSourceDocument:
    """Projeção Unicode íntegra de um SourceDocument."""

    source_document_id: UUID
    content_hash_sha256: str
    source_url: str | None
    encoding: str
    text: str
    decoding_duration_ms: float


@dataclass(frozen=True, slots=True)
class DomMetrics:
    """Fingerprint estrutural diagnóstico, sem semântica jurídica."""

    total_paragraphs: int
    non_empty_paragraphs: int
    anchors: int
    links: int
    strike_elements: int
    tables: int
    scripts: int
    premature_close_found: bool
    characters_after_first_html_close: int
    source_lines_available: bool


@dataclass(frozen=True, slots=True)
class DomDocument:
    """DOM derivado e seu diagnóstico estrutural reproduzível."""

    decoded: DecodedSourceDocument
    soup: BeautifulSoup
    metrics: DomMetrics
    dom_build_duration_ms: float
