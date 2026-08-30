"""Bootstrap do corpus v0.2 sem rede, Ollama ou banco real."""

from types import SimpleNamespace

from consultor_juridico.cli.interactive.bootstrap import run_bootstrap
from consultor_juridico.infrastructure.corpus import PARSER_VERSION


def _patch_database(
    monkeypatch,
    *,
    connected: bool = True,
    ready: bool = False,
    parser_version: str | None = None,
):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.db_service.check_db_status",
        lambda: {"connected": connected},
    )
    migrated: list[bool] = []
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.db_service.run_migrations",
        lambda: migrated.append(True),
    )
    repository = SimpleNamespace(
        status=lambda: SimpleNamespace(
            ready=ready,
            parser_version=parser_version,
        )
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.corpus_repository",
        lambda: repository,
    )
    return migrated


def test_bootstrap_skips_expensive_build_when_corpus_is_ready(monkeypatch):
    migrated = _patch_database(monkeypatch, ready=True, parser_version=PARSER_VERSION)
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.corpus_builder",
        lambda: (_ for _ in ()).throw(AssertionError("build não deveria executar")),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.retrieval_index_builder",
        lambda: SimpleNamespace(
            execute=lambda: SimpleNamespace(embedded=0, model="fake", dimensions=768)
        ),
    )
    events = list(run_bootstrap())
    assert migrated == [True]
    assert events[-1].message.startswith("ALREADY_READY")


def test_bootstrap_builds_corpus_and_missing_embeddings(monkeypatch):
    _patch_database(monkeypatch)
    result = SimpleNamespace(
        outcome=SimpleNamespace(value="CREATED"), provisions=100, search_units=200
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.corpus_builder",
        lambda: SimpleNamespace(execute=lambda: result),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.retrieval_index_builder",
        lambda: SimpleNamespace(
            execute=lambda: SimpleNamespace(embedded=200, model="fake", dimensions=768)
        ),
    )
    events = list(run_bootstrap())
    assert [event.step for event in events] == [
        "db",
        "db",
        "corpus",
        "corpus",
        "index",
        "index",
        "all",
    ]
    assert events[-1].message.startswith("PREPARED")


def test_bootstrap_fails_closed_when_database_is_offline(monkeypatch):
    _patch_database(monkeypatch, connected=False)
    events = list(run_bootstrap())
    assert len(events) == 1
    assert events[0].state == "failed"


def test_bootstrap_fails_closed_when_embedding_index_fails(monkeypatch):
    _patch_database(monkeypatch, ready=True, parser_version=PARSER_VERSION)
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.retrieval_index_builder",
        lambda: SimpleNamespace(
            execute=lambda: (_ for _ in ()).throw(RuntimeError("offline"))
        ),
    )
    events = list(run_bootstrap())
    assert events[-1].step == "index"
    assert events[-1].state == "failed"


def test_bootstrap_rebuilds_ready_corpus_with_stale_projection(monkeypatch):
    _patch_database(monkeypatch, ready=True, parser_version="constitutional-corpus-v2")
    result = SimpleNamespace(
        outcome=SimpleNamespace(value="CREATED"), provisions=100, search_units=190
    )
    builds: list[bool] = []
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.corpus_builder",
        lambda: SimpleNamespace(
            execute=lambda: builds.append(True) or result,
        ),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.retrieval_index_builder",
        lambda: SimpleNamespace(execute=lambda: SimpleNamespace(embedded=190)),
    )

    events = list(run_bootstrap())

    assert builds == [True]
    assert any(event.step == "corpus" for event in events)
    assert events[-1].message.startswith("PREPARED")


def test_bootstrap_retry_continues_after_interrupted_corpus_build(monkeypatch):
    _patch_database(monkeypatch)
    attempts = iter((RuntimeError("falha induzida"), None))
    result = SimpleNamespace(
        outcome=SimpleNamespace(value="CREATED"), provisions=100, search_units=200
    )

    def execute():
        failure = next(attempts)
        if failure is not None:
            raise failure
        return result

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.corpus_builder",
        lambda: SimpleNamespace(execute=execute),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.retrieval_index_builder",
        lambda: SimpleNamespace(execute=lambda: SimpleNamespace(embedded=200)),
    )

    first = list(run_bootstrap())
    second = list(run_bootstrap())

    assert first[-1].step == "corpus" and first[-1].state == "failed"
    assert second[-1].step == "all" and second[-1].state == "success"
