"""Cliente HTTP restrito à aquisição técnica de documentos."""

import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from consultor_juridico.ingestion.types import (
    DownloadedDocument,
    DownloadOutcome,
    HttpAcquisitionError,
    HttpPolicy,
    InvalidPayloadError,
)

TRANSIENT_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
HTML_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml"})
CHARSET_PATTERN = re.compile(r"charset\s*=\s*[\"']?([^;\s\"']+)", re.IGNORECASE)


class Downloader:
    """Realiza GET com redirects, limites e retries controlados."""

    def __init__(
        self,
        client: httpx.Client,
        policy: HttpPolicy,
        *,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.policy = policy
        self.sleep = sleep
        self.monotonic = monotonic

    def download(
        self, url: str, conditional_headers: dict[str, str] | None = None
    ) -> DownloadedDocument:
        """Baixa e valida tecnicamente um payload HTML canônico."""
        started_at = self.monotonic()
        last_error: Exception | None = None
        request_headers = {
            "User-Agent": self.policy.user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "identity",
        }
        request_headers.update(conditional_headers or {})

        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                response = self.client.get(
                    url,
                    headers=request_headers,
                    follow_redirects=True,
                    timeout=httpx.Timeout(
                        connect=self.policy.connect_timeout,
                        read=self.policy.read_timeout,
                        write=self.policy.write_timeout,
                        pool=self.policy.pool_timeout,
                    ),
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt == self.policy.max_attempts:
                    break
                self.sleep(self._backoff(attempt, retry_after=None))
                continue

            if response.status_code == httpx.codes.NOT_MODIFIED:
                return self._build_not_modified(url, response, attempt, started_at)

            if response.status_code in TRANSIENT_STATUS_CODES:
                if attempt == self.policy.max_attempts:
                    raise HttpAcquisitionError(
                        f"HTTP transitório persistente: {response.status_code}"
                    )
                self.sleep(self._backoff(attempt, response.headers.get("Retry-After")))
                continue

            if not response.is_success:
                raise HttpAcquisitionError(f"HTTP não sucedido: {response.status_code}")

            return self._build_document(url, response, attempt, started_at)

        raise HttpAcquisitionError(
            f"Falha HTTP após {self.policy.max_attempts} tentativas: {last_error}"
        ) from last_error

    def _build_document(
        self,
        requested_url: str,
        response: httpx.Response,
        attempts: int,
        started_at: float,
    ) -> DownloadedDocument:
        content_type_header = response.headers.get("Content-Type", "")
        content_type = content_type_header.partition(";")[0].strip().lower()
        if content_type not in HTML_CONTENT_TYPES:
            received_type = content_type_header or "ausente"
            raise InvalidPayloadError(
                f"Content-Type incompatível com HTML: {received_type}"
            )

        declared_length = self._declared_length(response)
        if declared_length is not None and declared_length > self.policy.max_bytes:
            raise InvalidPayloadError(
                f"Content-Length excede o limite: {declared_length} bytes"
            )

        # httpx entrega response.content após eventual descompressão de
        # Content-Encoding, mas antes de qualquer decoding de charset.
        canonical_bytes = response.content
        received_bytes = len(canonical_bytes)
        if received_bytes < self.policy.min_bytes:
            raise InvalidPayloadError(
                f"Payload abaixo do mínimo: {received_bytes} bytes"
            )
        if received_bytes > self.policy.max_bytes:
            raise InvalidPayloadError(
                f"Payload excede o limite: {received_bytes} bytes"
            )

        charset_match = CHARSET_PATTERN.search(content_type_header)
        declared_charset = charset_match.group(1) if charset_match else None
        duration_ms = round((self.monotonic() - started_at) * 1000)

        return DownloadedDocument(
            requested_url=requested_url,
            final_url=str(response.url),
            redirect_chain=tuple(str(item.url) for item in response.history),
            status_code=response.status_code,
            headers=tuple(response.headers.multi_items()),
            outcome=DownloadOutcome.ACQUIRED,
            content_type=content_type_header,
            declared_charset=declared_charset,
            content_length_declared=declared_length,
            canonical_bytes=canonical_bytes,
            content_encoding=response.headers.get("Content-Encoding"),
            attempts=attempts,
            duration_ms=duration_ms,
        )

    def _build_not_modified(
        self,
        requested_url: str,
        response: httpx.Response,
        attempts: int,
        started_at: float,
    ) -> DownloadedDocument:
        """Representa 304 sem exigir ou materializar um corpo."""
        return DownloadedDocument(
            requested_url=requested_url,
            final_url=str(response.url),
            redirect_chain=tuple(str(item.url) for item in response.history),
            status_code=response.status_code,
            headers=tuple(response.headers.multi_items()),
            outcome=DownloadOutcome.NOT_MODIFIED,
            content_type=response.headers.get("Content-Type"),
            declared_charset=None,
            content_length_declared=self._declared_length(response),
            canonical_bytes=None,
            content_encoding=response.headers.get("Content-Encoding"),
            attempts=attempts,
            duration_ms=round((self.monotonic() - started_at) * 1000),
        )

    @staticmethod
    def _declared_length(response: httpx.Response) -> int | None:
        value = response.headers.get("Content-Length")
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        retry_seconds = self._retry_after_seconds(retry_after)
        if retry_seconds is not None:
            return min(retry_seconds, self.policy.retry_after_max_seconds)
        return self.policy.backoff_seconds * (2 ** (attempt - 1))

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return None
