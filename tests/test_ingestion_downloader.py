"""Testes unitários do downloader sem acesso à internet."""

import gzip

import httpx
import pytest

from consultor_juridico.ingestion.downloader import Downloader
from consultor_juridico.ingestion.types import (
    HttpAcquisitionError,
    HttpPolicy,
    InvalidPayloadError,
)


def _policy(**overrides) -> HttpPolicy:
    values = {
        "connect_timeout": 10.0,
        "read_timeout": 30.0,
        "write_timeout": 10.0,
        "pool_timeout": 10.0,
        "max_attempts": 3,
        "backoff_seconds": 0.5,
        "retry_after_max_seconds": 5.0,
        "min_bytes": 1,
        "max_bytes": 1024,
        "user_agent": "test-agent",
    }
    values.update(overrides)
    return HttpPolicy(**values)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_success_preserves_canonical_bytes_and_metadata():
    payload = b"<html>\x00\xff</html>"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Accept-Encoding"] == "identity"
        assert request.headers["User-Agent"] == "test-agent"
        return httpx.Response(
            200,
            headers=[
                ("Content-Type", "text/html; charset=windows-1252"),
                ("Set-Cookie", "a=1"),
                ("Set-Cookie", "b=2"),
            ],
            content=payload,
        )

    with _client(handler) as client:
        result = Downloader(client, _policy()).download("https://example.test/doc")

    assert result.canonical_bytes == payload
    assert result.declared_charset == "windows-1252"
    assert result.final_url == "https://example.test/doc"
    assert result.headers.count(("set-cookie", "a=1")) == 1
    assert result.headers.count(("set-cookie", "b=2")) == 1
    assert result.metadata(adapter_version="v1")["received_bytes"] == len(payload)


def test_etag_and_last_modified_are_exposed_in_metadata():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "Content-Type": "text/html",
                "ETag": '"etag-value"',
                "Last-Modified": "Wed, 05 Aug 2026 12:10:12 GMT",
            },
            content=b"<html/>",
        )

    with _client(handler) as client:
        result = Downloader(client, _policy()).download("https://example.test/doc")

    metadata = result.metadata(adapter_version="v1")
    assert metadata["etag"] == '"etag-value"'
    assert metadata["last_modified"] == "Wed, 05 Aug 2026 12:10:12 GMT"


def test_conditional_headers_and_304_without_body_or_retry():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["If-None-Match"] == '"etag-value"'
        assert request.headers["If-Modified-Since"] == ("Wed, 05 Aug 2026 12:10:12 GMT")
        return httpx.Response(304, headers={"ETag": '"etag-value"'})

    with _client(handler) as client:
        result = Downloader(client, _policy(min_bytes=999)).download(
            "https://example.test/doc",
            conditional_headers={
                "If-None-Match": '"etag-value"',
                "If-Modified-Since": "Wed, 05 Aug 2026 12:10:12 GMT",
            },
        )

    assert result.outcome.value == "NOT_MODIFIED"
    assert result.status_code == 304
    assert result.canonical_bytes is None
    assert result.attempts == 1
    assert calls == 1


def test_content_encoding_is_decompressed_before_canonical_bytes():
    payload = b"<html>payload descomprimido</html>"
    compressed = gzip.compress(payload)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html", "Content-Encoding": "gzip"},
            content=compressed,
        )

    with _client(handler) as client:
        result = Downloader(client, _policy()).download("https://example.test/doc")

    assert result.canonical_bytes == payload
    assert result.content_encoding == "gzip"


def test_redirect_records_requested_and_final_urls():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "/final"})
        return httpx.Response(
            200, headers={"Content-Type": "text/html"}, content=b"<html/>"
        )

    with _client(handler) as client:
        result = Downloader(client, _policy()).download("https://example.test/start")

    assert result.requested_url == "https://example.test/start"
    assert result.final_url == "https://example.test/final"
    assert result.redirect_chain == ("https://example.test/start",)


@pytest.mark.parametrize("status", [404, 400, 403])
def test_permanent_http_error_is_not_retried(status: int):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, content=b"error")

    with _client(handler) as client:
        with pytest.raises(HttpAcquisitionError):
            Downloader(client, _policy()).download("https://example.test/doc")
    assert calls == 1


def test_transient_error_retries_then_succeeds():
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(500, headers={"Retry-After": "99"})
        return httpx.Response(
            200, headers={"Content-Type": "text/html"}, content=b"<html/>"
        )

    with _client(handler) as client:
        result = Downloader(client, _policy(), sleep=sleeps.append).download(
            "https://example.test/doc"
        )

    assert result.attempts == 3
    assert calls == 3
    assert sleeps == [5.0, 5.0]


def test_timeout_retries_and_reports_failure():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timeout", request=request)

    with _client(handler) as client:
        with pytest.raises(HttpAcquisitionError, match="3 tentativas"):
            Downloader(client, _policy(), sleep=lambda _: None).download(
                "https://example.test/doc"
            )
    assert calls == 3


@pytest.mark.parametrize(
    ("headers", "content", "message"),
    [
        ({"Content-Type": "text/html"}, b"", "abaixo do mínimo"),
        ({"Content-Type": "application/pdf"}, b"pdf", "Content-Type"),
        ({"Content-Type": "text/html"}, b"12345", "excede o limite"),
    ],
)
def test_payload_sanity_checks(headers, content: bytes, message: str):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers=headers, content=content)

    with _client(handler) as client:
        with pytest.raises(InvalidPayloadError, match=message):
            Downloader(client, _policy(max_bytes=4)).download(
                "https://example.test/doc"
            )
