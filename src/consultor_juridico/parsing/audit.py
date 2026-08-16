"""Auditoria determinística do resultado jurídico antes da materialização."""

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from typing import Any

from consultor_juridico.parsing.audit_types import (
    ActAudit,
    ArticleDuplicateKind,
    ArticleOccurrence,
    AuditFinding,
    AuditSeverity,
    DuplicateArticleGroup,
    MaterializationGate,
    StructuralAuditReport,
    UnclassifiedBlockAudit,
    UnclassifiedBlockKind,
)
from consultor_juridico.parsing.blocks import DocumentBlock
from consultor_juridico.parsing.legal_types import (
    ContentRole,
    CoverageDisposition,
    ElementType,
    ParsedLegalAct,
    ParsedLegalElement,
    TextStatus,
)
from consultor_juridico.parsing.segmentation import ConstitutionDocumentSegments


def audit_parsed_constitution(
    cf88: ParsedLegalAct,
    adct: ParsedLegalAct,
    segments: ConstitutionDocumentSegments,
) -> StructuralAuditReport:
    """Audita as árvores sem modificá-las e calcula o gate formal."""
    cf_audit = _audit_act(cf88, segments.cf_blocks)
    adct_audit = _audit_act(adct, segments.adct_blocks)
    findings = tuple(
        sorted(
            (*cf_audit.findings, *adct_audit.findings),
            key=_finding_key,
        )
    )
    gate = (
        MaterializationGate.BLOCKED
        if any(item.severity == AuditSeverity.BLOCKER for item in findings)
        else MaterializationGate.APPROVED
    )
    payload = {
        "cf88": _stable_act_payload(cf_audit),
        "adct": _stable_act_payload(adct_audit),
        "findings": [asdict(item) for item in findings],
        "gate": gate,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return StructuralAuditReport(cf_audit, adct_audit, findings, gate, fingerprint)


def article_audit_projection(
    act: ParsedLegalAct,
    labels: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    """Produz projeção compacta de artigos escolhidos para inspeção humana."""
    result = []
    for element, ancestry in _walk(act.root):
        if (
            element.element_type != ElementType.ARTICLE
            or element.number_label not in labels
        ):
            continue
        descendants = Counter(
            item.element_type.value
            for child in element.children
            for item, _ in _walk(child)
        )
        caput = next(
            child
            for child in element.children
            if child.element_type == ElementType.CAPUT
        )
        result.append(
            {
                "act": act.act_code,
                "number_label": element.number_label,
                "document_order": element.document_order,
                "block_index": element.source_locator["block_index"],
                "caput_status": caput.text_status,
                "content_role": caput.content_role,
                "ancestry": [
                    f"{item.element_type.value}:{item.number_label or item.raw_text}"
                    for item in ancestry
                ],
                "descendants_by_type": dict(sorted(descendants.items())),
            }
        )
    return tuple(result)


def _audit_act(act: ParsedLegalAct, blocks: tuple[DocumentBlock, ...]) -> ActAudit:
    records = tuple(_walk(act.root))
    by_block: dict[
        int, list[tuple[ParsedLegalElement, tuple[ParsedLegalElement, ...]]]
    ] = defaultdict(list)
    parent_child = Counter[str]()
    depth_counts = Counter[str]()
    notes_by_parent = Counter[str]()
    notes_by_article = Counter[str]()
    max_path: tuple[ParsedLegalElement, ...] = ()
    findings: list[AuditFinding] = []

    for element, ancestry in records:
        block_index = element.source_locator.get("block_index")
        if isinstance(block_index, int):
            by_block[block_index].append((element, ancestry))
        depth = len(ancestry) + 1
        depth_counts[str(depth)] += 1
        if depth > len(max_path):
            max_path = (*ancestry, element)
        if ancestry:
            parent_child[
                f"{ancestry[-1].element_type.value} → {element.element_type.value}"
            ] += 1
        if element.element_type == ElementType.NOTE:
            parent_type = ancestry[-1].element_type.value if ancestry else "NONE"
            notes_by_parent[parent_type] += 1
            article = _article_ancestor(ancestry)
            notes_by_article[article.number_label if article else "NO_ARTICLE"] += 1

    articles = [item for item, _ in records if item.element_type == ElementType.ARTICLE]
    occurrences = _article_occurrences(act.act_code, records)
    duplicate_groups = _duplicate_groups(occurrences)
    for group in duplicate_groups:
        severity = (
            AuditSeverity.INFO
            if group.kind == ArticleDuplicateKind.SAME_LEGAL_DEVICE_HISTORICAL_REDACTION
            else AuditSeverity.BLOCKER
        )
        findings.append(
            AuditFinding(
                (
                    "HISTORICAL_OCCURRENCES_RECONCILED"
                    if group.kind
                    == ArticleDuplicateKind.SAME_LEGAL_DEVICE_HISTORICAL_REDACTION
                    else "DUPLICATE_ARTICLE_STRUCTURAL_KEY"
                ),
                severity,
                act.act_code,
                ElementType.ARTICLE,
                group.number_label,
                group.occurrences[0].block_index,
                (
                    "Redações documentais distintas apontam para uma identidade "
                    "normativa compartilhada."
                    if group.kind
                    == ArticleDuplicateKind.SAME_LEGAL_DEVICE_HISTORICAL_REDACTION
                    else "Ocorrências de ARTICLE compartilham a mesma chave estrutural."
                ),
                {
                    "kind": group.kind,
                    "occurrence_count": len(group.occurrences),
                    "document_orders": [
                        item.document_order for item in group.occurrences
                    ],
                    "block_indices": [item.block_index for item in group.occurrences],
                    "statuses": [item.caput_status for item in group.occurrences],
                },
            )
        )

    caput_anomalies = _article_caput_findings(act.act_code, records, findings)
    _identity_findings(act, records, findings)
    _order_findings(act.act_code, records, findings)
    _provenance_findings(act.act_code, records, blocks, findings)
    _hierarchy_findings(act.act_code, records, findings)
    _note_findings(act.act_code, records, by_block, findings)
    _revoked_findings(act.act_code, records, blocks, findings)

    unclassified = tuple(
        _unclassified_audit(act.act_code, blocks_by_index[entry.block_index])
        for entry in act.coverage.entries
        if entry.disposition == CoverageDisposition.IGNORED_WITH_REASON
        for blocks_by_index in ({block.block_index: block for block in blocks},)
    )
    for item in unclassified:
        severity = (
            AuditSeverity.BLOCKER
            if item.diagnostic_kind
            in {
                UnclassifiedBlockKind.PARSER_MISSED_STRUCTURE,
                UnclassifiedBlockKind.HISTORICAL_RUBRIC_MODEL_GAP,
            }
            else AuditSeverity.WARNING
            if item.diagnostic_kind == UnclassifiedBlockKind.REQUIRES_REVIEW
            else AuditSeverity.INFO
        )
        findings.append(
            AuditFinding(
                "IGNORED_BLOCK_DIAGNOSED",
                severity,
                act.act_code,
                None,
                None,
                item.block_index,
                f"Bloco ignorado classificado como {item.diagnostic_kind}.",
                {"text": item.normalized_text[:240]},
            )
        )

    unresolved = [
        item for item, _ in records if item.text_status == TextStatus.UNRESOLVED
    ]
    unresolved_causes = Counter(_unresolved_cause(item) for item in unresolved)
    if unresolved:
        findings.append(
            AuditFinding(
                "UNRESOLVED_PRESERVED",
                AuditSeverity.WARNING,
                act.act_code,
                None,
                None,
                None,
                "Incertezas editoriais foram preservadas explicitamente.",
                {
                    "count": len(unresolved),
                    "causes": dict(sorted(unresolved_causes.items())),
                },
            )
        )

    reuse_counts = Counter(
        str(len(items)) if len(items) < 4 else "4+" for items in by_block.values()
    )
    unusual_reuse = tuple(
        sorted(
            block_index
            for block_index, items in by_block.items()
            if not _expected_block_reuse(tuple(element for element, _ in items))
        )
    )
    for block_index in unusual_reuse:
        findings.append(
            AuditFinding(
                "UNUSUAL_BLOCK_REUSE",
                AuditSeverity.WARNING,
                act.act_code,
                None,
                None,
                block_index,
                "Bloco originou combinação incomum de elementos; requer inspeção.",
                {"types": [item.element_type for item, _ in by_block[block_index]]},
            )
        )

    provenance = Counter(
        {
            "source_line_missing": sum(
                item.source_locator.get("source_line") is None for item, _ in records
            ),
            "anchors_empty": sum(
                not item.source_locator.get("anchors") for item, _ in records
            ),
            "links_present": sum(
                bool((item.parser_metadata or {}).get("links")) for item, _ in records
            ),
            "synthetic_structure": sum(
                bool((item.parser_metadata or {}).get("synthetic_structure"))
                for item, _ in records
            ),
        }
    )
    strike_matrix = _strike_status_matrix(records, blocks)
    coverage = {
        "total_blocks": act.coverage.total_blocks,
        "consumed_blocks": act.coverage.consumed_blocks,
        "ignored_blocks": act.coverage.ignored_blocks,
        "coverage_ratio": act.coverage.coverage_ratio,
        "ignored_by_reason": act.coverage.ignored_by_reason,
        "unclassified_blocks": len(unclassified),
        "blocks_consumed_multiple_times": sum(
            len(items) > 1 for items in by_block.values()
        ),
        "blocks_without_audit_record": len(blocks) - len(act.coverage.entries),
    }
    return ActAudit(
        act.act_code,
        len(records),
        len(articles),
        len({item.number_label for item in articles}),
        tuple(
            sorted(
                label
                for label, count in Counter(
                    item.number_label for item in articles
                ).items()
                if count > 1
            )
        ),
        duplicate_groups,
        caput_anomalies,
        unclassified,
        _status_by_type(records, TextStatus.UNRESOLVED),
        dict(sorted(unresolved_causes.items())),
        _status_by_type(records, TextStatus.HISTORICAL),
        _status_by_type(records, TextStatus.REVOKED),
        strike_matrix,
        dict(
            sorted(
                Counter(
                    item.content_role.value
                    for item, _ in records
                    if item.element_type == ElementType.NOTE
                ).items()
            )
        ),
        dict(sorted(notes_by_parent.items())),
        dict(sorted(notes_by_article.items(), key=lambda pair: (-pair[1], pair[0]))),
        dict(sorted(reuse_counts.items())),
        unusual_reuse,
        dict(sorted(parent_child.items())),
        dict(sorted(depth_counts.items(), key=lambda pair: int(pair[0]))),
        tuple(_path_entry(item) for item in max_path),
        coverage,
        dict(sorted(provenance.items())),
        tuple(
            sorted(
                {
                    item.number_label
                    for item in articles
                    if item.number_label and not item.number_label.isdigit()
                }
            )
        ),
        tuple(sorted(findings, key=_finding_key)),
    )


def _walk(
    node: ParsedLegalElement,
    ancestry: tuple[ParsedLegalElement, ...] = (),
):
    yield node, ancestry
    for child in node.children:
        yield from _walk(child, (*ancestry, node))


def _article_occurrences(
    act: str,
    records: tuple[tuple[ParsedLegalElement, tuple[ParsedLegalElement, ...]], ...],
) -> tuple[ArticleOccurrence, ...]:
    result = []
    for article, ancestry in records:
        if article.element_type != ElementType.ARTICLE:
            continue
        caput = next(
            child
            for child in article.children
            if child.element_type == ElementType.CAPUT
        )
        structural_ancestry = tuple(
            f"{item.element_type.value}:{item.number_label or item.raw_text}"
            for item in ancestry
            if item.element_type != ElementType.DOCUMENT_ROOT
        )
        key = article.identity_key or "/".join(
            (act, *structural_ancestry, f"ARTICLE:{article.number_label}")
        )
        result.append(
            ArticleOccurrence(
                act,
                article.number_label or "",
                key,
                article.document_order,
                int(article.source_locator["block_index"]),
                article.source_locator.get("source_line"),
                article.raw_text,
                caput.raw_text,
                caput.text_status,
                structural_ancestry,
                (article.parser_metadata or {}).get("classification_rule"),
            )
        )
    return tuple(result)


def _duplicate_groups(
    occurrences: tuple[ArticleOccurrence, ...],
) -> tuple[DuplicateArticleGroup, ...]:
    grouped: dict[str, list[ArticleOccurrence]] = defaultdict(list)
    for item in occurrences:
        grouped[item.structural_key].append(item)
    result = []
    for key, items in grouped.items():
        if len(items) < 2:
            continue
        statuses = {item.caput_status for item in items}
        if statuses & {
            TextStatus.HISTORICAL,
            TextStatus.REVOKED,
            TextStatus.UNRESOLVED,
        }:
            kind = ArticleDuplicateKind.SAME_LEGAL_DEVICE_HISTORICAL_REDACTION
        elif len({item.block_index for item in items}) < len(items):
            kind = ArticleDuplicateKind.PARSER_DUPLICATION
        else:
            kind = ArticleDuplicateKind.STRUCTURAL_AMBIGUITY
        result.append(
            DuplicateArticleGroup(
                items[0].act, items[0].number_label, key, kind, tuple(items)
            )
        )
    return tuple(
        sorted(result, key=lambda item: (item.number_label, item.structural_key))
    )


def _article_caput_findings(act: str, records, findings: list[AuditFinding]) -> int:
    anomalies = 0
    for article, _ in records:
        if article.element_type != ElementType.ARTICLE:
            continue
        caputs = [
            child
            for child in article.children
            if child.element_type == ElementType.CAPUT
        ]
        invalid = (
            len(caputs) != 1
            or not caputs[0].raw_text.strip()
            or not (caputs[0].parser_metadata or {}).get("synthetic_structure")
            or caputs[0].source_locator.get("block_index")
            != article.source_locator.get("block_index")
        )
        if invalid:
            anomalies += 1
            findings.append(
                AuditFinding(
                    "ARTICLE_CAPUT_INVALID",
                    AuditSeverity.BLOCKER,
                    act,
                    "ARTICLE",
                    article.number_label,
                    article.source_locator.get("block_index"),
                    "Contrato ARTICLE/CAPUT inválido.",
                    {"caput_count": len(caputs)},
                )
            )
    return anomalies


def _identity_findings(
    act: ParsedLegalAct,
    records: tuple[tuple[ParsedLegalElement, tuple[ParsedLegalElement, ...]], ...],
    findings: list[AuditFinding],
) -> None:
    provisions = {item.identity_key: item for item in act.provisions}
    current = Counter[str]()
    for item, ancestry in records:
        if item.element_type == ElementType.NOTE:
            if item.identity_key is not None:
                findings.append(
                    AuditFinding(
                        "NOTE_WITH_IDENTITY",
                        AuditSeverity.BLOCKER,
                        act.act_code,
                        item.element_type,
                        None,
                        item.source_locator.get("block_index"),
                        "NOTE não pode possuir identidade normativa.",
                        {},
                    )
                )
            continue
        provision = provisions.get(item.identity_key or "")
        if provision is None:
            findings.append(
                AuditFinding(
                    "UNMATCHED_NORMATIVE_OCCURRENCE",
                    AuditSeverity.BLOCKER,
                    act.act_code,
                    item.element_type,
                    item.number_label,
                    item.source_locator.get("block_index"),
                    "Ocorrência normativa sem provision reconciliado.",
                    {"identity_key": item.identity_key},
                )
            )
            continue
        if provision.element_type != item.element_type:
            findings.append(
                AuditFinding(
                    "ACT_OR_TYPE_IDENTITY_MISMATCH",
                    AuditSeverity.BLOCKER,
                    act.act_code,
                    item.element_type,
                    item.number_label,
                    item.source_locator.get("block_index"),
                    "Tipo da ocorrência diverge da identidade.",
                    {"identity_key": item.identity_key},
                )
            )
        expected_parent = next(
            (
                ancestor.identity_key
                for ancestor in reversed(ancestry)
                if ancestor.element_type != ElementType.NOTE
            ),
            None,
        )
        if provision.parent_identity_key != expected_parent:
            findings.append(
                AuditFinding(
                    "IDENTITY_PARENT_MISMATCH",
                    AuditSeverity.BLOCKER,
                    act.act_code,
                    item.element_type,
                    item.number_label,
                    item.source_locator.get("block_index"),
                    "Parent da ocorrência diverge da árvore de identidades.",
                    {"identity_key": item.identity_key},
                )
            )
        if item.text_status == TextStatus.CURRENT:
            current[item.identity_key or ""] += 1
    for identity_key, count in current.items():
        if count > 1:
            findings.append(
                AuditFinding(
                    "MULTIPLE_CURRENT_PER_VERSION_PROVISION",
                    AuditSeverity.BLOCKER,
                    act.act_code,
                    None,
                    None,
                    None,
                    "Mais de uma ocorrência CURRENT para a mesma identidade.",
                    {"identity_key": identity_key, "count": count},
                )
            )


def _order_findings(act: str, records, findings: list[AuditFinding]) -> None:
    orders = [item.document_order for item, _ in records]
    if orders != list(range(1, len(records) + 1)):
        findings.append(
            AuditFinding(
                "DOCUMENT_ORDER_INVALID",
                AuditSeverity.BLOCKER,
                act,
                None,
                None,
                None,
                "document_order não corresponde à pré-ordem contínua.",
                {"orders": orders[:20]},
            )
        )


def _provenance_findings(
    act: str, records, blocks, findings: list[AuditFinding]
) -> None:
    valid = {block.block_index for block in blocks}
    invalid = [
        item
        for item, _ in records
        if item.source_locator.get("block_index") not in valid
    ]
    if invalid:
        findings.append(
            AuditFinding(
                "PROVENANCE_INVALID",
                AuditSeverity.BLOCKER,
                act,
                None,
                None,
                None,
                "Elementos referenciam bloco fora do segmento.",
                {"count": len(invalid)},
            )
        )


def _hierarchy_findings(act: str, records, findings: list[AuditFinding]) -> None:
    allowed = {
        ("DOCUMENT_ROOT", "PREAMBLE"),
        ("DOCUMENT_ROOT", "TITLE"),
        ("DOCUMENT_ROOT", "CHAPTER"),
        ("DOCUMENT_ROOT", "SECTION"),
        ("DOCUMENT_ROOT", "SUBSECTION"),
        ("DOCUMENT_ROOT", "ARTICLE"),
        ("TITLE", "CHAPTER"),
        ("TITLE", "SECTION"),
        ("TITLE", "ARTICLE"),
        ("CHAPTER", "SECTION"),
        ("CHAPTER", "SUBSECTION"),
        ("CHAPTER", "ARTICLE"),
        ("SECTION", "SUBSECTION"),
        ("SECTION", "ARTICLE"),
        ("SUBSECTION", "ARTICLE"),
        ("ARTICLE", "CAPUT"),
        ("ARTICLE", "PARAGRAPH"),
        ("ARTICLE", "INCISO"),
        ("ARTICLE", "NOTE"),
        ("CAPUT", "NOTE"),
        ("PARAGRAPH", "INCISO"),
        ("PARAGRAPH", "NOTE"),
        ("INCISO", "ALINEA"),
        ("INCISO", "NOTE"),
        ("ALINEA", "ITEM"),
        ("ALINEA", "NOTE"),
        ("ITEM", "NOTE"),
        ("DOCUMENT_ROOT", "NOTE"),
        ("TITLE", "NOTE"),
        ("CHAPTER", "NOTE"),
        ("SECTION", "NOTE"),
        ("SUBSECTION", "NOTE"),
    }
    for item, ancestry in records:
        if not ancestry:
            continue
        edge = (ancestry[-1].element_type.value, item.element_type.value)
        if edge not in allowed:
            findings.append(
                AuditFinding(
                    "HIERARCHY_EDGE_UNEXPECTED",
                    AuditSeverity.BLOCKER,
                    act,
                    item.element_type,
                    item.number_label,
                    item.source_locator.get("block_index"),
                    f"Aresta hierárquica inesperada: {edge[0]} → {edge[1]}.",
                    {},
                )
            )


def _note_findings(act: str, records, by_block, findings: list[AuditFinding]) -> None:
    for note, ancestry in records:
        if note.element_type != ElementType.NOTE:
            continue
        invalid = (
            not note.raw_text.strip()
            or note.content_role == ContentRole.NORMATIVE
            or note.text_status != TextStatus.NOT_APPLICABLE
            or not ancestry
        )
        if invalid:
            findings.append(
                AuditFinding(
                    "NOTE_INVALID",
                    AuditSeverity.BLOCKER,
                    act,
                    "NOTE",
                    None,
                    note.source_locator.get("block_index"),
                    "NOTE viola role, status, texto ou hierarquia.",
                    {},
                )
            )
    for block_index, items in by_block.items():
        notes = [item for item, _ in items if item.element_type == ElementType.NOTE]
        duplicate_texts = [
            text
            for text, count in Counter(item.raw_text for item in notes).items()
            if count > 1
        ]
        if duplicate_texts:
            findings.append(
                AuditFinding(
                    "REPEATED_NOTE_TEXT_IN_SOURCE",
                    AuditSeverity.INFO,
                    act,
                    "NOTE",
                    None,
                    block_index,
                    "Texto de NOTE se repete factualmente no bloco de origem.",
                    {"texts": duplicate_texts},
                )
            )


def _revoked_findings(act: str, records, blocks, findings: list[AuditFinding]) -> None:
    by_index = {block.block_index: block for block in blocks}
    for item, _ in records:
        if item.text_status != TextStatus.REVOKED:
            continue
        block = by_index[int(item.source_locator["block_index"])]
        if not re.search(r"Revogad[oa]", block.text, re.I):
            findings.append(
                AuditFinding(
                    "REVOKED_WITHOUT_TEXTUAL_EVIDENCE",
                    AuditSeverity.BLOCKER,
                    act,
                    item.element_type,
                    item.number_label,
                    block.block_index,
                    "REVOKED sem marcador textual de revogação.",
                    {"contains_strike": block.contains_strike},
                )
            )


def _unclassified_audit(act: str, block: DocumentBlock) -> UnclassifiedBlockAudit:
    text = block.normalized_text_for_matching
    if not text:
        kind = UnclassifiedBlockKind.EMPTY_PRESENTATION
    elif re.match(r"^(?:do|da|dos|das)\s+", text):
        kind = UnclassifiedBlockKind.HISTORICAL_RUBRIC_MODEL_GAP
    elif re.match(
        r"^(?:art\.|§|parágrafo único|[ivxlcdm]+(?:-?[a-z])?\s+|[a-z]\s*\))",
        text,
        re.I,
    ) or re.match(
        r"^(?:título|capítulo|seção|subseção)\s+[ivxlcdm]+(?:-[a-z])?$",
        text,
        re.I,
    ):
        kind = UnclassifiedBlockKind.PARSER_MISSED_STRUCTURE
    elif re.search(
        r"este texto não substitui|publicad[oa] no dou|nota editorial", text
    ):
        kind = UnclassifiedBlockKind.EDITORIAL_NOTICE
    elif re.search(r"brasília|presidente|ministro|constituinte", text):
        kind = UnclassifiedBlockKind.SIGNATURE_BLOCK
    elif block.inside_table:
        kind = UnclassifiedBlockKind.NAVIGATION_ARTIFACT
    elif re.search(r"javascript|cookie|f5_|menu|voltar", text):
        kind = UnclassifiedBlockKind.TECHNICAL_ARTIFACT
    elif len(text) <= 3:
        kind = UnclassifiedBlockKind.EDITORIAL_SPACING
    else:
        kind = UnclassifiedBlockKind.REQUIRES_REVIEW
    return UnclassifiedBlockAudit(
        act,
        block.block_index,
        block.source_line,
        text[:500],
        block.anchors,
        block.contains_strike,
        block.inside_table,
        "unclassified_block",
        kind,
    )


def _unresolved_cause(item: ParsedLegalElement) -> str:
    coverage = (item.parser_metadata or {}).get("strike_coverage")
    if coverage == "partial":
        return "PARTIAL_STRIKE"
    if coverage == "full":
        return "FULL_STRIKE_WITHOUT_DECISIVE_MARKER"
    return "UNCLASSIFIED_STATUS_PATTERN"


def _strike_status_matrix(records, blocks) -> dict[str, dict[str, int]]:
    by_index = {block.block_index: block for block in blocks}
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    for item, _ in records:
        block = by_index[int(item.source_locator["block_index"])]
        state = (
            "FULLY_STRUCK"
            if block.fully_struck
            else "PARTIALLY_STRUCK"
            if block.partially_struck
            else "NO_STRIKE"
        )
        matrix[state][item.text_status.value] += 1
    return {
        state: dict(sorted(counts.items())) for state, counts in sorted(matrix.items())
    }


def _expected_block_reuse(elements: tuple[ParsedLegalElement, ...]) -> bool:
    types = Counter(item.element_type for item in elements)
    if len(elements) == 1:
        return True
    if types[ElementType.ARTICLE] == 1 and types[ElementType.CAPUT] == 1:
        return all(
            kind in {ElementType.ARTICLE, ElementType.CAPUT, ElementType.NOTE}
            for kind in types
        )
    if (
        sum(
            types[kind]
            for kind in {
                ElementType.PARAGRAPH,
                ElementType.INCISO,
                ElementType.ALINEA,
                ElementType.ITEM,
            }
        )
        == 1
    ):
        return all(
            kind
            in {
                ElementType.PARAGRAPH,
                ElementType.INCISO,
                ElementType.ALINEA,
                ElementType.ITEM,
                ElementType.NOTE,
            }
            for kind in types
        )
    return False


def _status_by_type(records, status: TextStatus) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                item.element_type.value
                for item, _ in records
                if item.text_status == status
            ).items()
        )
    )


def _article_ancestor(ancestry):
    return next(
        (
            item
            for item in reversed(ancestry)
            if item.element_type == ElementType.ARTICLE
        ),
        None,
    )


def _path_entry(item: ParsedLegalElement) -> dict[str, Any]:
    return {
        "element_type": item.element_type,
        "number_label": item.number_label,
        "document_order": item.document_order,
        "block_index": item.source_locator.get("block_index"),
    }


def _finding_key(item: AuditFinding):
    severity_order = {
        AuditSeverity.BLOCKER: 0,
        AuditSeverity.WARNING: 1,
        AuditSeverity.INFO: 2,
    }
    return (
        severity_order[item.severity],
        item.act,
        item.code,
        item.block_index or 0,
        item.number_label or "",
    )


def _stable_act_payload(act: ActAudit) -> dict[str, Any]:
    return asdict(act)
