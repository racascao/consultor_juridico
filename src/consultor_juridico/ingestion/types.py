"""Tipos explícitos do pipeline de aquisição documental."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID


class AcquisitionError(RuntimeError):
    """Erro técnico que impede uma aquisição documental válida."""


class HttpAcquisitionError(AcquisitionError):
    """Falha de transporte, timeout ou status HTTP."""


class InvalidPayloadError(AcquisitionError):
    """Resposta tecnicamente incompatível com o artefato esperado."""


@dataclass(frozen=True, slots=True)
class HttpPolicy:
    """Política configurável de download e repetição."""

    connect_timeout: float
    read_timeout: float
    write_timeout: float
    pool_timeout: float
    max_attempts: int
    backoff_seconds: float
    retry_after_max_seconds: float
    min_bytes: int
    max_bytes: int
    user_agent: str


class DownloadOutcome(StrEnum):
    """Resultado HTTP relevante para a aquisição documental."""

    ACQUIRED = "ACQUIRED"
    NOT_MODIFIED = "NOT_MODIFIED"


@dataclass(frozen=True, slots=True)
class DownloadedDocument:
    """Payload canônico e metadados técnicos de uma resposta HTTP válida."""

    requested_url: str
    final_url: str
    redirect_chain: tuple[str, ...]
    status_code: int
    headers: tuple[tuple[str, str], ...]
    outcome: DownloadOutcome
    content_type: str | None
    declared_charset: str | None
    content_length_declared: int | None
    canonical_bytes: bytes | None
    content_encoding: str | None
    attempts: int
    duration_ms: int

    def metadata(self, *, adapter_version: str) -> dict[str, Any]:
        """Retorna os metadados técnicos serializáveis em JSONB."""
        if self.canonical_bytes is None:
            raise ValueError("Resposta 304 não possui payload persistível")
        return {
            "final_url": self.final_url,
            "redirect_chain": list(self.redirect_chain),
            "status_code": self.status_code,
            "content_type": self.content_type,
            "declared_charset": self.declared_charset,
            "content_length_declared": self.content_length_declared,
            "received_bytes": len(self.canonical_bytes),
            "content_encoding": self.content_encoding,
            "attempts": self.attempts,
            "duration_ms": self.duration_ms,
            "adapter_version": adapter_version,
            "etag": self.header("ETag"),
            "last_modified": self.header("Last-Modified"),
        }

    def header(self, name: str) -> str | None:
        """Retorna a última ocorrência de um header sem perder a lista original."""
        expected = name.casefold()
        matches = [value for key, value in self.headers if key.casefold() == expected]
        return matches[-1] if matches else None


class IngestionOutcome(StrEnum):
    """Resultado persistente de uma tentativa de ingestão."""

    CREATED = "CREATED"
    ALREADY_KNOWN = "ALREADY_KNOWN"


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Resultado apresentado pela camada de aplicação à CLI."""

    outcome: IngestionOutcome
    document_id: UUID
    source_id: UUID
    sha256: str
    download: DownloadedDocument
