"""Materialização transacional do parsing constitucional auditado."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import func, null, select
from sqlalchemy.orm import Session

from consultor_juridico.models import (
    LegalAct,
    LegalElement,
    LegalProvision,
    LegalVersion,
    ParsingRun,
    SourceDocument,
)
from consultor_juridico.parsing.audit import audit_parsed_constitution
from consultor_juridico.parsing.audit_types import MaterializationGate
from consultor_juridico.parsing.blocks import enumerate_document_blocks
from consultor_juridico.parsing.decoder import decode_source_document
from consultor_juridico.parsing.dom import build_dom
from consultor_juridico.parsing.legal_parser import parse_constitution
from consultor_juridico.parsing.legal_types import ParsedLegalAct, ParsedLegalElement
from consultor_juridico.parsing.segmentation import segment_constitution_document

PARSER_NAME = "planalto_constitution"
PARSER_VERSION = "identity-v1"


class ParsingOutcome(StrEnum):
    CREATED = "CREATED"
    ALREADY_PARSED = "ALREADY_PARSED"


class ParsingInProgressError(RuntimeError):
    """Indica processamento lógico já iniciado e ainda não concluído."""


class MaterializationGateError(RuntimeError):
    """Impede persistência quando a auditoria estrutural não aprovou a árvore."""


@dataclass(frozen=True, slots=True)
class MaterializationResult:
    outcome: ParsingOutcome
    parsing_run_id: UUID
    source_document_id: UUID
    legal_version_ids: tuple[UUID, ...]
    provision_count: int
    element_count: int
    audit_fingerprint: str | None


def materialization_status(session: Session) -> dict[str, int | str | None]:
    """Resume o estado persistido sem alterar o banco."""
    counts: dict[str, int | str | None] = {}
    for name, model in (
        ("parsing_runs", ParsingRun),
        ("legal_acts", LegalAct),
        ("legal_versions", LegalVersion),
        ("legal_provisions", LegalProvision),
        ("legal_elements", LegalElement),
    ):
        counts[name] = int(session.scalar(select(func.count()).select_from(model)) or 0)
    completed = session.scalar(
        select(ParsingRun)
        .where(ParsingRun.status == "COMPLETED")
        .order_by(ParsingRun.finished_at.desc())
    )
    counts["latest_status"] = completed.status if completed else None
    counts["audit_fingerprint"] = (
        (completed.metadata_json or {}).get("audit_fingerprint") if completed else None
    )
    return counts


def materialize_constitution(
    session: Session,
    source_document_id: UUID,
    *,
    before_complete: Callable[[Session], None] | None = None,
) -> MaterializationResult:
    """Executa TX1, parsing em memória, TX2 atômica e TX3 em caso de falha."""
    document = session.get(SourceDocument, source_document_id)
    if document is None:
        raise LookupError(f"SourceDocument não encontrado: {source_document_id}")

    parsing_run = session.scalar(
        select(ParsingRun).where(
            ParsingRun.source_document_id == source_document_id,
            ParsingRun.parser_name == PARSER_NAME,
            ParsingRun.parser_version == PARSER_VERSION,
        )
    )
    if parsing_run is not None and parsing_run.status == "COMPLETED":
        versions = tuple(parsing_run.legal_versions)
        return MaterializationResult(
            ParsingOutcome.ALREADY_PARSED,
            parsing_run.id,
            source_document_id,
            tuple(item.id for item in versions),
            _run_provision_count(session, versions),
            sum(len(item.elements) for item in versions),
            (parsing_run.metadata_json or {}).get("audit_fingerprint"),
        )
    if parsing_run is not None and parsing_run.status == "RUNNING":
        raise ParsingInProgressError(f"ParsingRun em andamento: {parsing_run.id}")

    # TX1 — registra o início lógico independentemente da materialização.
    if parsing_run is None:
        parsing_run = ParsingRun(
            source_document_id=source_document_id,
            parser_name=PARSER_NAME,
            parser_version=PARSER_VERSION,
        )
        session.add(parsing_run)
    else:
        parsing_run.status = "RUNNING"
        parsing_run.started_at = datetime.now(UTC)
        parsing_run.finished_at = None
        parsing_run.metadata_json = None
    session.commit()
    run_id = parsing_run.id

    try:
        decoded = decode_source_document(document)
        dom = build_dom(decoded)
        projection = enumerate_document_blocks(dom)
        segments = segment_constitution_document(projection.blocks)
        parsed = parse_constitution(segments)
        audit = audit_parsed_constitution(parsed.cf88, parsed.adct, segments)
        if audit.gate != MaterializationGate.APPROVED:
            blockers = [
                item.code for item in audit.findings if item.severity == "BLOCKER"
            ]
            raise MaterializationGateError(
                f"Gate bloqueado; findings BLOCKER: {blockers}"
            )

        # TX2 — as duas versões, identities e occurrences tornam-se visíveis juntas.
        acts = {
            "CF88": _get_or_create_act(
                session,
                "CF/88",
                "Constituição Federal de 1988",
                "CONSTITUICAO",
            ),
            "ADCT": _get_or_create_act(
                session,
                "ADCT",
                "Ato das Disposições Constitucionais Transitórias",
                "ADCT",
            ),
        }
        versions: list[LegalVersion] = []
        provision_total = 0
        element_total = 0
        for parsed_act in (parsed.cf88, parsed.adct):
            act = acts[parsed_act.act_code]
            version = LegalVersion(
                legal_act_id=act.id,
                source_document_id=source_document_id,
                parsing_run_id=run_id,
                version_label=f"{parsed_act.act_code}-{document.content_hash_sha256[:12]}",
                is_active_for_query=False,
                metadata_json={
                    "parser_name": PARSER_NAME,
                    "parser_version": PARSER_VERSION,
                    "tree_fingerprint": parsed_act.fingerprint_sha256,
                },
            )
            session.add(version)
            session.flush()
            provision_by_key = _reconcile_provisions(session, act, parsed_act)
            provision_total += len(provision_by_key)
            element_total += _persist_occurrences(
                session, version, act, parsed_act.root, provision_by_key
            )
            versions.append(version)

        for act in acts.values():
            session.execute(
                LegalVersion.__table__.update()
                .where(
                    LegalVersion.legal_act_id == act.id,
                    LegalVersion.is_active_for_query.is_(True),
                    LegalVersion.parsing_run_id != run_id,
                )
                .values(is_active_for_query=False)
            )
        for version in versions:
            version.is_active_for_query = True
        if before_complete is not None:
            before_complete(session)
        parsing_run = session.get(ParsingRun, run_id)
        assert parsing_run is not None
        parsing_run.status = "COMPLETED"
        parsing_run.finished_at = datetime.now(UTC)
        parsing_run.metadata_json = {
            "audit_fingerprint": audit.fingerprint_sha256,
            "cf88_tree_fingerprint": parsed.cf88.fingerprint_sha256,
            "adct_tree_fingerprint": parsed.adct.fingerprint_sha256,
            "block_fingerprint": projection.fingerprint_sha256,
        }
        session.commit()
        return MaterializationResult(
            ParsingOutcome.CREATED,
            run_id,
            source_document_id,
            tuple(item.id for item in versions),
            provision_total,
            element_total,
            audit.fingerprint_sha256,
        )
    except Exception:
        session.rollback()
        # TX3 — somente o estado lógico FAILED sobrevive.
        failed = session.get(ParsingRun, run_id)
        if failed is not None:
            failed.status = "FAILED"
            failed.finished_at = datetime.now(UTC)
            session.commit()
        raise


def _get_or_create_act(
    session: Session, short_name: str, title: str, act_type: str
) -> LegalAct:
    act = session.scalar(select(LegalAct).where(LegalAct.short_name == short_name))
    if act is None:
        act = LegalAct(title=title, short_name=short_name, act_type=act_type)
        session.add(act)
        session.flush()
    return act


def _reconcile_provisions(
    session: Session, act: LegalAct, parsed: ParsedLegalAct
) -> dict[str, LegalProvision]:
    existing = {
        item.identity_key: item
        for item in session.scalars(
            select(LegalProvision).where(LegalProvision.legal_act_id == act.id)
        )
    }
    result: dict[str, LegalProvision] = {}
    for candidate in parsed.provisions:
        provision = existing.get(candidate.identity_key)
        if provision is not None:
            if (
                provision.element_type != candidate.element_type.value
                or provision.number_label != candidate.number_label
            ):
                raise MaterializationGateError(
                    f"Conflito de identidade persistida: {candidate.identity_key}"
                )
        else:
            parent = (
                result[candidate.parent_identity_key]
                if candidate.parent_identity_key is not None
                else None
            )
            provision = LegalProvision(
                legal_act_id=act.id,
                parent_id=parent.id if parent else None,
                element_type=candidate.element_type.value,
                number_label=candidate.number_label,
                identity_key=candidate.identity_key,
            )
            session.add(provision)
            session.flush()
            existing[candidate.identity_key] = provision
        result[candidate.identity_key] = provision
    return result


def _persist_occurrences(
    session: Session,
    version: LegalVersion,
    act: LegalAct,
    root: ParsedLegalElement,
    provision_by_key: dict[str, LegalProvision],
) -> int:
    count = 0

    def persist(node: ParsedLegalElement, parent: LegalElement | None) -> None:
        nonlocal count
        provision = provision_by_key.get(node.identity_key or "")
        element = LegalElement(
            legal_version_id=version.id,
            legal_act_id=act.id,
            legal_provision_id=provision.id if provision else None,
            parent_id=parent.id if parent else None,
            element_type=node.element_type.value,
            number_label=node.number_label,
            document_order=node.document_order,
            raw_text=node.raw_text,
            normalized_text=node.normalized_text,
            text_status=node.text_status.value,
            content_role=node.content_role.value,
            path=node.identity_key,
            source_locator=node.source_locator,
            parser_metadata=(
                node.parser_metadata if node.parser_metadata is not None else null()
            ),
        )
        session.add(element)
        session.flush()
        count += 1
        for child in node.children:
            persist(child, element)

    persist(root, None)
    return count


def _run_provision_count(session: Session, versions: tuple[LegalVersion, ...]) -> int:
    act_ids = {item.legal_act_id for item in versions}
    if not act_ids:
        return 0
    return int(
        session.scalar(
            select(func.count())
            .select_from(LegalProvision)
            .where(LegalProvision.legal_act_id.in_(act_ids))
        )
        or 0
    )
