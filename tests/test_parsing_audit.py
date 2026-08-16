"""Testes da auditoria estrutural pré-materialização."""

import hashlib
import uuid
from dataclasses import replace
from pathlib import Path

from consultor_juridico.parsing import (
    AuditSeverity,
    ElementType,
    MaterializationGate,
    TextStatus,
    audit_parsed_constitution,
    build_dom,
    decode_raw_document,
    enumerate_document_blocks,
    normalize_legal_text,
    parse_constitution,
    segment_constitution_document,
)

FIXTURES = Path(__file__).parent / "fixtures/parsing"


def _pipeline(cf: str, adct: str):
    html = (
        "<p>PREÂMBULO</p><p>Texto preambular.</p>"
        f"{cf}<p>Art. 250. Fecho.</p><p>Assinaturas</p>"
        "<p>ATO DAS DISPOSIÇÕES CONSTITUCIONAIS TRANSITÓRIAS</p>"
        f"{adct}<p>Art. 138. Fecho.</p>"
    )
    payload = html.encode("windows-1252")
    decoded = decode_raw_document(
        source_document_id=uuid.uuid4(),
        raw_bytes=payload,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )
    blocks = enumerate_document_blocks(build_dom(decoded)).blocks
    segments = segment_constitution_document(blocks)
    parsed = parse_constitution(segments)
    return parsed, segments


def _audit(cf: str = "<p>Art. 1º Texto.</p>", adct: str = "<p>Art. 1º ADCT.</p>"):
    parsed, segments = _pipeline(cf, adct)
    return audit_parsed_constitution(parsed.cf88, parsed.adct, segments)


def test_valid_structure_is_approved_and_deterministic():
    parsed, segments = _pipeline("<p>Art. 1º Texto.</p>", "<p>Art. 1º ADCT.</p>")
    first = audit_parsed_constitution(parsed.cf88, parsed.adct, segments)
    second = audit_parsed_constitution(parsed.cf88, parsed.adct, segments)
    assert first.gate == MaterializationGate.APPROVED
    assert first.fingerprint_sha256 == second.fingerprint_sha256
    assert not [
        item for item in first.findings if item.severity == AuditSeverity.BLOCKER
    ]


def test_historical_article_occurrences_share_identity_and_are_approved():
    html = (FIXTURES / "correction_01_multiple_redactions.html").read_text()
    report = _audit(html)
    assert report.gate == MaterializationGate.APPROVED
    assert report.cf88.duplicate_labels == ("6",)
    assert report.cf88.duplicate_groups[0].kind == (
        "SAME_LEGAL_DEVICE_HISTORICAL_REDACTION"
    )
    assert any(
        item.code == "HISTORICAL_OCCURRENCES_RECONCILED"
        for item in report.cf88.findings
    )
    statuses = {
        occurrence.caput_status
        for occurrence in report.cf88.duplicate_groups[0].occurrences
    }
    assert statuses == {TextStatus.UNRESOLVED, TextStatus.CURRENT}


def test_true_current_duplicate_remains_a_structural_ambiguity():
    html = (FIXTURES / "correction_03_true_duplicate.html").read_text()
    report = _audit(html)
    assert report.cf88.duplicate_groups[0].kind == "STRUCTURAL_AMBIGUITY"
    assert any(
        item.code == "DUPLICATE_ARTICLE_STRUCTURAL_KEY" for item in report.cf88.findings
    )


def test_alternative_historical_rubric_is_reconciled():
    html = (FIXTURES / "correction_08_historical_rubric.html").read_text()
    report = _audit(html)
    assert not report.cf88.unclassified_blocks
    assert report.gate == MaterializationGate.APPROVED


def test_article_caput_order_hierarchy_and_provenance_are_audited():
    report = _audit(
        "<p>Art. 12. Texto.</p><p>§ 1º Regra.</p><p>I - inciso.</p>"
        "<p>a) alínea.</p><p>1. item.</p>"
    )
    act = report.cf88
    assert act.article_caput_anomalies == 0
    assert act.parent_child_matrix["ARTICLE → CAPUT"] >= 1
    assert act.parent_child_matrix["ALINEA → ITEM"] == 1
    assert act.provenance["synthetic_structure"] >= act.total_articles + 1
    assert not any(item.code == "DOCUMENT_ORDER_INVALID" for item in act.findings)


def test_unclassified_block_has_explicit_diagnostic_category_and_complete_coverage():
    report = _audit("<p>Bloco estranho que exige revisão.</p><p>Art. 1º Texto.</p>")
    act = report.cf88
    assert act.unclassified_blocks[0].diagnostic_kind == "REQUIRES_REVIEW"
    assert act.coverage["blocks_without_audit_record"] == 0
    assert act.coverage["total_blocks"] == (
        act.coverage["consumed_blocks"] + act.coverage["ignored_blocks"]
    )


def test_unresolved_and_strike_status_matrix_are_explained():
    report = _audit("<p>Art. 1º Texto <strike>parcial</strike>.</p>")
    assert report.cf88.unresolved_by_cause == {"PARTIAL_STRIKE": 2}
    assert report.cf88.strike_status_matrix["PARTIALLY_STRUCK"]["UNRESOLVED"] == 2
    assert any(item.code == "UNRESOLVED_PRESERVED" for item in report.findings)


def test_notes_roles_parent_and_legitimate_block_reuse_are_audited():
    report = _audit(
        "<p>Art. 1º Texto. (Redação dada pela Emenda Constitucional nº 1) "
        "(Vide Lei nº 1)</p>"
    )
    act = report.cf88
    assert act.notes_by_role == {"AMENDMENT_NOTE": 1, "REFERENCE_NOTE": 1}
    assert act.notes_by_parent_type == {"CAPUT": 2}
    assert not act.unusual_block_reuse
    assert act.elements_per_block["4+"] == 1


def test_revoked_without_textual_evidence_is_a_blocker():
    parsed, segments = _pipeline("<p>Art. 1º Texto.</p>", "<p>Art. 1º ADCT.</p>")
    article = next(
        child
        for child in parsed.cf88.root.children
        if child.element_type == ElementType.ARTICLE
    )
    bad_caput = replace(article.children[0], text_status=TextStatus.REVOKED)
    bad_article = replace(article, children=(bad_caput,))
    bad_root = replace(
        parsed.cf88.root,
        children=tuple(
            bad_article if child is article else child
            for child in parsed.cf88.root.children
        ),
    )
    bad_act = replace(parsed.cf88, root=bad_root)
    report = audit_parsed_constitution(bad_act, parsed.adct, segments)
    assert report.gate == MaterializationGate.BLOCKED
    assert any(
        item.code == "REVOKED_WITHOUT_TEXTUAL_EVIDENCE"
        and item.severity == AuditSeverity.BLOCKER
        for item in report.findings
    )


def test_act_identity_and_alphanumeric_labels_are_distinct():
    report = _audit(
        "<p>Art. 1º CF.</p>",
        "<p>Art. 1º ADCT.</p><p>Art. 116-A. Dispositivo.</p>",
    )
    assert report.cf88.act == "CF88"
    assert report.adct.act == "ADCT"
    assert report.adct.alphanumeric_article_labels == ("116-A",)


def test_normalization_is_conservative_and_deterministic():
    raw = "  Constituição\r\n\u00a0CIDADÃ: ação.  "
    assert normalize_legal_text(raw) == "Constituição CIDADÃ: ação."
