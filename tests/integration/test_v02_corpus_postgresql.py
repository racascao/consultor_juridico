"""Integridade física do corpus em PostgreSQL descartável."""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import sessionmaker

from consultor_juridico.application.corpus.audit import CorpusAuditor
from consultor_juridico.application.corpus.catalog import LEI_9784_ACT, LEI_9784_SOURCE
from consultor_juridico.application.corpus.parser import PlanaltoLeiParser
from consultor_juridico.application.corpus.ports import AcquisitionResponse
from consultor_juridico.application.corpus.projection import ProvisionTextProjection
from consultor_juridico.domain.corpus import SnapshotData, VersionIdentity
from consultor_juridico.infrastructure.corpus.materializer import (
    SqlAlchemyCorpusMaterializer,
)
from consultor_juridico.infrastructure.corpus.models import (
    ActVersionModel,
    LegalActModel,
    ProvisionModel,
    SearchUnitModel,
    SearchUnitProvisionModel,
)
from consultor_juridico.infrastructure.corpus.repositories import (
    SqlAlchemySnapshotRepository,
)

DATABASE_URL = os.getenv("V02_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="V02_TEST_DATABASE_URL não configurada"
)
REAL_CAPTURE = (
    Path(__file__).parents[2]
    / "docs/corpus/artifacts/lei-9784-1999-planalto-2026-08-31.raw.html"
)


@pytest.fixture(scope="module")
def session_factory():
    engine = create_engine(DATABASE_URL)
    factory = sessionmaker(engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(session_factory):
    with session_factory() as session, session.begin():
        session.execute(
            text(
                "TRUNCATE search_unit_provisions, search_units, provisions, "
                "act_versions, legal_acts, source_snapshots, sources CASCADE"
            )
        )


def _snapshot(session_factory, payload: bytes | None = None) -> SnapshotData:
    payload = payload or REAL_CAPTURE.read_bytes()
    with session_factory() as session, session.begin():
        repository = SqlAlchemySnapshotRepository(session)
        record, _ = repository.store(
            LEI_9784_SOURCE,
            AcquisitionResponse(
                200,
                payload,
                "text/html",
                '"etag"',
                "Thu, 23 Apr 2026 23:00:54 GMT",
            ),
        )
        return SnapshotData(
            record.id,
            record.source_id,
            record.sha256,
            record.raw_bytes,
            LEI_9784_SOURCE.encoding,
        )


def _identity(snapshot: SnapshotData) -> VersionIdentity:
    return VersionIdentity(
        LEI_9784_ACT.natural_key,
        snapshot.sha256,
        "planalto-lei-structural",
        "1",
        "provision-text",
        "1",
    )


def test_schema_contains_only_phase_zero_tables(session_factory):
    with session_factory() as session:
        tables = set(
            session.scalars(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' ORDER BY tablename"
                )
            )
        )
    assert tables == {
        "act_versions",
        "alembic_version",
        "legal_acts",
        "provisions",
        "search_unit_provisions",
        "search_units",
        "source_snapshots",
        "sources",
    }


def test_snapshot_is_idempotent_and_immutable(session_factory):
    first = _snapshot(session_factory, b"<html>raw</html>")
    second = _snapshot(session_factory, b"<html>raw</html>")
    assert first.id == second.id
    with session_factory() as session:
        with pytest.raises(DBAPIError, match="immutable"):
            session.execute(
                text("UPDATE source_snapshots SET etag = 'changed' WHERE id = :id"),
                {"id": first.id},
            )
            session.commit()
        session.rollback()
        with pytest.raises(DBAPIError, match="immutable"):
            session.execute(
                text("DELETE FROM source_snapshots WHERE id = :id"), {"id": first.id}
            )
            session.commit()


def test_materialization_is_idempotent_and_auditable(session_factory):
    snapshot = _snapshot(session_factory)
    parser = PlanaltoLeiParser()
    projection = ProvisionTextProjection()
    parsed = parser.parse(snapshot.raw_bytes, encoding=snapshot.encoding)
    projected = projection.project(parsed)
    materializer = SqlAlchemyCorpusMaterializer(session_factory)
    first = materializer.materialize(
        act=LEI_9784_ACT,
        snapshot=snapshot,
        identity=_identity(snapshot),
        parsed=parsed,
        projected=projected,
    )
    second = materializer.materialize(
        act=LEI_9784_ACT,
        snapshot=snapshot,
        identity=_identity(snapshot),
        parsed=parsed,
        projected=projected,
    )
    assert first.created is True
    assert second.created is False
    assert first.act_version_id == second.act_version_id
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ActVersionModel)) == 1
        assert session.scalar(select(func.count()).select_from(ProvisionModel)) == 322
        assert session.scalar(select(func.count()).select_from(SearchUnitModel)) == 242
        assert (
            session.scalar(select(func.count()).select_from(SearchUnitProvisionModel))
            == 242
        )
        report = CorpusAuditor(session, parser, projection).audit(
            first.version_hash, encoding=snapshot.encoding
        )
    assert report.passed is True


