"""Orquestração de aquisição e materialização sem acoplamento entre HTTP e parser."""

from consultor_juridico.application.corpus.ports import (
    AcquisitionResult,
    CorpusMaterializer,
    MaterializationResult,
    SnapshotRepository,
    SourceAcquirer,
    SourceSpec,
)
from consultor_juridico.domain.corpus import (
    PARSER_NAME,
    PARSER_VERSION,
    PROJECTION_NAME,
    PROJECTION_VERSION,
    LegalActIdentity,
    ParsedDocument,
    ProjectedSearchUnit,
    VersionIdentity,
)


class AcquireOfficialSource:
    def __init__(self, acquirer: SourceAcquirer, snapshots: SnapshotRepository) -> None:
        self._acquirer = acquirer
        self._snapshots = snapshots

    def execute(self, source: SourceSpec) -> AcquisitionResult:
        previous = self._snapshots.latest_for_source(source)
        response = self._acquirer.acquire(
            source.official_url,
            etag=previous.etag if previous else None,
            last_modified=previous.last_modified if previous else None,
        )
        if response.status_code == 304:
            if previous is None:
                raise RuntimeError("Servidor retornou 304 sem snapshot anterior")
            return AcquisitionResult(previous, 304, created=False, reused=True)
        snapshot, created = self._snapshots.store(source, response)
        return AcquisitionResult(
            snapshot, response.status_code, created=created, reused=not created
        )


class MaterializeFromSnapshot:
    """Materialização explicitamente offline a partir de snapshot persistido."""

    def __init__(
        self,
        snapshots: SnapshotRepository,
        materializer: CorpusMaterializer,
        parser,
        projector,
    ) -> None:
        self._snapshots = snapshots
        self._materializer = materializer
        self._parser = parser
        self._projector = projector

    def execute(
        self, *, snapshot_sha: str, source: SourceSpec, act: LegalActIdentity
    ) -> MaterializationResult:
        snapshot = self._snapshots.by_sha(snapshot_sha, source.encoding)
        if snapshot is None:
            raise LookupError(f"SourceSnapshot não encontrado: {snapshot_sha}")
        parsed: ParsedDocument = self._parser.parse(
            snapshot.raw_bytes, encoding=snapshot.encoding
        )
        projected: tuple[ProjectedSearchUnit, ...] = self._projector.project(parsed)
        identity = VersionIdentity(
            legal_act_natural_key=act.natural_key,
            source_snapshot_sha256=snapshot.sha256,
            parser_name=PARSER_NAME,
            parser_version=PARSER_VERSION,
            projection_name=PROJECTION_NAME,
            projection_version=PROJECTION_VERSION,
        )
        return self._materializer.materialize(
            act=act,
            snapshot=snapshot,
            identity=identity,
            parsed=parsed,
            projected=projected,
        )
