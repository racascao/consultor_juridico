"""Validação criptográfica e decoding estrito da captura oficial."""

from time import perf_counter
from typing import Protocol
from uuid import UUID

from consultor_juridico.ingestion.hasher import sha256_hex
from consultor_juridico.parsing.errors import (
    SourceDocumentDecodingError,
    SourceDocumentIntegrityError,
)
from consultor_juridico.parsing.types import DecodedSourceDocument

PLANALTO_CONSTITUTION_ENCODING = "windows-1252"


class SourceDocumentLike(Protocol):
    id: UUID
    raw_bytes: bytes
    content_hash_sha256: str
    url_source: str


def decode_source_document(
    document: SourceDocumentLike,
    *,
    encoding: str = PLANALTO_CONSTITUTION_ENCODING,
) -> DecodedSourceDocument:
    """Valida e decodifica um SourceDocument sem depender da sessão ORM."""
    return decode_raw_document(
        source_document_id=document.id,
        raw_bytes=document.raw_bytes,
        expected_sha256=document.content_hash_sha256,
        source_url=document.url_source,
        encoding=encoding,
    )


def decode_raw_document(
    *,
    source_document_id: UUID,
    raw_bytes: bytes,
    expected_sha256: str,
    source_url: str | None = None,
    encoding: str = PLANALTO_CONSTITUTION_ENCODING,
) -> DecodedSourceDocument:
    """Confere SHA-256 antes de produzir uma projeção Unicode estrita."""
    computed_sha256 = sha256_hex(raw_bytes)
    if computed_sha256 != expected_sha256:
        raise SourceDocumentIntegrityError(
            "Integridade do SourceDocument inválida: "
            f"SHA-256 esperado={expected_sha256}, calculado={computed_sha256}."
        )

    started_at = perf_counter()
    try:
        text = raw_bytes.decode(encoding, errors="strict")
    except UnicodeDecodeError as exc:
        raise SourceDocumentDecodingError(
            f"Falha no decoding estrito com encoding {encoding!r}."
        ) from exc

    return DecodedSourceDocument(
        source_document_id=source_document_id,
        content_hash_sha256=computed_sha256,
        source_url=source_url,
        encoding=encoding,
        text=text,
        decoding_duration_ms=(perf_counter() - started_at) * 1000,
    )
