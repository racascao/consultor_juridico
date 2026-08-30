"""Integração opt-in da baseline v0.2 em PostgreSQL descartável."""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from threading import Lock
from time import sleep
from types import SimpleNamespace

import pytest
from sqlalchemy import func, inspect, select, text

from consultor_juridico.application.corpus import (
    MaterializeCorpusUseCase,
    RematerializeCorpusFromSnapshotUseCase,
    SearchUnitBuilder,
)
from consultor_juridico.application.retrieval import (
    BuildRetrievalIndex,
    EmbeddingMode,
)
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.domain import (
    CorpusIdentityConflict,
    ParsedCorpus,
    SourceCapture,
    SourceSnapshotIntegrityError,
    SourceSnapshotNotFound,
)
from consultor_juridico.infrastructure.corpus import (
    ConstitutionCorpusParser,
    SqlAlchemyCorpusRepository,
)
from consultor_juridico.infrastructure.corpus.models import (
    ActVersionRecord,
    LegalActRecord,
    ProvisionRecord,
    SearchUnitEmbeddingRecord,
    SearchUnitRecord,
    SourceRecord,
    SourceSnapshotRecord,
)
from consultor_juridico.infrastructure.retrieval import PostgresRetrievalRepository
from consultor_juridico.services.db_service import run_migrations

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_V02_DB_INTEGRATION") != "1",
    reason="requer PostgreSQL v0.2 descartável explícito",
)


@pytest.fixture(autouse=True)
def _require_and_clear_disposable_database():
    """Impede que a integração opt-in toque o corpus persistente do usuário."""
    from consultor_juridico.db.session import engine

    with engine.connect() as connection:
        database_name = connection.scalar(text("SELECT current_database()"))
    if not str(database_name).endswith("_test"):
        pytest.fail(
            "RUN_V02_DB_INTEGRATION exige PostgreSQL descartável cujo nome termine "
            "em '_test'."
        )
    run_migrations()
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE search_unit_embeddings, search_unit_provisions, "
                "search_units, provisions, act_versions, legal_acts, "
                "source_snapshots, sources CASCADE"
            )
        )


def _parsed() -> ParsedCorpus:
    return ConstitutionCorpusParser().parse(
        _capture(
            Path("tests/fixtures/corpus/contextual_constitution.html").read_bytes()
        )
    )


def _capture(raw: bytes) -> SourceCapture:
    return SourceCapture(
        "Portal do Planalto",
        "https://www.planalto.gov.br",
        "https://example.test/constituicao.htm",
        "https://example.test/constituicao.htm",
        datetime.now(UTC),
        raw,
        hashlib.sha256(raw).hexdigest(),
    )


def _units(parsed: ParsedCorpus, snapshot_hash: str):
    builder = SearchUnitBuilder()
    from consultor_juridico.domain import act_version_hash

    return tuple(
        (
            act.code,
            builder.build(
                act,
                act_version_hash(act.code, snapshot_hash, parsed.parser_version),
            ),
        )
        for act in parsed.acts
    )


