"""Repositórios SQLAlchemy de snapshots e leituras do corpus."""

from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from consultor_juridico.application.corpus.ports import (
    AcquisitionResponse,
    SnapshotRecord,
    SourceSpec,
)
from consultor_juridico.domain.corpus import SnapshotData
from consultor_juridico.infrastructure.corpus.models import (
    SourceModel,
    SourceSnapshotModel,
)


def _record(model: SourceSnapshotModel) -> SnapshotRecord:
    return SnapshotRecord(
        model.id,
        model.source_id,
        model.sha256,
        model.raw_bytes,
        model.byte_length,
        model.content_type,
        model.etag,
        model.last_modified,
        model.acquired_at,
    )


class SqlAlchemySnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _source(self, spec: SourceSpec) -> SourceModel | None:
        return self._session.scalar(
            select(SourceModel).where(
                SourceModel.authority_code == spec.authority_code,
                SourceModel.official_url == spec.official_url,
            )
        )

    def latest_for_source(self, source: SourceSpec) -> SnapshotRecord | None:
        model = self._source(source)
        if model is None:
            return None
        snapshot = self._session.scalar(
            select(SourceSnapshotModel)
            .where(SourceSnapshotModel.source_id == model.id)
            .order_by(SourceSnapshotModel.acquired_at.desc())
        )
        return _record(snapshot) if snapshot else None

    def store(
        self, source: SourceSpec, response: AcquisitionResponse
    ) -> tuple[SnapshotRecord, bool]:
        if response.status_code != 200 or response.raw_bytes is None:
            raise ValueError("Somente respostas 200 com bytes podem ser persistidas")
        model = self._source(source)
        if model is None:
            model = SourceModel(
                authority_code=source.authority_code,
                official_url=source.official_url,
                name=source.name,
            )
            self._session.add(model)
            self._session.flush()
        digest = sha256(response.raw_bytes).hexdigest()
        existing = self._session.scalar(
            select(SourceSnapshotModel).where(
                SourceSnapshotModel.source_id == model.id,
                SourceSnapshotModel.sha256 == digest,
            )
        )
        if existing:
            return _record(existing), False
        snapshot = SourceSnapshotModel(
            source_id=model.id,
            sha256=digest,
            raw_bytes=response.raw_bytes,
            byte_length=len(response.raw_bytes),
            content_type=response.content_type,
            etag=response.etag,
            last_modified=response.last_modified,
            acquired_at=datetime.now(UTC),
        )
        self._session.add(snapshot)
        self._session.flush()
        return _record(snapshot), True

    def by_sha(self, sha256_hex: str, encoding: str) -> SnapshotData | None:
        snapshot = self._session.scalar(
            select(SourceSnapshotModel).where(SourceSnapshotModel.sha256 == sha256_hex)
        )
        if snapshot is None:
            return None
        return SnapshotData(
            snapshot.id,
            snapshot.source_id,
            snapshot.sha256,
            snapshot.raw_bytes,
            encoding,
        )
