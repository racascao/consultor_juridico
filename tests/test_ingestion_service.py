"""Testes da orquestração de ingestão sem rede ou PostgreSQL."""

import uuid
from types import SimpleNamespace

import pytest

from consultor_juridico.ingestion.hasher import sha256_hex
from consultor_juridico.ingestion.service import IngestionService
from consultor_juridico.ingestion.types import (
    DownloadedDocument,
    DownloadOutcome,
    IngestionOutcome,
)


def _download(payload: bytes) -> DownloadedDocument:
    return DownloadedDocument(
        requested_url="https://example.test/doc",
        final_url="https://example.test/doc",
        redirect_chain=(),
        status_code=200,
        headers=(("content-type", "text/html"),),
        outcome=DownloadOutcome.ACQUIRED,
        content_type="text/html",
        declared_charset=None,
        content_length_declared=len(payload),
        canonical_bytes=payload,
        content_encoding=None,
        attempts=1,
        duration_ms=1,
    )


class FakeRepository:
    def __init__(self, *, created: bool = True, fail: bool = False, latest=None):
        self.created = created
        self.fail = fail
        self.session = SimpleNamespace(commit=lambda: None)
        self.source = SimpleNamespace(id=uuid.uuid4())
        self.document = SimpleNamespace(id=uuid.uuid4())
        self.received_hash = None
        self.latest = latest

    def get_or_create_source(self, **kwargs):
        return self.source

    def store_document(self, *, sha256, **kwargs):
        if self.fail:
            raise RuntimeError("database unavailable")
        self.received_hash = sha256
        return SimpleNamespace(document=self.document, created=self.created)

    def get_latest_document(self, **kwargs):
        return self.latest


def test_service_hashes_downloaded_bytes_and_reports_created():
    payload = b"canonical bytes"
    repository = FakeRepository()
    downloader = SimpleNamespace(download=lambda _, **kwargs: _download(payload))
    result = IngestionService(downloader, repository).ingest_constitution()

    assert repository.received_hash == sha256_hex(payload)
    assert result.outcome is IngestionOutcome.CREATED
    assert result.sha256 == sha256_hex(payload)


def test_service_reports_already_known():
    repository = FakeRepository(created=False)
    downloader = SimpleNamespace(download=lambda _, **kwargs: _download(b"known"))
    result = IngestionService(downloader, repository).ingest_constitution()
    assert result.outcome is IngestionOutcome.ALREADY_KNOWN


def test_database_failure_is_propagated():
    repository = FakeRepository(fail=True)
    downloader = SimpleNamespace(download=lambda _, **kwargs: _download(b"payload"))
    with pytest.raises(RuntimeError, match="database unavailable"):
        IngestionService(downloader, repository).ingest_constitution()


def test_service_sends_validators_and_maps_304_to_previous_document():
    previous = SimpleNamespace(
        id=uuid.uuid4(),
        content_hash_sha256="previous-hash",
        metadata_json={
            "etag": '"etag-value"',
            "last_modified": "Wed, 05 Aug 2026 12:10:12 GMT",
        },
    )
    repository = FakeRepository(latest=previous)
    received_headers = None

    def download(_, *, conditional_headers):
        nonlocal received_headers
        received_headers = conditional_headers
        result = _download(b"unused")
        return DownloadedDocument(
            requested_url=result.requested_url,
            final_url=result.final_url,
            redirect_chain=(),
            status_code=304,
            headers=(("etag", '"etag-value"'),),
            outcome=DownloadOutcome.NOT_MODIFIED,
            content_type=None,
            declared_charset=None,
            content_length_declared=None,
            canonical_bytes=None,
            content_encoding=None,
            attempts=1,
            duration_ms=1,
        )

    result = IngestionService(
        SimpleNamespace(download=download), repository
    ).ingest_constitution()

    assert received_headers == {
        "If-None-Match": '"etag-value"',
        "If-Modified-Since": "Wed, 05 Aug 2026 12:10:12 GMT",
    }
    assert result.outcome is IngestionOutcome.ALREADY_KNOWN
    assert result.document_id == previous.id
    assert result.sha256 == "previous-hash"
    assert repository.received_hash is None


def test_service_without_validators_sends_no_conditional_headers():
    previous = SimpleNamespace(
        id=uuid.uuid4(), content_hash_sha256="hash", metadata_json={}
    )
    repository = FakeRepository(latest=previous)
    received_headers = None

    def download(_, *, conditional_headers):
        nonlocal received_headers
        received_headers = conditional_headers
        return _download(b"new payload")

    IngestionService(
        SimpleNamespace(download=download), repository
    ).ingest_constitution()
    assert received_headers == {}


def test_200_after_validators_runs_normal_new_capture_pipeline():
    previous = SimpleNamespace(
        id=uuid.uuid4(),
        content_hash_sha256="old-hash",
        metadata_json={"etag": '"old-etag"'},
    )
    repository = FakeRepository(latest=previous)
    received_headers = None

    def download(_, *, conditional_headers):
        nonlocal received_headers
        received_headers = conditional_headers
        return _download(b"new raw bytes")

    result = IngestionService(
        SimpleNamespace(download=download), repository
    ).ingest_constitution()

    assert received_headers == {"If-None-Match": '"old-etag"'}
    assert result.outcome is IngestionOutcome.CREATED
    assert repository.received_hash == sha256_hex(b"new raw bytes")