def test_v02_migration_repository_idempotence_and_versioning(monkeypatch):
    run_migrations()
    from consultor_juridico.db.session import engine

    assert set(inspect(engine).get_table_names()) >= {
        "sources",
        "source_snapshots",
        "legal_acts",
        "act_versions",
        "provisions",
        "search_units",
        "search_unit_provisions",
        "search_unit_embeddings",
    }
    repository = SqlAlchemyCorpusRepository(SessionLocal)
    raw = Path("tests/fixtures/corpus/contextual_constitution.html").read_bytes()
    first_capture = _capture(raw)
    with SessionLocal() as session, session.begin():
        persisted_source = SourceRecord(
            name="Planalto",
            official_url=first_capture.official_url,
        )
        session.add(persisted_source)
        session.flush()
        persisted_source_id = persisted_source.id

    empty_status = repository.status()
    assert empty_status.ready is False
    assert empty_status.provisions_by_act == ()
    assert empty_status.search_units_by_type == ()

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.db_service.check_db_status",
        lambda: {"connected": True},
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.db_service.run_migrations",
        lambda: None,
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.corpus_repository",
        lambda: repository,
    )
    bootstrap_result = SimpleNamespace(
        outcome=SimpleNamespace(value="CREATED"), provisions=1, search_units=1
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.corpus_builder",
        lambda: SimpleNamespace(execute=lambda: bootstrap_result),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.retrieval_index_builder",
        lambda: SimpleNamespace(execute=lambda: SimpleNamespace(embedded=0)),
    )
    from consultor_juridico.cli.interactive.bootstrap import run_bootstrap

    bootstrap_events = tuple(run_bootstrap())
    assert all(event.state != "failed" for event in bootstrap_events)

    parsed = _parsed()
    first_units = _units(parsed, first_capture.sha256)

    broken_first_act = first_units[0]
    broken_draft = replace(
        broken_first_act[1][0],
        provision_stable_keys=("CF88/IDENTIDADE:INEXISTENTE",),
    )
    broken_units = (
        (broken_first_act[0], (broken_draft, *broken_first_act[1][1:])),
        *first_units[1:],
    )
    with pytest.raises(KeyError, match="IDENTIDADE:INEXISTENTE"):
        repository.materialize(first_capture, parsed, broken_units)
    failed_status = repository.status()
    assert failed_status.snapshots == 0
    assert failed_status.act_versions == 0
    assert failed_status.provisions_by_act == ()
    assert failed_status.search_units_by_type == ()

    first = repository.materialize(first_capture, parsed, first_units)
    repeated = repository.materialize(first_capture, parsed, first_units)
    assert first.created is True
    assert repeated.created is False
    with SessionLocal() as session:
        sources = tuple(session.scalars(select(SourceRecord)).all())
        assert len(sources) == 1
        assert sources[0].id == persisted_source_id
        assert (
            session.scalar(select(func.count()).select_from(SourceSnapshotRecord)) == 1
        )
        assert session.scalar(select(func.count()).select_from(LegalActRecord)) == 2
        assert session.scalar(select(func.count()).select_from(ActVersionRecord)) == 2

    conflicting_source = replace(first_capture, source_name="Fonte incompatível")
    with pytest.raises(CorpusIdentityConflict, match="Conflito de identidade"):
        repository.materialize(conflicting_source, parsed, first_units)

    second_capture = _capture(raw + b"<!-- nova captura -->")
    repository.materialize(
        second_capture, parsed, _units(parsed, second_capture.sha256)
    )
    populated_status = repository.status()
    assert populated_status.ready is True
    expected_provisions = {
        act.code: sum(1 for root in act.root_provisions for _ in _walk(root))
        for act in parsed.acts
    }
    assert dict(populated_status.provisions_by_act) == expected_provisions
    active_units = _units(parsed, second_capture.sha256)
    expected_units: dict[str, int] = {}
    for _, drafts in active_units:
        for draft in drafts:
            expected_units[draft.unit_type.value] = (
                expected_units.get(draft.unit_type.value, 0) + 1
            )
    assert dict(populated_status.search_units_by_type) == expected_units
    with SessionLocal() as session:
        assert (
            session.scalar(select(func.count()).select_from(SourceSnapshotRecord)) == 2
        )
        assert session.scalar(select(func.count()).select_from(LegalActRecord)) == 2
        assert session.scalar(select(func.count()).select_from(ActVersionRecord)) == 4
        assert (
            session.scalar(
                select(func.count())
                .select_from(ActVersionRecord)
                .where(ActVersionRecord.active.is_(True))
            )
            == 2
        )
        active_snapshot_ids = set(
            session.scalars(
                select(ActVersionRecord.source_snapshot_id).where(
                    ActVersionRecord.active.is_(True)
                )
            ).all()
        )
        assert len(active_snapshot_ids) == 1
        assert session.scalar(select(func.count()).select_from(ProvisionRecord)) > 0
        assert session.scalar(select(func.count()).select_from(SearchUnitRecord)) > 0
        promulgation = session.scalar(
            select(SearchUnitRecord).where(
                SearchUnitRecord.unit_type == "DOCUMENT_METADATA",
                SearchUnitRecord.search_text.contains("5 de outubro de 1988"),
            )
        )
        assert promulgation is not None
        assert promulgation.source_locator.startswith("block:")
        assert promulgation.stable_reference == "CF88/METADATA:PROMULGATION_DATE"

    retrieval = PostgresRetrievalRepository(SessionLocal)
    lexical = retrieval.lexical("serviço militar obrigatório", 10)
    assert lexical
    assert any(item.stable_reference == "CF88/ARTICLE:143" for item in lexical)
    metadata_lexical = retrieval.lexical("5 outubro 1988", 10)
    assert any(
        item.stable_reference == "CF88/METADATA:PROMULGATION_DATE"
        for item in metadata_lexical
    )

    class FakeEmbeddingProvider:
        provider_name = "fake"
        model_name = "fake-768"
        dimensions = 768

        def embed(self, texts, mode):
            assert mode is EmbeddingMode.DOCUMENT
            return tuple((float(index),) * 768 for index, _ in enumerate(texts, 1))

    indexed = BuildRetrievalIndex(retrieval, FakeEmbeddingProvider()).execute()
    assert indexed.embedded > 0
    assert (
        BuildRetrievalIndex(retrieval, FakeEmbeddingProvider()).execute().embedded == 0
    )
    with SessionLocal() as session:
        assert session.scalar(
            select(func.count()).select_from(SearchUnitEmbeddingRecord)
        ) == session.scalar(
            select(func.count())
            .select_from(SearchUnitRecord)
            .join(
                ActVersionRecord,
                SearchUnitRecord.act_version_id == ActVersionRecord.id,
            )
            .where(ActVersionRecord.active.is_(True))
        )
    active_unit_count = sum(len(drafts) for _, drafts in active_units)
    vector = retrieval.vector((1.0,) * 768, "fake-768", 10)
    assert vector
    complete_vector_pool = retrieval.vector((1.0,) * 768, "fake-768", active_unit_count)
    assert any(
        item.stable_reference == "CF88/METADATA:PROMULGATION_DATE"
        for item in complete_vector_pool
    )

    class ControlledEmbeddingProvider:
        provider_name = "fake"
        model_name = "concurrent-768"
        dimensions = 768

        def __init__(self):
            self.calls = 0
            self._lock = Lock()

        def embed(self, texts, mode):
            assert mode is EmbeddingMode.DOCUMENT
            with self._lock:
                self.calls += 1
            sleep(0.005)
            return tuple((1.0,) * 768 for _ in texts)

    controlled = ControlledEmbeddingProvider()
    with ThreadPoolExecutor(max_workers=2) as executor:
        concurrent_results = tuple(
            executor.map(
                lambda _: BuildRetrievalIndex(
                    retrieval, controlled, batch_size=2
                ).execute(),
                range(2),
            )
        )
    assert sorted(item.embedded for item in concurrent_results) == [
        0,
        active_unit_count,
    ]
    assert controlled.calls == ceil(active_unit_count / 2)

    class PartialFailureProvider(ControlledEmbeddingProvider):
        model_name = "partial-768"

        def embed(self, texts, mode):
            if self.calls == 1:
                self.calls += 1
                raise RuntimeError("falha induzida depois do primeiro lote")
            return super().embed(texts, mode)

    partial = PartialFailureProvider()
    with pytest.raises(RuntimeError, match="falha induzida"):
        BuildRetrievalIndex(retrieval, partial, batch_size=2).execute()
    with SessionLocal() as session:
        persisted_partial = int(
            session.scalar(
                select(func.count())
                .select_from(SearchUnitEmbeddingRecord)
                .where(SearchUnitEmbeddingRecord.model == "partial-768")
            )
            or 0
        )
    assert persisted_partial == 2

    resumed_provider = ControlledEmbeddingProvider()
    resumed_provider.model_name = "partial-768"
    resumed = BuildRetrievalIndex(retrieval, resumed_provider, batch_size=2).execute()
    assert resumed.embedded == active_unit_count - persisted_partial

    concurrent_capture = _capture(raw + b"<!-- build concorrente -->")
    concurrent_units = _units(parsed, concurrent_capture.sha256)
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(
            executor.map(
                lambda _: repository.materialize(
                    concurrent_capture, parsed, concurrent_units
                ),
                range(2),
            )
        )
    assert sorted(item.created for item in outcomes) == [False, True]
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(SourceRecord)) == 1
        assert (
            session.scalar(select(func.count()).select_from(SourceSnapshotRecord)) == 3
        )
        assert session.scalar(select(func.count()).select_from(LegalActRecord)) == 2
        assert session.scalar(select(func.count()).select_from(ActVersionRecord)) == 6
    assert repository.status().ready is True


