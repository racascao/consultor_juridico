"""Regressão opt-in e somente leitura sobre a captura constitucional aceita."""

import os
import time
import uuid
from collections import Counter

import pytest
from sqlalchemy import func, select

from consultor_juridico.db.session import SessionLocal
from consultor_juridico.models import (
    LegalElement,
    LegalProvision,
    LegalVersion,
    ParsingRun,
    SourceDocument,
)
from consultor_juridico.parsing import (
    article_audit_projection,
    audit_parsed_constitution,
    build_dom,
    decode_source_document,
    enumerate_document_blocks,
    parse_constitution,
    parsed_act_metrics,
    segment_constitution_document,
)

pytestmark = pytest.mark.parsing_integration

REFERENCE_DOCUMENT_ID = uuid.UUID("27f0ff6b-dd9e-4c4e-ba56-c34984f691e1")
REFERENCE_SHA256 = "25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d"


@pytest.mark.skipif(
    os.getenv("RUN_PARSING_INTEGRATION") != "1",
    reason="Defina RUN_PARSING_INTEGRATION=1 para ler a captura real local.",
)
def test_reference_capture_decodes_and_builds_complete_dom_read_only():
    with SessionLocal() as session:
        document = session.get(SourceDocument, REFERENCE_DOCUMENT_ID)
        assert document is not None
        assert document.content_hash_sha256 == REFERENCE_SHA256

        counts_before = _derived_counts(session)
        started_at = time.perf_counter()
        first = build_dom(decode_source_document(document))
        projection = enumerate_document_blocks(first)
        segments = segment_constitution_document(projection.blocks)
        parsed = parse_constitution(segments)
        audit_started_at = time.perf_counter()
        audit = audit_parsed_constitution(parsed.cf88, parsed.adct, segments)
        audit_ms = (time.perf_counter() - audit_started_at) * 1000
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        second = build_dom(decode_source_document(document))
        reparsed = parse_constitution(
            segment_constitution_document(enumerate_document_blocks(second).blocks)
        )
        reaudit = audit_parsed_constitution(
            reparsed.cf88,
            reparsed.adct,
            segment_constitution_document(enumerate_document_blocks(second).blocks),
        )
        counts_after = _derived_counts(session)

    metrics = first.metrics
    visible_text = first.soup.get_text(" ", strip=True)
    first_close = first.decoded.text.lower().index("</html>")

    assert 4_300 <= metrics.total_paragraphs <= 4_400
    assert 4_280 <= metrics.non_empty_paragraphs <= 4_380
    assert 7_300 <= metrics.anchors <= 7_500
    assert 2_500 <= metrics.links <= 2_650
    assert 740 <= metrics.strike_elements <= 800
    assert metrics.tables == 2
    assert metrics.scripts == 2
    assert metrics.premature_close_found is True
    assert metrics.characters_after_first_html_close > 1_600_000
    assert first.decoded.text.index("PREÂMBULO") < first_close
    assert first.decoded.text.index("Art. 250") > first_close
    assert "ATO DAS DISPOSIÇÕES CONSTITUCIONAIS TRANSITÓRIAS" in visible_text
    assert first.decoded.text.rindex("Art. 138") > first_close
    assert first.metrics == second.metrics
    assert first.decoded.text == second.decoded.text
    assert counts_before == counts_after
    assert segments.leading_blocks[0].block_index == 1
    assert segments.cf_blocks[0].normalized_text_for_matching == "preâmbulo"
    assert segments.cf_blocks[-1].normalized_text_for_matching.startswith("art. 250")
    assert segments.adct_blocks[0].normalized_text_for_matching == (
        "ato das disposições constitucionais transitórias"
    )
    assert segments.adct_blocks[-1].normalized_text_for_matching.startswith("art. 138")
    all_segmented = (
        segments.leading_blocks
        + segments.cf_blocks
        + segments.transition_blocks
        + segments.adct_blocks
        + segments.trailing_blocks
    )
    assert all_segmented == projection.blocks
    assert parsed.cf88.fingerprint_sha256 == reparsed.cf88.fingerprint_sha256
    assert parsed.adct.fingerprint_sha256 == reparsed.adct.fingerprint_sha256
    assert audit.fingerprint_sha256 == reaudit.fingerprint_sha256
    assert not [
        item
        for act_audit in (audit.cf88, audit.adct)
        for item in act_audit.unclassified_blocks
        if item.diagnostic_kind == "PARSER_MISSED_STRUCTURE"
    ]
    assert all(
        act_audit.coverage["blocks_without_audit_record"] == 0
        for act_audit in (audit.cf88, audit.adct)
    )
    assert audit.adct.strike_status_matrix["FULLY_STRUCK"].get("CURRENT", 0) == 0
    assert audit.gate.value == "APPROVED_FOR_MATERIALIZATION"
    assert not [item for item in audit.findings if item.severity == "BLOCKER"]
    assert len(parsed.cf88.provisions) > 3_000
    assert len(parsed.adct.provisions) > 900
    cf_labels = {
        item.number_label
        for item in _walk(parsed.cf88.root)
        if item.element_type.value == "ARTICLE"
    }
    adct_labels = {
        item.number_label
        for item in _walk(parsed.adct.root)
        if item.element_type.value == "ARTICLE"
    }
    assert {"1", "5", "12", "60", "250"} <= cf_labels
    assert {"1", "60", "116-A", "117", "134", "138"} <= adct_labels
    assert parsed.cf88.coverage.total_blocks == len(segments.cf_blocks)
    assert parsed.adct.coverage.total_blocks == len(segments.adct_blocks)

    print(f"document_id={document.id}")
    print(f"sha256={first.decoded.content_hash_sha256}")
    print(f"encoding={first.decoded.encoding}")
    print(f"metrics={metrics}")
    print(f"blocks={len(projection.blocks)}")
    print(f"blocks_fingerprint={projection.fingerprint_sha256}")
    print(
        "segment_sizes="
        f"leading:{len(segments.leading_blocks)},"
        f"cf:{len(segments.cf_blocks)},"
        f"transition:{len(segments.transition_blocks)},"
        f"adct:{len(segments.adct_blocks)},"
        f"trailing:{len(segments.trailing_blocks)}"
    )
    print(f"blocks_ms={projection.enumeration_duration_ms:.3f}")
    print(f"segmentation_ms={segments.segmentation_duration_ms:.3f}")
    print(f"cf_legal_metrics={parsed_act_metrics(parsed.cf88)}")
    print(f"adct_legal_metrics={parsed_act_metrics(parsed.adct)}")
    print(f"cf_coverage={_coverage_summary(parsed.cf88.coverage)}")
    print(f"adct_coverage={_coverage_summary(parsed.adct.coverage)}")
    print(f"legal_parsing_ms={parsed.parsing_duration_ms:.3f}")
    print(f"audit_gate={audit.gate}")
    print(f"audit_fingerprint={audit.fingerprint_sha256}")
    print(f"audit_ms={audit_ms:.3f}")
    print(
        "audit_findings="
        f"info:{sum(item.severity == 'INFO' for item in audit.findings)},"
        f"warning:{sum(item.severity == 'WARNING' for item in audit.findings)},"
        f"blocker:{sum(item.severity == 'BLOCKER' for item in audit.findings)}"
    )
    print(f"cf_duplicate_groups={len(audit.cf88.duplicate_groups)}")
    print(f"adct_duplicate_groups={len(audit.adct.duplicate_groups)}")
    for act_audit in (audit.cf88, audit.adct):
        unclassified_kinds = Counter(
            item.diagnostic_kind for item in act_audit.unclassified_blocks
        )
        print(
            f"{act_audit.act}_unique_article_labels={act_audit.unique_article_labels}"
        )
        print(f"{act_audit.act}_duplicate_labels={act_audit.duplicate_labels}")
        print(
            f"{act_audit.act}_duplicate_kinds="
            f"{dict(Counter(item.kind for item in act_audit.duplicate_groups))}"
        )
        print(f"{act_audit.act}_unclassified_kinds={dict(unclassified_kinds)}")
        print(f"{act_audit.act}_unresolved_by_type={act_audit.unresolved_by_type}")
        print(f"{act_audit.act}_unresolved_by_cause={act_audit.unresolved_by_cause}")
        print(f"{act_audit.act}_historical_by_type={act_audit.historical_by_type}")
        print(f"{act_audit.act}_revoked_by_type={act_audit.revoked_by_type}")
        print(f"{act_audit.act}_strike_status={act_audit.strike_status_matrix}")
        print(f"{act_audit.act}_notes_by_role={act_audit.notes_by_role}")
        print(f"{act_audit.act}_notes_by_parent={act_audit.notes_by_parent_type}")
        print(
            f"{act_audit.act}_note_outliers="
            f"{list(act_audit.notes_by_article.items())[:10]}"
        )
        print(f"{act_audit.act}_elements_per_block={act_audit.elements_per_block}")
        print(f"{act_audit.act}_unusual_reuse={act_audit.unusual_block_reuse}")
        print(f"{act_audit.act}_parent_child={act_audit.parent_child_matrix}")
        print(f"{act_audit.act}_depth_distribution={act_audit.depth_distribution}")
        print(f"{act_audit.act}_max_depth_path={act_audit.maximum_depth_path}")
        print(f"{act_audit.act}_provenance={act_audit.provenance}")
        print(f"{act_audit.act}_alphanumeric={act_audit.alphanumeric_article_labels}")
    blocker_codes = Counter(
        item.code for item in audit.findings if item.severity == "BLOCKER"
    )
    warning_codes = Counter(
        item.code for item in audit.findings if item.severity == "WARNING"
    )
    print(f"audit_blocker_codes={dict(blocker_codes)}")
    print(f"audit_warning_codes={dict(warning_codes)}")
    print(
        "cf_sentinels="
        f"{article_audit_projection(parsed.cf88, ('1', '5', '6', '12', '60', '250'))}"
    )
    adct_sentinel_labels = (
        "1",
        "60",
        "116-A",
        "117",
        "134",
        "135",
        "136",
        "137",
        "138",
    )
    print(
        f"adct_sentinels={article_audit_projection(parsed.adct, adct_sentinel_labels)}"
    )
    print(f"decode_ms={first.decoded.decoding_duration_ms:.3f}")
    print(f"dom_ms={first.dom_build_duration_ms:.3f}")
    print(f"total_elapsed_ms={elapsed_ms:.3f}")


def _derived_counts(session) -> tuple[int, int, int, int]:
    return (
        session.scalar(select(func.count()).select_from(ParsingRun)),
        session.scalar(select(func.count()).select_from(LegalVersion)),
        session.scalar(select(func.count()).select_from(LegalProvision)),
        session.scalar(select(func.count()).select_from(LegalElement)),
    )


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _coverage_summary(report):
    return {
        "total_blocks": report.total_blocks,
        "consumed_blocks": report.consumed_blocks,
        "ignored_blocks": report.ignored_blocks,
        "coverage_ratio": report.coverage_ratio,
        "ignored_by_reason": report.ignored_by_reason,
    }
