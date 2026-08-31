"""Contratos puros do corpus jurídico da Fase 0."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

PARSER_NAME = "planalto-lei-structural"
PARSER_VERSION = "1"
PROJECTION_NAME = "provision-text"
PROJECTION_VERSION = "1"


class ProvisionType(StrEnum):
    DOCUMENT_ROOT = "DOCUMENT_ROOT"
    CHAPTER = "CHAPTER"
    ARTICLE = "ARTICLE"
    CAPUT = "CAPUT"
    PARAGRAPH = "PARAGRAPH"
    INCISO = "INCISO"


class LegalStatus(StrEnum):
    IN_FORCE = "IN_FORCE"
    VETOED = "VETOED"


class IgnoreReason(StrEnum):
    EMPTY_PRESENTATION = "EMPTY_PRESENTATION"
    NON_LEGAL_PAGE_CHROME = "NON_LEGAL_PAGE_CHROME"


@dataclass(frozen=True, slots=True)
class SourceLocator:
    paragraph_start: int
    paragraph_end: int
    anchor_name: str | None = None

    def __post_init__(self) -> None:
        if self.paragraph_start < 0 or self.paragraph_end < self.paragraph_start:
            raise ValueError("Intervalo de parágrafos inválido")

    def as_dict(self) -> dict[str, int | str]:
        value: dict[str, int | str] = {
            "paragraph_start": self.paragraph_start,
            "paragraph_end": self.paragraph_end,
        }
        if self.anchor_name:
            value["anchor_name"] = self.anchor_name
        return value


@dataclass(frozen=True, slots=True)
class ParsedProvision:
    provision_type: ProvisionType
    stable_key: str
    number_label: str | None
    citation_text: str | None
    source_locator: SourceLocator
    document_order: int
    legal_status: LegalStatus = LegalStatus.IN_FORCE
    parent_stable_key: str | None = None

    @property
    def content_hash(self) -> str:
        return sha256((self.citation_text or "").encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class CoverageRecord:
    paragraph_index: int
    consumed_by: str | None = None
    ignored_reason: IgnoreReason | None = None

    def __post_init__(self) -> None:
        if (self.consumed_by is None) == (self.ignored_reason is None):
            raise ValueError("Cobertura deve ser consumida ou ignorada, exclusivamente")


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    provisions: tuple[ParsedProvision, ...]
    coverage: tuple[CoverageRecord, ...]
    total_dom_paragraphs: int
    non_empty_paragraphs: int

    @property
    def consumed_paragraphs(self) -> int:
        return sum(record.consumed_by is not None for record in self.coverage)

    @property
    def explicitly_ignored_paragraphs(self) -> int:
        return sum(record.ignored_reason is not None for record in self.coverage)


@dataclass(frozen=True, slots=True)
class ProjectedSearchUnit:
    unit_key: str
    search_text: str
    provision_stable_keys: tuple[str, ...]

    @property
    def content_hash(self) -> str:
        return sha256(self.search_text.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class LegalActIdentity:
    act_code: str
    jurisdiction: str
    act_type: str
    number: str
    year: int
    title: str

    @property
    def natural_key(self) -> str:
        return self.act_code


@dataclass(frozen=True, slots=True)
class VersionIdentity:
    legal_act_natural_key: str
    source_snapshot_sha256: str
    parser_name: str
    parser_version: str
    projection_name: str
    projection_version: str

    @property
    def version_hash(self) -> str:
        payload = json.dumps(
            {
                "legal_act_natural_key": self.legal_act_natural_key,
                "parser_name": self.parser_name,
                "parser_version": self.parser_version,
                "projection_name": self.projection_name,
                "projection_version": self.projection_version,
                "source_snapshot_sha256": self.source_snapshot_sha256,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class SnapshotData:
    id: UUID
    source_id: UUID
    sha256: str
    raw_bytes: bytes
    encoding: str


class CorpusError(RuntimeError):
    """Erro base do corpus."""


class SourceDocumentDecodingError(CorpusError):
    """Bytes não podem ser decodificados pelo contrato da fonte."""


class UnsupportedSourceStructure(CorpusError):
    """Estrutura potencialmente jurídica não reconhecida."""

    def __init__(self, paragraph_index: int, excerpt: str, reason: str) -> None:
        super().__init__(
            f"Parágrafo {paragraph_index} não suportado ({reason}): {excerpt[:160]}"
        )
        self.paragraph_index = paragraph_index
        self.excerpt = excerpt[:160]
        self.reason = reason


def decode_strict(raw_bytes: bytes, encoding: str) -> str:
    try:
        return raw_bytes.decode(encoding, errors="strict")
    except UnicodeDecodeError as exc:
        raise SourceDocumentDecodingError(
            f"Falha no decoding estrito com {encoding}: byte {exc.start}"
        ) from exc


def through_first_html_close(text: str) -> str:
    end = text.lower().find("</html>")
    if end < 0:
        raise UnsupportedSourceStructure(-1, text[:160], "fechamento </html> ausente")
    return text[: end + len("</html>")]