def test_source_snapshot_is_physically_immutable():
    capture = _capture("captura imutável".encode())
    source = SourceRecord(
        name=capture.source_name,
        official_url=capture.official_url,
    )
    with SessionLocal() as session:
        session.add(source)
        session.flush()
        session.add(
            SourceSnapshotRecord(
                source_id=source.id,
                requested_url=capture.requested_url,
                final_url=capture.final_url,
                fetched_at=capture.fetched_at,
                raw_bytes=capture.raw_bytes,
                sha256=capture.sha256,
            )
        )
        session.commit()
        snapshot = session.scalar(select(SourceSnapshotRecord).limit(1))
        snapshot.content_type = "mutated"
        with pytest.raises(ValueError, match="imutável"):
            session.commit()


class StaticParser:
    def __init__(self, parsed: ParsedCorpus) -> None:
        self.parsed = parsed
        self.captures: list[SourceCapture] = []

    def parse(self, capture: SourceCapture) -> ParsedCorpus:
        self.captures.append(capture)
        return self.parsed


def _materializer(repository, parsed):
    return MaterializeCorpusUseCase(
        StaticParser(parsed), repository, SearchUnitBuilder()
    )


def test_snapshot_reprojection_v2_to_v3_is_offline_atomic_and_idempotent(
    monkeypatch,
):
    repository = SqlAlchemyCorpusRepository(SessionLocal)
    raw = Path("tests/fixtures/corpus/contextual_constitution.html").read_bytes()
    capture = _capture(raw)
    current = _parsed()
    parsed_v2 = replace(current, parser_version="constitutional-corpus-v2")
    v2_materializer = _materializer(repository, parsed_v2)
    v2_result = v2_materializer.execute(capture)
    assert v2_result.outcome.value == "CREATED"

    http_calls: list[None] = []

    def unexpected_http(_self):
        http_calls.append(None)
        raise AssertionError("reprojeção tentou aquisição HTTP")

    monkeypatch.setattr(
        "consultor_juridico.infrastructure.corpus.source."
        "PlanaltoHttpSourceFetcher.fetch",
        unexpected_http,
    )
    parser_v3 = StaticParser(current)
    rematerializer = RematerializeCorpusFromSnapshotUseCase(
        repository,
        MaterializeCorpusUseCase(parser_v3, repository, SearchUnitBuilder()),
    )

    first = rematerializer.execute(capture.sha256)
    repeated = rematerializer.execute(capture.sha256)

    assert first.outcome.value == "CREATED"
    assert repeated.outcome.value == "ALREADY_READY"
    assert parser_v3.captures[0].raw_bytes == raw
    assert parser_v3.captures[0].sha256 == capture.sha256
    assert http_calls == []
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(SourceRecord)) == 1
        assert (
            session.scalar(select(func.count()).select_from(SourceSnapshotRecord)) == 1
        )
        assert session.scalar(select(func.count()).select_from(LegalActRecord)) == 2
        assert session.scalar(select(func.count()).select_from(ActVersionRecord)) == 4
        versions = tuple(
            session.scalars(
                select(ActVersionRecord).order_by(ActVersionRecord.parser_version)
            ).all()
        )
        assert {item.source_snapshot_id for item in versions} == {
            session.scalar(select(SourceSnapshotRecord.id))
        }
        assert (
            sum(item.parser_version == "constitutional-corpus-v2" for item in versions)
            == 2
        )
        assert (
            sum(item.parser_version == current.parser_version for item in versions) == 2
        )
        assert all(
            not item.active
            for item in versions
            if item.parser_version == "constitutional-corpus-v2"
        )
        assert all(
            item.active
            for item in versions
            if item.parser_version == current.parser_version
        )


