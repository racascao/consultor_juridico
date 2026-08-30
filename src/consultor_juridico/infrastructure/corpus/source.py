"""Aquisição HTTP oficial adaptada ao port de corpus v0.2."""

from datetime import UTC, datetime

import httpx

from consultor_juridico.config import settings
from consultor_juridico.domain import SourceCapture
from consultor_juridico.ingestion.downloader import Downloader
from consultor_juridico.ingestion.hasher import sha256_hex
from consultor_juridico.ingestion.sources.planalto import PLANALTO_SOURCE
from consultor_juridico.ingestion.types import DownloadOutcome, HttpPolicy


class PlanaltoHttpSourceFetcher:
    def fetch(self) -> SourceCapture:
        policy = HttpPolicy(
            connect_timeout=settings.ingestion_connect_timeout,
            read_timeout=settings.ingestion_read_timeout,
            write_timeout=settings.ingestion_write_timeout,
            pool_timeout=settings.ingestion_pool_timeout,
            max_attempts=settings.ingestion_max_attempts,
            backoff_seconds=settings.ingestion_backoff_seconds,
            retry_after_max_seconds=settings.ingestion_retry_after_max_seconds,
            min_bytes=settings.ingestion_min_bytes,
            max_bytes=settings.ingestion_max_bytes,
            user_agent=settings.planalto_user_agent,
        )
        with httpx.Client() as client:
            downloaded = Downloader(client, policy).download(
                PLANALTO_SOURCE.constitution_url
            )
        if downloaded.outcome is not DownloadOutcome.ACQUIRED:
            raise RuntimeError("Aquisição sem payload não pode iniciar novo corpus.")
        raw_bytes = downloaded.canonical_bytes
        if raw_bytes is None:
            raise RuntimeError("Aquisição oficial retornou payload ausente.")
        return SourceCapture(
            source_name=PLANALTO_SOURCE.name,
            official_url=PLANALTO_SOURCE.base_url,
            requested_url=downloaded.requested_url,
            final_url=downloaded.final_url,
            fetched_at=datetime.now(UTC),
            raw_bytes=raw_bytes,
            sha256=sha256_hex(raw_bytes),
            etag=downloaded.header("ETag"),
            last_modified=downloaded.header("Last-Modified"),
            content_type=downloaded.content_type,
        )
