"""Testes da projeção factual do DOM em DocumentBlock."""

import hashlib
import uuid

from consultor_juridico.parsing import (
    build_dom,
    decode_raw_document,
    enumerate_document_blocks,
    normalize_text_for_matching,
)


def _project(
    html: str, *, source_url: str | None = "https://example.test/base/doc.htm"
):
    payload = html.encode("windows-1252")
    decoded = decode_raw_document(
        source_document_id=uuid.uuid4(),
        raw_bytes=payload,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        source_url=source_url,
    )
    return enumerate_document_blocks(build_dom(decoded))


def test_block_index_order_text_and_determinism():
    html = "<p>  Texto\xa0 factual </p><p>segundo</p>"
    first = _project(html)
    second = _project(html)

    assert tuple(block.block_index for block in first.blocks) == (1, 2)
    assert first.blocks[0].text == "  Texto\xa0 factual "
    assert first.blocks[0].normalized_text_for_matching == "texto factual"
    assert first.blocks == second.blocks
    assert first.fingerprint_sha256 == second.fingerprint_sha256


def test_matching_normalization_is_conservative_and_separate():
    factual = "  Art.\xa0 250 — AÇÃO  "

    assert normalize_text_for_matching(factual) == "art. 250 — ação"
    assert factual == "  Art.\xa0 250 — AÇÃO  "


def test_anchors_links_and_resolution_are_preserved():
    projection = _project(
        '<p id="p1"><a name="art1"></a><a href="../ec/1.htm"> EC 1 </a></p>'
    )
    block = projection.blocks[0]

    assert block.anchors == ("p1", "art1")
    assert block.links[0].anchor_text == " EC 1 "
    assert block.links[0].href_original == "../ec/1.htm"
    assert block.links[0].resolved_url == "https://example.test/ec/1.htm"


def test_missing_source_url_does_not_invent_resolved_url():
    block = _project('<p><a href="relative.htm">link</a></p>', source_url=None).blocks[
        0
    ]

    assert block.links[0].resolved_url is None


def test_source_line_is_factual_and_absence_is_not_invented():
    payload = b"<p>linha</p>"
    decoded = decode_raw_document(
        source_document_id=uuid.uuid4(),
        raw_bytes=payload,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )
    dom = build_dom(decoded)
    assert enumerate_document_blocks(dom).blocks[0].source_line == 1

    dom.soup.p.sourceline = None
    assert enumerate_document_blocks(dom).blocks[0].source_line is None


def test_strike_coverage_is_factual_only():
    blocks = _project(
        "<p><strike>todo</strike></p>"
        "<p>parte <strike>riscada</strike></p>"
        "<p>corrente</p>"
    ).blocks

    assert (blocks[0].contains_strike, blocks[0].fully_struck) == (True, True)
    assert blocks[1].partially_struck is True
    assert not blocks[2].contains_strike


def test_scripts_and_inline_tags_do_not_become_independent_blocks():
    projection = _project(
        "<script>infraestrutura</script><p><span>texto</span><a>âncora</a></p>"
    )

    assert len(projection.blocks) == 1
    assert projection.blocks[0].tag == "p"
    assert projection.blocks[0].text == "textoâncora"
