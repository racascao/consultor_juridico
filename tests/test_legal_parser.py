"""Golden tests do parser jurídico estrutural exclusivamente em memória."""

import hashlib
import uuid
from pathlib import Path

import pytest

from consultor_juridico.parsing import (
    ContentRole,
    ElementType,
    LegalHierarchyError,
    TextStatus,
    build_dom,
    decode_raw_document,
    enumerate_document_blocks,
    parse_constitution,
    segment_constitution_document,
)

FIXTURES = Path(__file__).parent / "fixtures/parsing"


def _blocks(name: str):
    payload = (FIXTURES / name).read_text().encode("windows-1252")
    decoded = decode_raw_document(
        source_document_id=uuid.uuid4(),
        raw_bytes=payload,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        source_url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
    )
    return enumerate_document_blocks(build_dom(decoded)).blocks


def _full_segments(cf_extra: str, adct_extra: str):
    cf_end = "" if "Art. 250" in cf_extra else "<p>Art. 250. Fecho da CF.</p>"
    adct_end = "" if "Art. 138" in adct_extra else "<p>Art. 138. Fecho do ADCT.</p>"
    html = (
        "<p>PREÂMBULO</p><p>Texto preambular.</p>"
        + cf_extra
        + cf_end
        + "<p>Assinaturas</p>"
        + "<p>ATO DAS DISPOSIÇÕES CONSTITUCIONAIS TRANSITÓRIAS</p>"
        + adct_extra
        + adct_end
    )
    payload = html.encode("windows-1252")
    decoded = decode_raw_document(
        source_document_id=uuid.uuid4(),
        raw_bytes=payload,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )
    projection = enumerate_document_blocks(build_dom(decoded))
    return segment_constitution_document(projection.blocks)


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def test_root_preamble_divisions_article_and_caput():
    extra = (FIXTURES / "legal_01_start_cf.html").read_text().split("<p>Art. 1º", 1)[1]
    segments = _full_segments(
        "<p>TÍTULO I</p><p>Dos Princípios Fundamentais</p><p>Art. 1º" + extra,
        "<p>Art. 1º ADCT.</p>",
    )
    parsed = parse_constitution(segments)
    flat = tuple(_walk(parsed.cf88.root))

    assert parsed.cf88.root.element_type == ElementType.DOCUMENT_ROOT
    assert parsed.cf88.root.document_order == 1
    assert any(item.element_type == ElementType.PREAMBLE for item in flat)
    title = next(item for item in flat if item.element_type == ElementType.TITLE)
    article = next(
        item
        for item in flat
        if item.element_type == ElementType.ARTICLE and item.number_label == "1"
    )
    assert "Dos Princípios" in title.raw_text
    assert [child.element_type for child in article.children].count(
        ElementType.CAPUT
    ) == 1
    assert parsed.cf88.root.identity_key == "CF88/@root"
    assert article.identity_key.endswith("/ARTICLE:1")
    assert article.children[0].identity_key == f"{article.identity_key}/CAPUT:@caput"
    assert all(
        item.identity_key for item in flat if item.element_type != ElementType.NOTE
    )
    assert all(
        item.identity_key is None
        for item in flat
        if item.element_type == ElementType.NOTE
    )


def test_deep_hierarchy_paragraph_inciso_alinea_item():
    segments = _full_segments(
        (FIXTURES / "legal_02_deep_hierarchy.html").read_text(), "<p>Art. 1º ADCT.</p>"
    )
    flat = tuple(_walk(parse_constitution(segments).cf88.root))
    types = {item.element_type for item in flat}
    assert {
        ElementType.ARTICLE,
        ElementType.CAPUT,
        ElementType.PARAGRAPH,
        ElementType.INCISO,
        ElementType.ALINEA,
        ElementType.ITEM,
    } <= types
    sole = _full_segments(
        "<p>Art. 2º Texto.</p><p>Parágrafo único. Regra única.</p>",
        "<p>Art. 1º ADCT.</p>",
    )
    paragraph = next(
        item
        for item in _walk(parse_constitution(sole).cf88.root)
        if item.element_type == ElementType.PARAGRAPH
    )
    assert paragraph.number_label == "único"


