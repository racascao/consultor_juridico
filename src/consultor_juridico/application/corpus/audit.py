"""Auditoria mecânica e rastreamento ponta a ponta do corpus."""

from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from consultor_juridico.domain.corpus import LegalActIdentity, VersionIdentity
from consultor_juridico.infrastructure.corpus.models import (
    ActVersionModel,
    LegalActModel,
    ProvisionModel,
    SearchUnitModel,
    SearchUnitProvisionModel,
    SourceModel,
    SourceSnapshotModel,
)


@dataclass(frozen=True, slots=True)
class AuditReport:
    passed: bool
    checks: dict[str, bool]
    provision_count: int
    search_unit_count: int


class CorpusAuditor:
    def __init__(self, session: Session, parser, projector) -> None:
        self._session = session
        self._parser = parser
        self._projector = projector

    def audit(self, version_hash: str, *, encoding: str) -> AuditReport:
        version = self._session.scalar(
            select(ActVersionModel).where(ActVersionModel.version_hash == version_hash)
        )
        if version is None:
            raise LookupError(f"ActVersion não encontrada: {version_hash}")
        act = self._session.get(LegalActModel, version.legal_act_id)
        snapshot = self._session.get(SourceSnapshotModel, version.source_snapshot_id)
        if act is None or snapshot is None:
            raise RuntimeError("Cadeia de proveniência incompleta")
        parsed = self._parser.parse(snapshot.raw_bytes, encoding=encoding)
        projected = self._projector.project(parsed)
        stored_provisions = tuple(
            self._session.scalars(
                select(ProvisionModel)
                .where(ProvisionModel.act_version_id == version.id)
                .order_by(ProvisionModel.document_order)
            )
        )
        stored_units = tuple(
            self._session.scalars(
                select(SearchUnitModel)
                .where(SearchUnitModel.act_version_id == version.id)
                .order_by(SearchUnitModel.unit_key)
            )
        )
        identity = VersionIdentity(
            LegalActIdentity(
                act.act_code,
                act.jurisdiction,
                act.act_type,
                act.number,
                act.year,
                act.title,
            ).natural_key,
            snapshot.sha256,
            version.parser_name,
            version.parser_version,
            version.projection_name,
            version.projection_version,
        )
        provision_ids = {item.id for item in stored_provisions}
        cross_parent = any(
            item.parent_id is not None and item.parent_id not in provision_ids
            for item in stored_provisions
        )
        links = tuple(
            self._session.execute(
                select(SearchUnitProvisionModel, SearchUnitModel, ProvisionModel)
                .join(
                    SearchUnitModel,
                    SearchUnitModel.id == SearchUnitProvisionModel.search_unit_id,
                )
                .join(
                    ProvisionModel,
                    ProvisionModel.id == SearchUnitProvisionModel.provision_id,
                )
                .where(SearchUnitModel.act_version_id == version.id)
            ).all()
        )
        linked_units = {row[0].search_unit_id for row in links}
        checks = {
            "snapshot_sha256": sha256(snapshot.raw_bytes).hexdigest()
            == snapshot.sha256,
            "snapshot_byte_length": len(snapshot.raw_bytes) == snapshot.byte_length,
            "version_hash": identity.version_hash == version.version_hash,
            "stable_keys": len({p.stable_key for p in stored_provisions})
            == len(stored_provisions),
            "document_order": len({p.document_order for p in stored_provisions})
            == len(stored_provisions),
            "parents": not cross_parent,
            "provision_hashes": all(
                sha256((p.citation_text or "").encode()).hexdigest() == p.content_hash
                for p in stored_provisions
            ),
            "unit_hashes": all(
                sha256(unit.search_text.encode()).hexdigest() == unit.content_hash
                for unit in stored_units
            ),
            "source_locators": all(
                p.source_locator["paragraph_start"] >= 0
                and p.source_locator["paragraph_end"]
                >= p.source_locator["paragraph_start"]
                for p in stored_provisions
            ),
            "all_units_linked": linked_units == {unit.id for unit in stored_units},
            "links_same_version": all(
                unit.act_version_id == provision.act_version_id == version.id
                for _, unit, provision in links
            ),
            "coverage": len(parsed.coverage) == parsed.total_dom_paragraphs,
            "materialized_provisions": len(stored_provisions) == len(parsed.provisions),
            "materialized_units": len(stored_units) == len(projected),
        }
        return AuditReport(
            passed=all(checks.values()),
            checks=checks,
            provision_count=len(stored_provisions),
            search_unit_count=len(stored_units),
        )


def list_versions(session: Session) -> tuple[dict[str, object], ...]:
    rows = session.execute(
        select(ActVersionModel, LegalActModel, SourceSnapshotModel)
        .join(LegalActModel, LegalActModel.id == ActVersionModel.legal_act_id)
        .join(
            SourceSnapshotModel,
            SourceSnapshotModel.id == ActVersionModel.source_snapshot_id,
        )
        .order_by(ActVersionModel.materialized_at)
    ).all()
    return tuple(
        {
            "act_code": act.act_code,
            "act_version_id": version.id,
            "version_hash": version.version_hash,
            "source_snapshot_sha256": snapshot.sha256,
            "parser": f"{version.parser_name}/{version.parser_version}",
            "projection": f"{version.projection_name}/{version.projection_version}",
            "materialized_at": version.materialized_at,
        }
        for version, act, snapshot in rows
    )


def trace_unit(session: Session, version_hash: str, unit_key: str) -> dict[str, object]:
    row = session.execute(
        select(
            SearchUnitModel,
            ProvisionModel,
            ActVersionModel,
            SourceSnapshotModel,
            SourceModel,
        )
        .join(
            SearchUnitProvisionModel,
            SearchUnitProvisionModel.search_unit_id == SearchUnitModel.id,
        )
        .join(
            ProvisionModel, ProvisionModel.id == SearchUnitProvisionModel.provision_id
        )
        .join(ActVersionModel, ActVersionModel.id == SearchUnitModel.act_version_id)
        .join(
            SourceSnapshotModel,
            SourceSnapshotModel.id == ActVersionModel.source_snapshot_id,
        )
        .join(SourceModel, SourceModel.id == SourceSnapshotModel.source_id)
        .where(
            ActVersionModel.version_hash == version_hash,
            SearchUnitModel.unit_key == unit_key,
        )
        .order_by(SearchUnitProvisionModel.position)
    ).first()
    if row is None:
        raise LookupError(f"SearchUnit não encontrada: {unit_key}")
    unit, provision, version, snapshot, source = row
    return {
        "unit_key": unit.unit_key,
        "search_text": unit.search_text,
        "stable_key": provision.stable_key,
        "provision_type": provision.provision_type,
        "citation_text": provision.citation_text,
        "source_locator": provision.source_locator,
        "document_order": provision.document_order,
        "version_hash": version.version_hash,
        "parser": f"{version.parser_name}/{version.parser_version}",
        "projection": f"{version.projection_name}/{version.projection_version}",
        "snapshot_sha256": snapshot.sha256,
        "snapshot_byte_length": snapshot.byte_length,
        "official_url": source.official_url,
    }
