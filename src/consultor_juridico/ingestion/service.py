"""Orquestração da aquisição oficial, hashing e persistência."""

from typing import Any

import httpx
from sqlalchemy.orm import Session

from consultor_juridico.config import Settings, settings
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.ingestion.downloader import Downloader
from consultor_juridico.ingestion.hasher import sha256_hex
from consultor_juridico.ingestion.repository import SourceDocumentRepository
from consultor_juridico.ingestion.sources.planalto import (
    PLANALTO_SOURCE,
    PlanaltoSourceAdapter,
)
from consultor_juridico.ingestion.types import (
    DownloadOutcome,
    HttpPolicy,
    IngestionOutcome,
    IngestionResult,
)


class IngestionService:
    """Coordena componentes sem interpretar o conteúdo jurídico."""

    def __init__(
        self,
        downloader: Downloader,
        repository: SourceDocumentRepository,
        *,
        adapter: PlanaltoSourceAdapter = PLANALTO_SOURCE,
    ) -> None:
        self.downloader = downloader
        self.repository = repository
        self.adapter = adapter

    def ingest_constitution(self) -> IngestionResult:
        """Captura CF/88 e ADCT como um único documento físico."""
        source = self.repository.get_or_create_source(
            name=self.adapter.name,
            base_url=self.adapter.base_url,
            description=self.adapter.description,
        )
        latest = self.repository.get_latest_document(
            source_id=source.id,
            url_source=self.adapter.constitution_url,
        )
        conditional_headers = self._conditional_headers(latest)
        download = self.downloader.download(
            self.adapter.constitution_url,
            conditional_headers=conditional_headers,
        )

        if download.outcome is DownloadOutcome.NOT_MODIFIED:
            if latest is None:
                raise RuntimeError("Servidor retornou 304 sem captura anterior")
            self.repository.session.commit()
            return IngestionResult(
                outcome=IngestionOutcome.ALREADY_KNOWN,
                document_id=latest.id,
                source_id=source.id,
                sha256=latest.content_hash_sha256,
                download=download,
            )

        if download.canonical_bytes is None:
            raise RuntimeError("Resposta adquirida sem bytes canônicos")
        digest = sha256_hex(download.canonical_bytes)
        stored = self.repository.store_document(
            source=source,
            sha256=digest,
            download=download,
            adapter_version=self.adapter.adapter_version,
        )
        self.repository.session.commit()
        return IngestionResult(
            outcome=(
                IngestionOutcome.CREATED
                if stored.created
                else IngestionOutcome.ALREADY_KNOWN
            ),
            document_id=stored.document.id,
            source_id=source.id,
            sha256=digest,
            download=download,
        )

    @staticmethod
    def _conditional_headers(latest) -> dict[str, str]:
        if latest is None or not latest.metadata_json:
            return {}
        headers: dict[str, str] = {}
        if etag := latest.metadata_json.get("etag"):
            headers["If-None-Match"] = etag
        if last_modified := latest.metadata_json.get("last_modified"):
            headers["If-Modified-Since"] = last_modified
        return headers


def build_http_policy(app_settings: Settings) -> HttpPolicy:
    """Converte Settings na política imutável usada pelo downloader."""
    return HttpPolicy(
        connect_timeout=app_settings.ingestion_connect_timeout,
        read_timeout=app_settings.ingestion_read_timeout,
        write_timeout=app_settings.ingestion_write_timeout,
        pool_timeout=app_settings.ingestion_pool_timeout,
        max_attempts=app_settings.ingestion_max_attempts,
        backoff_seconds=app_settings.ingestion_backoff_seconds,
        retry_after_max_seconds=app_settings.ingestion_retry_after_max_seconds,
        min_bytes=app_settings.ingestion_min_bytes,
        max_bytes=app_settings.ingestion_max_bytes,
        user_agent=app_settings.planalto_user_agent,
    )


def run_planalto_ingestion(
    *, app_settings: Settings = settings, session: Session | None = None
) -> IngestionResult:
    """Composition root para a ingestão usada pela CLI e integração."""
    owns_session = session is None
    active_session = session or SessionLocal()
    try:
        with httpx.Client() as client:
            service = IngestionService(
                Downloader(client, build_http_policy(app_settings)),
                SourceDocumentRepository(active_session),
            )
            return service.ingest_constitution()
    except Exception:
        active_session.rollback()
        raise
    finally:
        if owns_session:
            active_session.close()


def get_ingestion_status(*, session: Session | None = None) -> list[dict[str, Any]]:
    """Retorna capturas persistidas sem inferir versões jurídicas."""
    owns_session = session is None
    active_session = session or SessionLocal()
    try:
        documents = SourceDocumentRepository(active_session).list_documents()
        return [
            {
                "id": str(document.id),
                "source": document.source.name,
                "url_source": document.url_source,
                "sha256": document.content_hash_sha256,
                "fetched_at": document.fetched_at,
                "received_bytes": len(document.raw_bytes),
            }
            for document in documents
        ]
    finally:
        if owns_session:
            active_session.close()
