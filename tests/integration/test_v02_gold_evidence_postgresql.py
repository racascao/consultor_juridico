"""Materialização física de Gold Evidence em PostgreSQL descartável."""

import os
from hashlib import sha256

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from consultor_juridico.infrastructure.corpus.models import (
    ActVersionModel,
    LegalActModel,
    ProvisionModel,
    SourceModel,
    SourceSnapshotModel,
)
from consultor_juridico.infrastructure.gold_evidence import (
    SqlAlchemyGoldEvidenceRepository,
)

DATABASE_URL = os.getenv("V02_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="V02_TEST_DATABASE_URL não configurada"
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


def _seed(session) -> str:
    raw = b"<html>gold</html>"
    source = SourceModel(
        authority_code="PLANALTO-GOLD",
        official_url="https://example.test/gold",
        name="Fonte Gold",
    )
    session.add(source)
    session.flush()
    snapshot = SourceSnapshotModel(
        source_id=source.id,
        sha256=sha256(raw).hexdigest(),
        raw_bytes=raw,
        byte_length=len(raw),
        content_type="text/html",
    )
    act = LegalActModel(
        act_code="ACT-GOLD",
        jurisdiction="BR",
        act_type="LEI",
        number="1",
        year=2000,
        title="Lei Gold",
    )
    session.add_all((snapshot, act))
    session.flush()
    version_hash = sha256(b"gold-version").hexdigest()
    version = ActVersionModel(
        legal_act_id=act.id,
        source_snapshot_id=snapshot.id,
        parser_name="parser",
        parser_version="1",
        projection_name="projection",
        projection_version="1",
        version_hash=version_hash,
    )
    session.add(version)
    session.flush()
    session.add_all(
        (
            ProvisionModel(
                act_version_id=version.id,
                stable_key="ARTICLE:1/CAPUT",
                provision_type="CAPUT",
                document_order=2,
                citation_text="Texto segundo",
                source_locator={"paragraph_start": 2, "paragraph_end": 2},
                content_hash=sha256(b"Texto segundo").hexdigest(),
                legal_status="IN_FORCE",
            ),
            ProvisionModel(
                act_version_id=version.id,
                stable_key="ARTICLE:1/PARAGRAPH:1",
                provision_type="PARAGRAPH",
                number_label="1",
                document_order=1,
                citation_text="Texto primeiro",
                source_locator={"paragraph_start": 1, "paragraph_end": 1},
                content_hash=sha256(b"Texto primeiro").hexdigest(),
                legal_status="IN_FORCE",
            ),
        )
    )
    return version_hash


def test_gold_evidence_preserves_version_provenance_and_document_order(
    session_factory,
):
    with session_factory() as session, session.begin():
        version_hash = _seed(session)
    with session_factory() as session:
        repository = SqlAlchemyGoldEvidenceRepository(session)
        context = repository.context(version_hash)
        evidence = repository.materialize(
            version_hash,
            ("ARTICLE:1/CAPUT", "ARTICLE:1/PARAGRAPH:1"),
        )
        provision_keys = repository.provision_keys(version_hash)
    assert context.legal_act_code == "ACT-GOLD"
    assert context.official_url == "https://example.test/gold"
    assert [item.stable_key for item in evidence] == [
        "ARTICLE:1/PARAGRAPH:1",
        "ARTICLE:1/CAPUT",
    ]
    assert all(
        item.source_snapshot_sha256 == context.source_snapshot_sha256
        for item in evidence
    )
    assert provision_keys == {
        "ARTICLE:1/CAPUT",
        "ARTICLE:1/PARAGRAPH:1",
    }


def test_gold_evidence_requires_explicit_existing_version(session_factory):
    with session_factory() as session:
        with pytest.raises(LookupError, match="ActVersion não encontrada"):
            SqlAlchemyGoldEvidenceRepository(session).context("f" * 64)


def test_direct_children_are_version_scoped_ordered_and_limited(session_factory):
    with session_factory() as session, session.begin():
        version_hash = _seed(session)
        session.flush()
        parent = session.scalar(
            select(ProvisionModel).where(ProvisionModel.stable_key == "ARTICLE:1/CAPUT")
        )
        child = session.scalar(
            select(ProvisionModel).where(
                ProvisionModel.stable_key == "ARTICLE:1/PARAGRAPH:1"
            )
        )
        child.parent_id = parent.id
    with session_factory() as session:
        children = SqlAlchemyGoldEvidenceRepository(session).direct_children(
            version_hash,
            ("ARTICLE:1/CAPUT",),
            max_children_per_parent=1,
        )
    assert tuple(children) == ("ARTICLE:1/CAPUT",)
    assert [item.stable_key for item in children["ARTICLE:1/CAPUT"]] == [
        "ARTICLE:1/PARAGRAPH:1"
    ]
