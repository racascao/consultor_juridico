"""Testes da segmentação documental, sem interpretação jurídica."""

import hashlib
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

from consultor_juridico.parsing import (
    AmbiguousDocumentSentinelError,
    InvalidDocumentOrderError,
    MissingDocumentSentinelError,
    build_dom,
    decode_raw_document,
    enumerate_document_blocks,
    segment_constitution_document,
)

FIXTURES = Path(__file__).parent / "fixtures/parsing"


def _blocks(name: str):
    payload = (FIXTURES / name).read_text(encoding="utf-8").encode("windows-1252")
    decoded = decode_raw_document(
        source_document_id=uuid.uuid4(),
        raw_bytes=payload,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )
    dom = build_dom(decoded)
    return dom, enumerate_document_blocks(dom).blocks


def test_false_adct_menu_is_leading_and_real_heading_starts_adct():
    _, blocks = _blocks("segmentation_01_false_menu_adct.html")
    segments = segment_constitution_document(blocks)

    assert (
        "ato das disposições" in segments.leading_blocks[0].normalized_text_for_matching
    )
    assert segments.leading_blocks[0].inside_table is True
    assert segments.cf_blocks[0].normalized_text_for_matching == "preâmbulo"
    assert segments.adct_blocks[0].anchors == ("adct",)


def test_cf_transition_adct_and_trailing_regions_are_observable():
    _, blocks = _blocks("segmentation_03_cf_transition_adct.html")
    segments = segment_constitution_document(blocks)

    assert segments.cf_blocks[-1].normalized_text_for_matching.startswith("art. 250")
    assert [block.text for block in segments.transition_blocks] == [
        "Brasília, 5 de outubro de 1988.",
        "Este texto não substitui o publicado no D.O.U.",
    ]
    assert segments.adct_blocks[0].normalized_text_for_matching.startswith("ato das")
    assert segments.adct_blocks[-1].normalized_text_for_matching.startswith("art. 138")
    assert segments.trailing_blocks == ()


def test_content_after_premature_html_close_remains_in_adct():
    dom, blocks = _blocks("segmentation_05_premature_close.html")
    segments = segment_constitution_document(blocks)

    assert dom.metrics.premature_close_found is True
    assert "preservado depois" in segments.adct_blocks[-1].normalized_text_for_matching


def test_adct_end_leaves_later_editorial_content_trailing():
    _, blocks = _blocks("segmentation_04_adct_end.html")
    segments = segment_constitution_document(blocks)

    assert segments.adct_blocks[-1].normalized_text_for_matching.startswith("art. 138")
    assert tuple(block.text for block in segments.trailing_blocks) == (
        "Assinaturas posteriores",
    )


def test_missing_adct_sentinel_fails_explicitly():
    _, blocks = _blocks("segmentation_06_missing_adct.html")
    with pytest.raises(MissingDocumentSentinelError, match="ADCT"):
        segment_constitution_document(blocks)


def test_ambiguous_adct_sentinel_fails_explicitly():
    _, blocks = _blocks("segmentation_07_ambiguous_adct.html")
    with pytest.raises(AmbiguousDocumentSentinelError, match="ambígua"):
        segment_constitution_document(blocks)


def test_impossible_sentinel_order_fails_explicitly():
    _, blocks = _blocks("segmentation_08_impossible_order.html")
    with pytest.raises(InvalidDocumentOrderError, match="antes"):
        segment_constitution_document(blocks)


def test_invalid_block_index_order_fails_explicitly():
    _, blocks = _blocks("segmentation_02_cf_start.html")
    invalid = (replace(blocks[0], block_index=2), *blocks[1:])
    with pytest.raises(InvalidDocumentOrderError, match="block_index"):
        segment_constitution_document(invalid)


def test_partition_has_no_duplicates_and_is_deterministic():
    _, blocks = _blocks("segmentation_03_cf_transition_adct.html")
    first = segment_constitution_document(blocks)
    second = segment_constitution_document(blocks)
    all_regions = (
        first.leading_blocks
        + first.cf_blocks
        + first.transition_blocks
        + first.adct_blocks
        + first.trailing_blocks
    )

    assert first.leading_blocks == second.leading_blocks
    assert first.cf_blocks == second.cf_blocks
    assert first.transition_blocks == second.transition_blocks
    assert first.adct_blocks == second.adct_blocks
    assert first.trailing_blocks == second.trailing_blocks
    assert tuple(block.block_index for block in all_regions) == tuple(
        range(1, len(blocks) + 1)
    )
