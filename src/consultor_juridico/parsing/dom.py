"""Construção integral do DOM legado com BeautifulSoup e html.parser."""

import re
from time import perf_counter

from bs4 import BeautifulSoup

from consultor_juridico.parsing.types import (
    DecodedSourceDocument,
    DomDocument,
    DomMetrics,
)

HTML_CLOSE_PATTERN = re.compile(r"</html\s*>", re.IGNORECASE)


def build_dom(decoded: DecodedSourceDocument) -> DomDocument:
    """Constrói o DOM sem limpar, reparar manualmente ou reserializar a fonte."""
    started_at = perf_counter()
    soup = BeautifulSoup(decoded.text, "html.parser")
    duration_ms = (perf_counter() - started_at) * 1000

    paragraphs = soup.find_all("p")
    anchors = soup.find_all("a")
    first_close = HTML_CLOSE_PATTERN.search(decoded.text)
    characters_after_close = (
        len(decoded.text) - first_close.end() if first_close is not None else 0
    )
    non_trivial_tail = bool(
        first_close is not None and decoded.text[first_close.end() :].strip()
    )
    nodes_with_source_line = soup.find_all(
        lambda tag: tag.name is not None and tag.sourceline is not None, limit=1
    )

    metrics = DomMetrics(
        total_paragraphs=len(paragraphs),
        non_empty_paragraphs=sum(
            bool(node.get_text(strip=True)) for node in paragraphs
        ),
        anchors=len(anchors),
        links=sum(node.has_attr("href") for node in anchors),
        strike_elements=len(soup.find_all("strike")),
        tables=len(soup.find_all("table")),
        scripts=len(soup.find_all("script")),
        premature_close_found=non_trivial_tail,
        characters_after_first_html_close=characters_after_close,
        source_lines_available=bool(nodes_with_source_line),
    )
    return DomDocument(
        decoded=decoded,
        soup=soup,
        metrics=metrics,
        dom_build_duration_ms=duration_ms,
    )
