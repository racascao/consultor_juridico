"""Ports pequenos da fundação documental."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from consultor_juridico.domain.corpus import (
    LegalActIdentity,
    ParsedDocument,
    ProjectedSearchUnit,
    SnapshotData,
    VersionIdentity,
)


@dataclass(frozen=True, slots=True)
class SourceSpec:
    authority_code: str
    official_url: str
    name: str
    encoding: str


@dataclass(frozen=True, slots=True)
class AcquisitionResponse:
    status_code: int
    raw_bytes: bytes | None
    content_type: str | None
    etag: str | None
    last_modified: str | None


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    id: UUID
    source_id: UUID
    sha256: str
    raw_bytes: bytes
    byte_length: int
    content_type: str | None
    etag: str | None
    last_modified: str | None
    acquired_at: datetime


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    snapshot: SnapshotRecord
    status_code: int
    created: bool
    reused: bool


@dataclass(frozen=True, slots=True)
class MaterializationResult:
    act_version_id: UUID
    version_hash: str
    provision_count: int
    search_unit_count: int
    created: bool


class SourceAcquirer(Protocol):
    def acquire(
        self, url: str, *, etag: str | None, last_modified: str | None
    ) -> AcquisitionResponse: ...


class SnapshotRepository(Protocol):
    def latest_for_source(self, source: SourceSpec) -> SnapshotRecord | None: ...

    def store(
        self, source: SourceSpec, response: AcquisitionResponse
    ) -> tuple[SnapshotRecord, bool]: ...

    def by_sha(self, sha256_hex: str, encoding: str) -> SnapshotData | None: ...


class CorpusMaterializer(Protocol):
    def materialize(
        self,
        *,
        act: LegalActIdentity,
        snapshot: SnapshotData,
        identity: VersionIdentity,
        parsed: ParsedDocument,
        projected: tuple[ProjectedSearchUnit, ...],
    ) -> MaterializationResult: ...