def test_snapshot_reader_fails_explicitly_for_missing_or_corrupt_payload():
    repository = SqlAlchemyCorpusRepository(SessionLocal)
    with pytest.raises(SourceSnapshotNotFound):
        repository.read_by_sha256("f" * 64)

    expected_raw = b"payload esperado"
    expected_sha = hashlib.sha256(expected_raw).hexdigest()
    with SessionLocal() as session, session.begin():
        source = SourceRecord(
            name="Planalto",
            official_url="https://example.test/fonte-corrompida",
        )
        session.add(source)
        session.flush()
        session.add(
            SourceSnapshotRecord(
                source_id=source.id,
                requested_url="https://example.test/documento",
                final_url="https://example.test/documento",
                fetched_at=datetime.now(UTC),
                raw_bytes=b"payload corrompido",
                sha256=expected_sha,
            )
        )

    with pytest.raises(SourceSnapshotIntegrityError) as error:
        repository.read_by_sha256(expected_sha)
    assert error.value.expected_sha256 == expected_sha
    assert (
        error.value.actual_sha256 == hashlib.sha256(b"payload corrompido").hexdigest()
    )


def test_failed_v3_reprojection_rolls_back_and_retry_succeeds(monkeypatch):
    repository = SqlAlchemyCorpusRepository(SessionLocal)
    capture = _capture(
        Path("tests/fixtures/corpus/contextual_constitution.html").read_bytes()
    )
    current = _parsed()
    parsed_v2 = replace(current, parser_version="constitutional-corpus-v2")
    _materializer(repository, parsed_v2).execute(capture)
    original_search_units = repository._search_units
    calls = 0

    def fail_on_adct(session, version, drafts, provisions):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("falha induzida na segunda materialização")
        return original_search_units(session, version, drafts, provisions)

    monkeypatch.setattr(repository, "_search_units", fail_on_adct)
    rematerializer = RematerializeCorpusFromSnapshotUseCase(
        repository, _materializer(repository, current)
    )
    with pytest.raises(RuntimeError, match="falha induzida"):
        rematerializer.execute(capture.sha256)

    with SessionLocal() as session:
        versions_after_failure = tuple(session.scalars(select(ActVersionRecord)).all())
        assert len(versions_after_failure) == 2
        assert all(item.active for item in versions_after_failure)
        assert all(
            item.parser_version == "constitutional-corpus-v2"
            for item in versions_after_failure
        )
        assert (
            session.scalar(select(func.count()).select_from(SourceSnapshotRecord)) == 1
        )

    monkeypatch.setattr(repository, "_search_units", original_search_units)
    retried = rematerializer.execute(capture.sha256)
    assert retried.outcome.value == "CREATED"
    assert repository.status().parser_version == current.parser_version


def _walk(provision):
    yield provision
    for child in provision.children:
        yield from _walk(child)
