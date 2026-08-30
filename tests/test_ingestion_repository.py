"""Testes de persistência, proveniência e idempotência da ingestão."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from consultor_juridico.db.session import SessionLocal, engine
from consultor_juridico.ingestion.repository import SourceDocumentRepository
from consultor_juridico.ingestion.types import DownloadedDocument, DownloadOutcome
from consultor_juridico.services.db_service import run_migrations


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    run_migrations()


@pytest.fixture
def db_session() -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    yield session
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


def _download(payload: bytes, url: str = "https://example.test/doc"):
    return DownloadedDocument(
        requested_url=url,
        final_url=url,
        redirect_chain=(),
        status_code=200,
        headers=(("content-type", "text/html"), ("set-cookie", "a=1")),
        outcome=DownloadOutcome.ACQUIRED,
        content_type="text/html",
        declared_charset=None,
        content_length_declared=len(payload),
        canonical_bytes=payload,
        content_encoding=None,
        attempts=1,
        duration_ms=10,
    )


def test_repository_preserves_bytes_metadata_and_is_idempotent(db_session: Session):
    repository = SourceDocumentRepository(db_session)
    source = repository.get_or_create_source(
        name="Fonte repository",
        base_url="https://repository.example",
        description="Teste",
    )
    payload = b"\x00\xff<html>raw</html>"
    first = repository.store_document(
        source=source,
        sha256="hash-a",
        download=_download(payload),
        adapter_version="adapter-v1",
    )
    second = repository.store_document(
        source=source,
        sha256="hash-a",
        download=_download(payload),
        adapter_version="adapter-v1",
    )

    assert first.created is True
    assert second.created is False
    assert second.document.id == first.document.id
    assert first.document.raw_bytes == payload
    assert first.document.http_headers[1] == ["set-cookie", "a=1"]
    assert first.document.metadata_json["received_bytes"] == len(payload)


def test_same_url_with_different_bytes_creates_new_document(db_session: Session):
    repository = SourceDocumentRepository(db_session)
    source = repository.get_or_create_source(
        name="Fonte mudanças",
        base_url="https://changes.example",
        description="Teste",
    )
    first = repository.store_document(
        source=source,
        sha256="hash-first",
        download=_download(b"first"),
        adapter_version="v1",
    )
    second = repository.store_document(
        source=source,
        sha256="hash-second",
        download=_download(b"second"),
        adapter_version="v1",
    )
    assert first.created is True
    assert second.created is True
    assert first.document.id != second.document.id
    latest = repository.get_latest_document(
        source_id=source.id, url_source="https://example.test/doc"
    )
    assert latest is not None
    assert latest.id == second.document.id


def test_same_hash_from_different_sources_creates_distinct_documents(
    db_session: Session,
):
    repository = SourceDocumentRepository(db_session)
    source_a = repository.get_or_create_source(
        name="A", base_url="https://source-a.example", description="A"
    )
    source_b = repository.get_or_create_source(
        name="B", base_url="https://source-b.example", description="B"
    )
    first = repository.store_document(
        source=source_a,
        sha256="shared-hash",
        download=_download(b"shared"),
        adapter_version="v1",
    )
    second = repository.store_document(
        source=source_b,
        sha256="shared-hash",
        download=_download(b"shared"),
        adapter_version="v1",
    )
    assert first.document.id != second.document.id


def test_fetched_at_is_populated_by_database(db_session: Session):
    repository = SourceDocumentRepository(db_session)
    source = repository.get_or_create_source(
        name="Timestamp", base_url="https://timestamp.example", description="Teste"
    )
    stored = repository.store_document(
        source=source,
        sha256="timestamp-hash",
        download=_download(b"timestamp"),
        adapter_version="v1",
    )
    db_session.flush()
    assert isinstance(stored.document.fetched_at, datetime)
    assert stored.document.fetched_at.tzinfo is not None
    assert stored.document.fetched_at <= datetime.now(UTC)
