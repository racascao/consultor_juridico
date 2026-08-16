"""Testes unitários do carregamento integral do DOM legado."""

import hashlib
import uuid
from pathlib import Path

from consultor_juridico.parsing import build_dom, decode_raw_document

FIXTURE = Path(__file__).parent / "fixtures/parsing/premature_html_close.html"


def _build(payload: bytes):
    decoded = decode_raw_document(
        source_document_id=uuid.uuid4(),
        raw_bytes=payload,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )
    return build_dom(decoded)


def test_html_parser_preserves_content_after_premature_close():
    document = _build(FIXTURE.read_bytes())
    visible_text = document.soup.get_text(" ", strip=True)

    assert "antes" in visible_text
    assert "depois" in visible_text
    assert document.metrics.premature_close_found is True
    assert document.metrics.characters_after_first_html_close > 50


def test_dom_metrics_cover_relevant_legacy_structures():
    document = _build(FIXTURE.read_bytes())

    assert document.metrics.total_paragraphs == 3
    assert document.metrics.non_empty_paragraphs == 2
    assert document.metrics.anchors == 2
    assert document.metrics.links == 1
    assert document.metrics.strike_elements == 1
    assert document.metrics.tables == 0
    assert document.metrics.scripts == 1
    assert document.metrics.source_lines_available is True


def test_dom_build_is_deterministic_for_relevant_results():
    payload = FIXTURE.read_bytes()
    first = _build(payload)
    second = _build(payload)

    assert first.decoded.text == second.decoded.text
    assert first.decoded.encoding == second.decoded.encoding
    assert first.metrics == second.metrics
    assert first.soup.get_text(" ", strip=True) == second.soup.get_text(" ", strip=True)


def test_well_formed_html_has_no_premature_close_tail():
    document = _build(b"<html><body><p>texto</p></body></html>")

    assert document.metrics.premature_close_found is False
    assert document.metrics.characters_after_first_html_close == 0