def test_failed_materialization_rolls_back_every_derived_row(session_factory):
    snapshot = _snapshot(session_factory)
    parser = PlanaltoLeiParser()
    parsed = parser.parse(snapshot.raw_bytes, encoding=snapshot.encoding)
    projected = ProvisionTextProjection().project(parsed)
    duplicate = projected + (projected[0],)
    with pytest.raises(IntegrityError):
        SqlAlchemyCorpusMaterializer(session_factory).materialize(
            act=LEI_9784_ACT,
            snapshot=snapshot,
            identity=_identity(snapshot),
            parsed=parsed,
            projected=duplicate,
        )
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ActVersionModel)) == 0
        assert session.scalar(select(func.count()).select_from(LegalActModel)) == 0
        assert session.scalar(select(func.count()).select_from(ProvisionModel)) == 0
        assert session.scalar(select(func.count()).select_from(SearchUnitModel)) == 0


def test_provision_stable_key_and_document_order_are_unique_per_version(
    session_factory,
):
    snapshot = _snapshot(session_factory)
    parsed = PlanaltoLeiParser().parse(snapshot.raw_bytes, encoding=snapshot.encoding)
    projected = ProvisionTextProjection().project(parsed)
    result = SqlAlchemyCorpusMaterializer(session_factory).materialize(
        act=LEI_9784_ACT,
        snapshot=snapshot,
        identity=_identity(snapshot),
        parsed=parsed,
        projected=projected,
    )
    with session_factory() as session:
        original = session.scalar(
            select(ProvisionModel).where(
                ProvisionModel.act_version_id == result.act_version_id
            )
        )
        session.add(
            ProvisionModel(
                act_version_id=result.act_version_id,
                stable_key=original.stable_key,
                provision_type="CAPUT",
                document_order=9999,
                source_locator={"paragraph_start": 0, "paragraph_end": 0},
                content_hash="0" * 64,
                legal_status="IN_FORCE",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.add(
            ProvisionModel(
                act_version_id=result.act_version_id,
                stable_key="SYNTHETIC:UNIQUE-CHECK",
                provision_type="CAPUT",
                document_order=original.document_order,
                source_locator={"paragraph_start": 0, "paragraph_end": 0},
                content_hash="0" * 64,
                legal_status="IN_FORCE",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_cross_version_parent_and_search_link_are_blocked(session_factory):
    snapshot = _snapshot(session_factory)
    parsed = PlanaltoLeiParser().parse(snapshot.raw_bytes, encoding=snapshot.encoding)
    projected = ProvisionTextProjection().project(parsed)
    materializer = SqlAlchemyCorpusMaterializer(session_factory)
    first = materializer.materialize(
        act=LEI_9784_ACT,
        snapshot=snapshot,
        identity=_identity(snapshot),
        parsed=parsed,
        projected=projected,
    )
    second_identity = VersionIdentity(
        LEI_9784_ACT.natural_key,
        snapshot.sha256,
        "planalto-lei-structural",
        "2",
        "provision-text",
        "1",
    )
    second = materializer.materialize(
        act=LEI_9784_ACT,
        snapshot=snapshot,
        identity=second_identity,
        parsed=parsed,
        projected=projected,
    )
    with session_factory() as session:
        parent = session.scalar(
            select(ProvisionModel).where(
                ProvisionModel.act_version_id == first.act_version_id
            )
        )
        child = session.scalar(
            select(ProvisionModel).where(
                ProvisionModel.act_version_id == second.act_version_id,
                ProvisionModel.parent_id.is_not(None),
            )
        )
        child.parent_id = parent.id
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        unit = session.scalar(
            select(SearchUnitModel).where(
                SearchUnitModel.act_version_id == first.act_version_id
            )
        )
        provision = session.scalar(
            select(ProvisionModel).where(
                ProvisionModel.act_version_id == second.act_version_id
            )
        )
        session.add(
            SearchUnitProvisionModel(
                search_unit_id=unit.id, provision_id=provision.id, position=99
            )
        )
        with pytest.raises(DBAPIError, match="cross-version"):
            session.commit()
