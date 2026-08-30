"""Caso de uso pequeno que coordena captura, parsing e materialização."""

from dataclasses import dataclass
from enum import StrEnum

from consultor_juridico.application.corpus.builder import SearchUnitBuilder
from consultor_juridico.application.corpus.ports import (
    CorpusParser,
    CorpusRepository,
    SourceFetcher,
    SourceSnapshotReader,
)
from consultor_juridico.application.corpus.validation import (
    validate_unique_provision_keys,
)
from consultor_juridico.domain import SourceCapture, act_version_hash


class CorpusBuildOutcome(StrEnum):
    CREATED = "CREATED"
    ALREADY_READY = "ALREADY_READY"


@dataclass(frozen=True, slots=True)
class BuildCorpusResult:
    outcome: CorpusBuildOutcome
    snapshot_sha256: str
    act_versions: int
    provisions: int
    search_units: int


class BuildCorpusUseCase:
    def __init__(
        self,
        fetcher: SourceFetcher,
        parser: CorpusParser,
        repository: CorpusRepository,
        search_unit_builder: SearchUnitBuilder,
    ) -> None:
        self._fetcher = fetcher
        self._materializer = MaterializeCorpusUseCase(
            parser, repository, search_unit_builder
        )

    def execute(self) -> BuildCorpusResult:
        return self._materializer.execute(self._fetcher.fetch())


class MaterializeCorpusUseCase:
    """Interpreta e persiste uma captura já obtida, sem adquirir sua fonte."""

    def __init__(
        self,
        parser: CorpusParser,
        repository: CorpusRepository,
        search_unit_builder: SearchUnitBuilder,
    ) -> None:
        self._parser = parser
        self._repository = repository
        self._search_unit_builder = search_unit_builder

    def execute(self, capture: SourceCapture) -> BuildCorpusResult:
        parsed = self._parser.parse(capture)
        validate_unique_provision_keys(parsed)
        units = tuple(
            (
                act.code,
                self._search_unit_builder.build(
                    act,
                    act_version_hash(act.code, capture.sha256, parsed.parser_version),
                ),
            )
            for act in parsed.acts
        )
        materialized = self._repository.materialize(capture, parsed, units)
        outcome = (
            CorpusBuildOutcome.CREATED
            if materialized.created
            else CorpusBuildOutcome.ALREADY_READY
        )
        return BuildCorpusResult(
            outcome,
            materialized.snapshot_sha256,
            materialized.act_versions,
            materialized.provisions,
            materialized.search_units,
        )


class RematerializeCorpusFromSnapshotUseCase:
    """Reprojeta uma captura persistida sem permitir aquisição remota."""

    def __init__(
        self,
        snapshot_reader: SourceSnapshotReader,
        materializer: MaterializeCorpusUseCase,
    ) -> None:
        self._snapshot_reader = snapshot_reader
        self._materializer = materializer

    def execute(self, snapshot_sha256: str) -> BuildCorpusResult:
        capture = self._snapshot_reader.read_by_sha256(snapshot_sha256)
        return self._materializer.execute(capture)
