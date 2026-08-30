"""Modelo imutável do corpus contextual da v0.2."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class ProvisionType(StrEnum):
    PREAMBLE = "PREAMBLE"
    TITLE = "TITLE"
    CHAPTER = "CHAPTER"
    SECTION = "SECTION"
    SUBSECTION = "SUBSECTION"
    ARTICLE = "ARTICLE"
    CAPUT = "CAPUT"
    PARAGRAPH = "PARAGRAPH"
    INCISO = "INCISO"
    ALINEA = "ALINEA"
    ITEM = "ITEM"


class SearchUnitType(StrEnum):
    DOCUMENT_METADATA = "DOCUMENT_METADATA"
    ARTICLE = "ARTICLE"
    CONTEXTUAL_PROVISION = "CONTEXTUAL_PROVISION"


class DuplicateProvisionStableKey(ValueError):
    """Indica duas ocorrências ativas para a mesma identidade normativa."""

    def __init__(
        self,
        stable_key: str,
        first_locator: str | None,
        second_locator: str | None,
    ) -> None:
        self.stable_key = stable_key
        self.first_locator = first_locator
        self.second_locator = second_locator
        super().__init__(
            "Stable key duplicada antes da persistência: "
            f"{stable_key}; primeira={first_locator}; segunda={second_locator}."
        )


class CorpusIdentityConflict(ValueError):
    """Indica identidade natural persistida com significado incompatível."""

    def __init__(self, entity: str, natural_key: str, detail: str) -> None:
        self.entity = entity
        self.natural_key = natural_key
        super().__init__(
            f"Conflito de identidade em {entity} ({natural_key}): {detail}."
        )


class SourceSnapshotNotFound(LookupError):
    """Indica que a captura imutável solicitada não existe no corpus."""

    def __init__(self, sha256: str) -> None:
        self.sha256 = sha256
        super().__init__(f"SourceSnapshot não encontrado: {sha256}.")


class SourceSnapshotIntegrityError(ValueError):
    """Indica divergência entre o payload persistido e seu SHA-256 factual."""

    def __init__(self, expected_sha256: str, actual_sha256: str) -> None:
        self.expected_sha256 = expected_sha256
        self.actual_sha256 = actual_sha256
        super().__init__(
            "Integridade do SourceSnapshot inválida: "
            f"esperado={expected_sha256}; calculado={actual_sha256}."
        )


@dataclass(frozen=True, slots=True)
class SourceCapture:
    source_name: str
    official_url: str
    requested_url: str
    final_url: str
    fetched_at: datetime
    raw_bytes: bytes
    sha256: str
    etag: str | None = None
    last_modified: str | None = None
    content_type: str | None = None

    def __post_init__(self) -> None:
        if not self.raw_bytes:
            raise ValueError("Captura oficial não pode estar vazia.")
        digest = hashlib.sha256(self.raw_bytes).hexdigest()
        if digest != self.sha256:
            raise ValueError("SHA-256 da captura não corresponde aos bytes.")


@dataclass(frozen=True, slots=True)
class ParsedMetadata:
    kind: str
    citation_text: str
    source_locator: str
    promulgation_date: date | None = None


@dataclass(frozen=True, slots=True)
class ParsedProvision:
    stable_key: str
    provision_type: ProvisionType
    label: str | None
    document_order: int
    citation_text: str
    source_locator: str | None
    children: tuple[ParsedProvision, ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.stable_key.strip()
            or not self.citation_text.strip()
            or self.document_order < 1
        ):
            raise ValueError("Provision exige identidade, texto e ordem positiva.")


@dataclass(frozen=True, slots=True)
class ParsedAct:
    code: str
    title: str
    act_type: str
    root_provisions: tuple[ParsedProvision, ...]
    metadata: tuple[ParsedMetadata, ...] = ()
    promulgation_date: date | None = None


@dataclass(frozen=True, slots=True)
class ParsedCorpus:
    acts: tuple[ParsedAct, ...]
    parser_version: str


@dataclass(frozen=True, slots=True)
class SearchUnitDraft:
    unit_type: SearchUnitType
    stable_reference: str
    anchor_stable_key: str | None
    search_text: str
    content_hash: str
    document_order: int
    provision_stable_keys: tuple[str, ...]
    source_locator: str | None = None
    source_excerpt: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.search_text.strip()
            or not self.stable_reference.strip()
            or len(self.content_hash) != 64
            or self.document_order < 1
        ):
            raise ValueError("SearchUnit exige texto, hash SHA-256 e ordem positiva.")


def technical_label(value: str) -> str:
    """Normaliza somente labels estruturais usadas em identidade."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    compact = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value).strip("-")
    return compact.upper() or "SEM-ROTULO"


def provision_stable_key(
    act_code: str,
    provision_type: ProvisionType,
    label: str | None,
    parent_key: str | None = None,
) -> str:
    token = provision_type.value
    if provision_type is not ProvisionType.PREAMBLE:
        token = f"{token}:{technical_label(label or '')}"
    return f"{parent_key}/{token}" if parent_key else f"{act_code}/{token}"


def search_unit_hash(
    *,
    unit_type: SearchUnitType,
    act_code: str,
    version_hash: str,
    anchor_stable_key: str | None,
    search_text: str,
) -> str:
    canonical = json.dumps(
        {
            "unit_type": unit_type.value,
            "act_code": act_code,
            "version_hash": version_hash,
            "anchor": anchor_stable_key,
            "search_text": search_text,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def act_version_hash(act_code: str, snapshot_sha256: str, parser_version: str) -> str:
    value = f"{act_code}\n{snapshot_sha256}\n{parser_version}"
    return hashlib.sha256(value.encode()).hexdigest()
