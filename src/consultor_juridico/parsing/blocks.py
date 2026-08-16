"""Projeção determinística do DOM em blocos documentais factuais."""

import hashlib
import json
import re
from dataclasses import dataclass
from time import perf_counter
from urllib.parse import urljoin

from bs4 import NavigableString, Tag

from consultor_juridico.parsing.types import DomDocument

MATCHING_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class DocumentLink:
    """Hyperlink factual preservado dentro de um bloco."""

    anchor_text: str
    href_original: str
    resolved_url: str | None


@dataclass(frozen=True, slots=True)
class DocumentBlock:
    """Parágrafo observável do HTML, sem interpretação jurídica."""

    block_index: int
    tag: str
    text: str
    normalized_text_for_matching: str
    source_line: int | None
    anchors: tuple[str, ...]
    links: tuple[DocumentLink, ...]
    inside_table: bool
    contains_strike: bool
    fully_struck: bool
    partially_struck: bool


@dataclass(frozen=True, slots=True)
class BlockProjection:
    """Sequência de blocos e diagnóstico de sua produção."""

    blocks: tuple[DocumentBlock, ...]
    fingerprint_sha256: str
    enumeration_duration_ms: float


def normalize_text_for_matching(text: str) -> str:
    """Produz somente a projeção conservadora usada por sentinelas."""
    spacing_normalized = text.replace("\u00a0", " ").replace("\u202f", " ")
    return MATCHING_WHITESPACE.sub(" ", spacing_normalized).strip().casefold()


def enumerate_document_blocks(document: DomDocument) -> BlockProjection:
    """Enumera todos os parágrafos em ordem DOM, começando em um."""
    started_at = perf_counter()
    blocks = tuple(
        _build_block(node, index, document.decoded.source_url)
        for index, node in enumerate(document.soup.find_all("p"), start=1)
    )
    return BlockProjection(
        blocks=blocks,
        fingerprint_sha256=block_projection_fingerprint(blocks),
        enumeration_duration_ms=(perf_counter() - started_at) * 1000,
    )


def block_projection_fingerprint(blocks: tuple[DocumentBlock, ...]) -> str:
    """Calcula fingerprint diagnóstico; não substitui o hash documental."""
    stable_projection = [
        {
            "block_index": block.block_index,
            "tag": block.tag,
            "text": block.text,
            "source_line": block.source_line,
            "anchors": block.anchors,
            "links": [
                (link.anchor_text, link.href_original, link.resolved_url)
                for link in block.links
            ],
            "inside_table": block.inside_table,
            "contains_strike": block.contains_strike,
            "fully_struck": block.fully_struck,
        }
        for block in blocks
    ]
    serialized = json.dumps(
        stable_projection,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _build_block(node: Tag, block_index: int, source_url: str | None) -> DocumentBlock:
    text = node.get_text()
    anchors = _anchors(node)
    links = tuple(
        DocumentLink(
            anchor_text=anchor.get_text(),
            href_original=str(anchor["href"]),
            resolved_url=(
                urljoin(source_url, str(anchor["href"])) if source_url else None
            ),
        )
        for anchor in node.find_all("a", href=True)
    )
    textual_nodes = tuple(
        item
        for item in node.descendants
        if isinstance(item, NavigableString) and str(item).strip()
    )
    struck_nodes = tuple(item for item in textual_nodes if item.find_parent("strike"))
    contains_strike = bool(struck_nodes)
    fully_struck = bool(textual_nodes) and len(struck_nodes) == len(textual_nodes)
    return DocumentBlock(
        block_index=block_index,
        tag=node.name,
        text=text,
        normalized_text_for_matching=normalize_text_for_matching(text),
        source_line=node.sourceline,
        anchors=anchors,
        links=links,
        inside_table=node.find_parent("table") is not None,
        contains_strike=contains_strike,
        fully_struck=fully_struck,
        partially_struck=contains_strike and not fully_struck,
    )


def _anchors(node: Tag) -> tuple[str, ...]:
    values: list[str] = []
    for candidate in (node, *node.find_all("a")):
        for attribute in ("name", "id"):
            value = candidate.get(attribute)
            if value is not None:
                values.append(str(value))
    return tuple(values)
