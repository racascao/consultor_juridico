"""Integração opt-in com a fonte oficial real e o PostgreSQL."""

import os

import pytest
from sqlalchemy import delete, func, select

from consultor_juridico.db.session import SessionLocal
from consultor_juridico.ingestion.hasher import sha256_hex
from consultor_juridico.ingestion.service import run_planalto_ingestion
from consultor_juridico.ingestion.types import DownloadOutcome, IngestionOutcome
from consultor_juridico.models import Source, SourceDocument
from consultor_juridico.services.db_service import run_migrations

pytestmark = pytest.mark.planalto_integration


@pytest.mark.skipif(
    os.getenv("RUN_PLANALTO_INTEGRATION") != "1",
    reason="Defina RUN_PLANALTO_INTEGRATION=1 para acessar o Planalto real.",
)
def test_real_planalto_download_persistence_and_idempotency():
    """Baixa, persiste, relê bytes e confirma a segunda execução idempotente."""
    run_migrations()
    first = run_planalto_ingestion()
    created_by_test = first.outcome is IngestionOutcome.CREATED

    try:
        with SessionLocal() as session:
            persisted = session.get(SourceDocument, first.document_id)
            assert persisted is not None
            assert persisted.raw_bytes == first.download.canonical_bytes
            assert sha256_hex(persisted.raw_bytes) == first.sha256
            count_before = session.scalar(
                select(func.count())
                .select_from(SourceDocument)
                .where(
                    SourceDocument.source_id == first.source_id,
                    SourceDocument.content_hash_sha256 == first.sha256,
                )
            )

        second = run_planalto_ingestion()

        with SessionLocal() as session:
            count_after = session.scalar(
                select(func.count())
                .select_from(SourceDocument)
                .where(
                    SourceDocument.source_id == first.source_id,
                    SourceDocument.content_hash_sha256 == first.sha256,
                )
            )

        assert first.download.status_code == 200
        assert first.download.outcome is DownloadOutcome.ACQUIRED
        assert first.outcome in {
            IngestionOutcome.CREATED,
            IngestionOutcome.ALREADY_KNOWN,
        }
        assert second.download.status_code == 304
        assert second.download.outcome is DownloadOutcome.NOT_MODIFIED
        assert second.download.canonical_bytes is None
        assert second.outcome is IngestionOutcome.ALREADY_KNOWN
        assert second.document_id == first.document_id
        assert count_before == count_after == 1

        metadata = persisted.metadata_json or {}
        print(f"status={first.download.status_code}")
        print(f"etag={metadata.get('etag')}")
        print(f"last_modified={metadata.get('last_modified')}")
        print(f"received_bytes={len(persisted.raw_bytes)}")
        print(f"sha256={first.sha256}")
        print(f"document_id={first.document_id}")
        print(f"second_status={second.download.status_code}")
        print(f"second_outcome={second.outcome.value}")
    finally:
        if created_by_test:
            with SessionLocal.begin() as session:
                session.execute(
                    delete(SourceDocument).where(
                        SourceDocument.source_id == first.source_id
                    )
                )
                session.execute(delete(Source).where(Source.id == first.source_id))
