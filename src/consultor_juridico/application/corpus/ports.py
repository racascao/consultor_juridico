"""Boundaries reais da aquisição, parsing e persistência do corpus."""

from dataclasses import dataclass
from typing import Protocol

from consultor_juridico.domain import ParsedCorpus, SearchUnitDraft, SourceCapture


@dataclass(frozen=True, slots=True)
class CorpusStatus:
    ready: bool
    snapshots: int
    active_snapshot_sha256: str | None
    legal_acts: int
    act_versions: int
    provisions_by_act: tuple[tuple[str, int], ...]
    search_units_by_type: tuple[tuple[str, int], ...]
    parser_version: str | None


@dataclass(frozen=True, slots=True)
class MaterializedCorpus:
    created: bool
    snapshot_sha256: str
    act_versions: int
    provisions: int
    search_units: int


class SourceFetcher(Protocol):
    def fetch(self) -> SourceCapture: ...


class SourceSnapshotReader(Protocol):
    def read_by_sha256(self, snapshot_sha256: str) -> SourceCapture: ...


class CorpusParser(Protocol):
    def parse(self, capture: SourceCapture) -> ParsedCorpus: ...


class CorpusRepository(Protocol):
    def materialize(
        self,
        capture: SourceCapture,
        parsed: ParsedCorpus,
        search_units: tuple[tuple[str, tuple[SearchUnitDraft, ...]], ...],
    ) -> MaterializedCorpus: ...

    def status(self) -> CorpusStatus: ...