def test_historical_revoked_unresolved_and_notes():
    extra = (
        (FIXTURES / "legal_03_historical.html").read_text()
        + (FIXTURES / "legal_04_revoked.html").read_text()
        + "<p><strike>Art. 8º Texto incerto.</strike></p>"
    )
    parsed = parse_constitution(_full_segments(extra, "<p>Art. 1º ADCT.</p>"))
    flat = tuple(_walk(parsed.cf88.root))
    statuses = {item.text_status for item in flat}
    assert {
        TextStatus.HISTORICAL,
        TextStatus.REVOKED,
        TextStatus.UNRESOLVED,
    } <= statuses
    notes = [item for item in flat if item.element_type == ElementType.NOTE]
    assert notes and all(
        item.text_status == TextStatus.NOT_APPLICABLE for item in notes
    )
    assert all(item.content_role != ContentRole.NORMATIVE for item in notes)


def test_historical_occurrences_share_normative_identity():
    parsed = parse_constitution(
        _full_segments(
            "<p><strike>Art. 6º Redação histórica.</strike></p>"
            "<p>Art. 6º Redação corrente.</p>",
            "<p>Art. 1º ADCT.</p>",
        )
    )
    articles = [
        item
        for item in _walk(parsed.cf88.root)
        if item.element_type == ElementType.ARTICLE and item.number_label == "6"
    ]
    assert len(articles) == 2
    assert len({item.identity_key for item in articles}) == 1
    assert (
        len(
            [
                item
                for item in parsed.cf88.provisions
                if item.element_type == ElementType.ARTICLE and item.number_label == "6"
            ]
        )
        == 1
    )
    assert articles[0].identity_key != next(
        item.identity_key
        for item in _walk(parsed.adct.root)
        if item.element_type == ElementType.ARTICLE and item.number_label == "1"
    )


def test_links_anchors_locator_metadata_and_continuous_order():
    extra = (FIXTURES / "legal_05_notes_links.html").read_text()
    act = parse_constitution(_full_segments(extra, "<p>Art. 1º ADCT.</p>")).cf88
    flat = tuple(_walk(act.root))
    assert tuple(item.document_order for item in flat) == tuple(range(1, len(flat) + 1))
    assert all(item.source_locator["block_index"] >= 1 for item in flat)
    assert any((item.parser_metadata or {}).get("links") for item in flat)
    assert any("art5" in item.source_locator["anchors"] for item in flat)


def test_suffix_recent_adct_and_determinism():
    adct = (
        FIXTURES / "legal_08_suffix.html"
    ).read_text() + "<p>Art. 134. Regra recente.</p>"
    segments = _full_segments("<p>Art. 1º CF.</p>", adct)
    first = parse_constitution(segments)
    second = parse_constitution(segments)
    labels = {item.number_label for item in _walk(first.adct.root)}
    assert {"116-A", "117", "134", "138"} <= labels
    assert first.cf88.fingerprint_sha256 == second.cf88.fingerprint_sha256
    assert first.adct.fingerprint_sha256 == second.adct.fingerprint_sha256
    assert first.cf88.coverage == second.cf88.coverage


def test_end_of_cf_and_complex_adct_golden_fixtures():
    cf = (FIXTURES / "legal_06_cf_end.html").read_text()
    adct = (FIXTURES / "legal_07_adct_complex.html").read_text()
    parsed = parse_constitution(_full_segments(cf, adct))
    assert "250" in {item.number_label for item in _walk(parsed.cf88.root)}
    adct_types = {item.element_type for item in _walk(parsed.adct.root)}
    assert {
        ElementType.ARTICLE,
        ElementType.CAPUT,
        ElementType.PARAGRAPH,
        ElementType.INCISO,
        ElementType.ALINEA,
    } <= adct_types


def test_recent_and_after_premature_close_golden_fixtures():
    recent = _blocks("legal_09_recent.html")
    assert [block.text.split()[1].rstrip(".") for block in recent] == ["134", "138"]

    after_close = _blocks("legal_10_after_close.html")
    assert [block.text for block in after_close] == [
        "Art. 1º Texto inicial.",
        "Art. 138. Texto tardio preservado.",
    ]


