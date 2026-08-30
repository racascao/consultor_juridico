"""Leitura de snapshots e persistência transacional do corpus v0.2."""

import hashlib
import re
import unicodedata
from collections.abc import Callable

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from consultor_juridico.application.corpus.ports import (
    CorpusStatus,
    MaterializedCorpus,
)
from consultor_juridico.domain import (
    CorpusIdentityConflict,
    ParsedCorpus,
    ParsedProvision,
    SearchUnitDraft,
    SourceCapture,
    SourceSnapshotIntegrityError,
    SourceSnapshotNotFound,
    act_version_hash,
)
from consultor_juridico.infrastructure.corpus.models import (
    ActVersionRecord,
    LegalActRecord,
    ProvisionRecord,
    SearchUnitProvisionRecord,
    SearchUnitRecord,
    SourceRecord,
    SourceSnapshotRecord,
)

CORPUS_MATERIALIZATION_LOCK_ID = 0x434F52505553


class SqlAlchemyCorpusRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def read_by_sha256(self, snapshot_sha256: str) -> SourceCapture:
        """Reconstrói a captura exata persistida e valida sua integridade."""
        with self._session_factory() as session:
            row = session.execute(
                select(SourceSnapshotRecord, SourceRecord)
                .join(SourceRecord, SourceRecord.id == SourceSnapshotRecord.source_id)
                .where(SourceSnapshotRecord.sha256 == snapshot_sha256)
            ).one_or_none()
            if row is None:
                raise SourceSnapshotNotFound(snapshot_sha256)
            snapshot, source = row
            raw_bytes = bytes(snapshot.raw_bytes)
            actual_sha256 = hashlib.sha256(raw_bytes).hexdigest()
            if actual_sha256 != snapshot.sha256:
                raise SourceSnapshotIntegrityError(snapshot.sha256, actual_sha256)
            return SourceCapture(
                source_name=source.name,
                official_url=source.official_url,
                requested_url=snapshot.requested_url,
                final_url=snapshot.final_url,
                fetched_at=snapshot.fetched_at,
                raw_bytes=raw_bytes,
                sha256=snapshot.sha256,
                etag=snapshot.etag,
                last_modified=snapshot.last_modified,
                content_type=snapshot.content_type,
            )

    def materialize(
        self,
        capture: SourceCapture,
        parsed: ParsedCorpus,
        search_units: tuple[tuple[str, tuple[SearchUnitDraft, ...]], ...],
    ) -> MaterializedCorpus:
        with self._session_factory() as session, session.begin():
            self._lock_materialization(session)
            snapshot = session.scalar(
                select(SourceSnapshotRecord).where(
                    SourceSnapshotRecord.sha256 == capture.sha256
                )
            )
            source = self._source(session, capture)
            if snapshot is None:
                snapshot = self._snapshot(session, source, capture)
            elif snapshot.source_id != source.id:
                raise CorpusIdentityConflict(
                    "SourceSnapshot",
                    capture.sha256,
                    "a captura existente pertence a outra Source",
                )
            expected_hashes = {
                act.code: act_version_hash(
                    act.code, capture.sha256, parsed.parser_version
                )
                for act in parsed.acts
            }
            existing = self._existing_versions(session, expected_hashes)
            if existing and len(existing) != len(parsed.acts):
                raise CorpusIdentityConflict(
                    "ActVersion",
                    capture.sha256,
                    "conjunto parcial de versões para snapshot/parser",
                )
            if len(existing) == len(parsed.acts):
                self._validate_existing_versions(
                    existing, snapshot, parsed.parser_version
                )
                return self._result(session, capture.sha256, False, tuple(existing))

            units_by_act = dict(search_units)
            created_versions: list[ActVersionRecord] = []
            for act in parsed.acts:
                legal_act = self._legal_act(session, act)
                session.execute(
                    update(ActVersionRecord)
                    .where(ActVersionRecord.legal_act_id == legal_act.id)
                    .values(active=False)
                )
                version = ActVersionRecord(
                    legal_act_id=legal_act.id,
                    source_snapshot_id=snapshot.id,
                    version_hash=expected_hashes[act.code],
                    parser_version=parsed.parser_version,
                    active=True,
                )
                session.add(version)
                session.flush()
                provisions = self._provisions(session, version, act.root_provisions)
                self._search_units(session, version, units_by_act[act.code], provisions)
                created_versions.append(version)
            session.flush()
            return self._result(session, capture.sha256, True, tuple(created_versions))

    @staticmethod
    def _lock_materialization(session: Session) -> None:
        """Serializa builds concorrentes sem estado externo ou lock persistente."""
        session.execute(
            select(func.pg_advisory_xact_lock(CORPUS_MATERIALIZATION_LOCK_ID))
        )

    def status(self) -> CorpusStatus:
        with self._session_factory() as session:
            active = session.scalars(
                select(ActVersionRecord).where(ActVersionRecord.active.is_(True))
            ).all()
            snapshot_hash = None
            parser_version = None
            if active:
                snapshot = session.get(
                    SourceSnapshotRecord, active[0].source_snapshot_id
                )
                snapshot_hash = snapshot.sha256 if snapshot else None
                parser_version = active[0].parser_version
            provisions = tuple(
                session.execute(
                    select(LegalActRecord.code, func.count(ProvisionRecord.id))
                    .select_from(LegalActRecord)
                    .join(
                        ActVersionRecord,
                        ActVersionRecord.legal_act_id == LegalActRecord.id,
                    )
                    .join(
                        ProvisionRecord,
                        ProvisionRecord.act_version_id == ActVersionRecord.id,
                    )
                    .where(ActVersionRecord.active.is_(True))
                    .group_by(LegalActRecord.code)
                    .order_by(LegalActRecord.code)
                ).all()
            )
            units = tuple(
                session.execute(
                    select(SearchUnitRecord.unit_type, func.count(SearchUnitRecord.id))
                    .select_from(SearchUnitRecord)
                    .join(
                        ActVersionRecord,
                        SearchUnitRecord.act_version_id == ActVersionRecord.id,
                    )
                    .where(ActVersionRecord.active.is_(True))
                    .group_by(SearchUnitRecord.unit_type)
                    .order_by(SearchUnitRecord.unit_type)
                ).all()
            )
            unit_acts = set(
                session.scalars(
                    select(LegalActRecord.code)
                    .select_from(LegalActRecord)
                    .join(
                        ActVersionRecord,
                        ActVersionRecord.legal_act_id == LegalActRecord.id,
                    )
                    .join(
                        SearchUnitRecord,
                        SearchUnitRecord.act_version_id == ActVersionRecord.id,
                    )
                    .where(ActVersionRecord.active.is_(True))
                    .distinct()
                ).all()
            )
            return CorpusStatus(
                ready=len(active) == 2
                and {code for code, _ in provisions} == {"CF88", "ADCT"}
                and unit_acts == {"CF88", "ADCT"},
                snapshots=int(
                    session.scalar(
                        select(func.count()).select_from(SourceSnapshotRecord)
                    )
                    or 0
                ),
                active_snapshot_sha256=snapshot_hash,
                legal_acts=int(
                    session.scalar(select(func.count()).select_from(LegalActRecord))
                    or 0
                ),
                act_versions=int(
                    session.scalar(select(func.count()).select_from(ActVersionRecord))
                    or 0
                ),
                provisions_by_act=provisions,
                search_units_by_type=units,
                parser_version=parser_version,
            )

    @staticmethod
    def _source(session: Session, capture: SourceCapture) -> SourceRecord:
        source = session.scalar(
            select(SourceRecord).where(
                SourceRecord.official_url == capture.official_url
            )
        )
        if source is None:
            source = SourceRecord(
                name=capture.source_name, official_url=capture.official_url
            )
            session.add(source)
            session.flush()
        elif _canonical_source_name(source.name) != _canonical_source_name(
            capture.source_name
        ):
            raise CorpusIdentityConflict(
                "Source",
                capture.official_url,
                f"nome persistido={source.name!r}, recebido={capture.source_name!r}",
            )
        return source

    @staticmethod
    def _snapshot(
        session: Session, source: SourceRecord, capture: SourceCapture
    ) -> SourceSnapshotRecord:
        snapshot = SourceSnapshotRecord(
            source_id=source.id,
            requested_url=capture.requested_url,
            final_url=capture.final_url,
            fetched_at=capture.fetched_at,
            raw_bytes=capture.raw_bytes,
            sha256=capture.sha256,
            etag=capture.etag,
            last_modified=capture.last_modified,
            content_type=capture.content_type,
        )
        session.add(snapshot)
        session.flush()
        return snapshot

    @staticmethod
    def _existing_versions(
        session: Session, expected_hashes: dict[str, str]
    ) -> tuple[ActVersionRecord, ...]:
        identities = tuple(
            and_(LegalActRecord.code == code, ActVersionRecord.version_hash == digest)
            for code, digest in expected_hashes.items()
        )
        if not identities:
            return ()
        return tuple(
            session.scalars(
                select(ActVersionRecord)
                .join(
                    LegalActRecord,
                    ActVersionRecord.legal_act_id == LegalActRecord.id,
                )
                .where(or_(*identities))
            ).all()
        )

    @staticmethod
    def _validate_existing_versions(
        versions: tuple[ActVersionRecord, ...],
        snapshot: SourceSnapshotRecord,
        parser_version: str,
    ) -> None:
        for version in versions:
            if (
                version.source_snapshot_id != snapshot.id
                or version.parser_version != parser_version
            ):
                raise CorpusIdentityConflict(
                    "ActVersion",
                    version.version_hash,
                    "snapshot ou parser_version incompatível",
                )

    @staticmethod
    def _legal_act(session: Session, act) -> LegalActRecord:
        record = session.scalar(
            select(LegalActRecord).where(LegalActRecord.code == act.code)
        )
        promulgation = next(
            (
                item
                for item in act.metadata
                if item.kind == "PROMULGATION" and item.promulgation_date
            ),
            None,
        )
        if record is None:
            record = LegalActRecord(
                code=act.code,
                title=act.title,
                act_type=act.act_type,
                promulgation_date=act.promulgation_date,
                promulgation_source_locator=(
                    promulgation.source_locator if promulgation else None
                ),
            )
            session.add(record)
            session.flush()
        elif (
            record.title != act.title
            or record.act_type != act.act_type
            or record.promulgation_date != act.promulgation_date
        ):
            raise CorpusIdentityConflict(
                "LegalAct",
                act.code,
                "título, tipo ou data de promulgação incompatível",
            )
        return record

    def _provisions(
        self,
        session: Session,
        version: ActVersionRecord,
        roots: tuple[ParsedProvision, ...],
    ) -> dict[str, ProvisionRecord]:
        records: dict[str, ProvisionRecord] = {}

        def add(items: tuple[ParsedProvision, ...], parent_id=None) -> None:
            for item in sorted(items, key=lambda value: value.document_order):
                record = ProvisionRecord(
                    act_version_id=version.id,
                    parent_id=parent_id,
                    stable_key=item.stable_key,
                    provision_type=item.provision_type.value,
                    label=item.label,
                    document_order=item.document_order,
                    citation_text=item.citation_text,
                    source_locator=item.source_locator,
                )
                session.add(record)
                session.flush()
                records[item.stable_key] = record
                add(item.children, record.id)

        add(roots)
        return records

    @staticmethod
    def _search_units(
        session: Session,
        version: ActVersionRecord,
        drafts: tuple[SearchUnitDraft, ...],
        provisions: dict[str, ProvisionRecord],
    ) -> None:
        for draft in drafts:
            anchor = provisions.get(draft.anchor_stable_key or "")
            record = SearchUnitRecord(
                act_version_id=version.id,
                unit_type=draft.unit_type.value,
                stable_reference=draft.stable_reference,
                anchor_provision_id=anchor.id if anchor else None,
                search_text=draft.search_text,
                content_hash=draft.content_hash,
                document_order=draft.document_order,
                source_locator=draft.source_locator,
                source_excerpt=draft.source_excerpt,
            )
            session.add(record)
            session.flush()
            session.add_all(
                SearchUnitProvisionRecord(
                    search_unit_id=record.id,
                    provision_id=provisions[key].id,
                )
                for key in draft.provision_stable_keys
            )

    @staticmethod
    def _result(
        session: Session,
        snapshot_sha256: str,
        created: bool,
        versions: tuple[ActVersionRecord, ...],
    ) -> MaterializedCorpus:
        version_ids = tuple(item.id for item in versions)
        provisions = int(
            session.scalar(
                select(func.count())
                .select_from(ProvisionRecord)
                .where(ProvisionRecord.act_version_id.in_(version_ids))
            )
            or 0
        )
        search_units = int(
            session.scalar(
                select(func.count())
                .select_from(SearchUnitRecord)
                .where(SearchUnitRecord.act_version_id.in_(version_ids))
            )
            or 0
        )
        return MaterializedCorpus(
            created, snapshot_sha256, len(versions), provisions, search_units
        )


def _canonical_source_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    tokens = re.findall(r"[a-z0-9]+", ascii_value)
    return " ".join(
        token for token in tokens if token not in {"portal", "do", "da", "de"}
    )