def test_partial_strike_is_factual_and_conservatively_unresolved():
    parsed = parse_constitution(
        _full_segments(
            "<p>Art. 9º Texto <strike>parcial anterior</strike> vigente.</p>",
            "<p>Art. 1º ADCT.</p>",
        )
    )
    caput = next(
        item
        for item in _walk(parsed.cf88.root)
        if item.element_type == ElementType.CAPUT
    )
    assert caput.text_status == TextStatus.UNRESOLVED
    assert caput.parser_metadata == {
        "synthetic_structure": True,
        "classification_rule": "article_caput",
        "strike_coverage": "partial",
    }


def test_coverage_accounts_for_every_block_and_ignored_reason():
    parsed = parse_constitution(
        _full_segments(
            "<p>Bloco desconhecido</p><p>Art. 1º CF.</p>", "<p>Art. 1º ADCT.</p>"
        )
    )
    report = parsed.cf88.coverage
    assert report.total_blocks == report.consumed_blocks + report.ignored_blocks
    assert report.ignored_by_reason["unclassified_block"] == 1
    assert len(report.entries) == report.total_blocks


def test_subdivision_without_article_fails_explicitly():
    with pytest.raises(LegalHierarchyError):
        parse_constitution(_full_segments("<p>I - órfão.</p>", "<p>Art. 1º ADCT.</p>"))


def test_spacing_variants_and_inciso_without_hyphen_are_recognized():
    html = (FIXTURES / "correction_04_alinea_spacing.html").read_text()
    act = parse_constitution(_full_segments(html, "<p>Art. 1º ADCT.</p>")).cf88
    flat = tuple(_walk(act.root))
    assert [
        item.number_label for item in flat if item.element_type == ElementType.INCISO
    ] == ["I"]
    assert [
        item.number_label for item in flat if item.element_type == ElementType.ALINEA
    ] == ["a", "b"]
    assert act.coverage.ignored_blocks == 0

    no_hyphen = (FIXTURES / "correction_05_inciso_no_hyphen.html").read_text()
    second = parse_constitution(_full_segments(no_hyphen, "<p>Art. 1º ADCT.</p>")).cf88
    assert [
        item.number_label
        for item in _walk(second.root)
        if item.element_type == ElementType.INCISO
    ] == ["I", "II", "IV"]


def test_alphanumeric_inciso_preserves_factual_label_and_rejects_lowercase_prose():
    html = (FIXTURES / "correction_06_inciso_viiia.html").read_text()
    html += "<p>Da organização administrativa.</p>"
    act = parse_constitution(_full_segments(html, "<p>Art. 1º ADCT.</p>")).cf88
    flat = tuple(_walk(act.root))
    assert [
        item.number_label for item in flat if item.element_type == ElementType.INCISO
    ] == ["VIIIA"]
    assert act.coverage.ignored_by_reason == {"unclassified_block": 1}


def test_section_suffix_skips_editorial_note_before_rubric():
    html = (FIXTURES / "correction_07_section_va.html").read_text()
    act = parse_constitution(_full_segments(html, "<p>Art. 1º ADCT.</p>")).cf88
    flat = tuple(_walk(act.root))
    section = next(
        item
        for item in flat
        if item.element_type == ElementType.SECTION and item.number_label == "V-A"
    )
    assert "Do Imposto sobre Bens e Serviços" in section.raw_text
    assert any(child.element_type == ElementType.NOTE for child in section.children)
    assert act.coverage.ignored_blocks == 0


def test_continuous_inciso_series_without_hyphens_is_preserved():
    html = (FIXTURES / "correction_09_inciso_series.html").read_text()
    act = parse_constitution(_full_segments(html, "<p>Art. 1º ADCT.</p>")).cf88
    assert [
        item.number_label
        for item in _walk(act.root)
        if item.element_type == ElementType.INCISO
    ] == ["I", "II", "III", "IV"]


def test_strike_ancestor_is_factual_and_never_current():
    html = (FIXTURES / "correction_10_struck_current_adct.html").read_text()
    act = parse_constitution(_full_segments("<p>Art. 1º CF.</p>", html)).adct
    article = next(
        item
        for item in _walk(act.root)
        if item.element_type == ElementType.ARTICLE and item.number_label == "83"
    )
    assert article.text_status == TextStatus.UNRESOLVED
    assert article.children[0].text_status == TextStatus.UNRESOLVED
    assert article.parser_metadata == {"strike_coverage": "full"}
