"""Contrato público da CLI do MVP2, sem rede ou inferência."""

from io import StringIO
from types import SimpleNamespace

from rich.console import Console

from consultor_juridico import __version__
from consultor_juridico.application.workflow import ProviderCall, WorkflowDiagnostics
from consultor_juridico.domain import EvidenceCandidate, SourceSnapshotNotFound


def test_cli_version(cli_runner, cli_app):
    result = cli_runner.invoke(cli_app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_cli_db_status(cli_runner, cli_app, monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.main.db_service.check_db_status",
        lambda: {
            "connected": True,
            "alembic_version": "001_v02_initial_schema",
            "tables": ["sources", "search_units"],
        },
    )
    result = cli_runner.invoke(cli_app, ["db", "status"])
    assert result.exit_code == 0
    assert "001_v02_initial_schema" in result.stdout


def test_cli_corpus_status(cli_runner, cli_app, monkeypatch):
    status = SimpleNamespace(
        ready=True,
        active_snapshot_sha256="a" * 64,
        provisions_by_act=(("CF88", 20),),
        search_units_by_type=(("ARTICLE", 20),),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.main.corpus_repository",
        lambda: SimpleNamespace(status=lambda: status),
    )
    result = cli_runner.invoke(cli_app, ["corpus", "status"])
    assert result.exit_code == 0
    assert "READY" in result.stdout
    assert "Provisions CF88: 20" in result.stdout


def test_cli_rematerializes_persisted_snapshot_without_http(
    cli_runner, cli_app, monkeypatch
):
    snapshot_sha = "a" * 64
    calls = []
    monkeypatch.setattr(
        "consultor_juridico.cli.main.db_service.run_migrations", lambda: None
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.main.corpus_rematerializer",
        lambda: SimpleNamespace(
            execute=lambda value: (
                calls.append(value)
                or SimpleNamespace(
                    outcome=SimpleNamespace(value="CREATED"),
                    snapshot_sha256=value,
                    provisions=12,
                    search_units=21,
                )
            )
        ),
    )

    result = cli_runner.invoke(
        cli_app, ["corpus", "rematerializar", "--snapshot-sha", snapshot_sha]
    )

    assert result.exit_code == 0
    assert calls == [snapshot_sha]
    assert "CREATED" in result.stdout
    assert snapshot_sha in result.stdout


def test_cli_rematerialization_fails_explicitly_for_unknown_snapshot(
    cli_runner, cli_app, monkeypatch
):
    snapshot_sha = "f" * 64
    monkeypatch.setattr(
        "consultor_juridico.cli.main.db_service.run_migrations", lambda: None
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.main.corpus_rematerializer",
        lambda: SimpleNamespace(
            execute=lambda _value: (_ for _ in ()).throw(
                SourceSnapshotNotFound(snapshot_sha)
            )
        ),
    )

    result = cli_runner.invoke(
        cli_app, ["corpus", "rematerializar", "--snapshot-sha", snapshot_sha]
    )

    assert result.exit_code == 1
    assert "SNAPSHOT_NOT_FOUND" in result.stdout


def test_cli_rematerialization_help_explains_persisted_source_and_no_http(
    cli_runner, cli_app
):
    result = cli_runner.invoke(cli_app, ["corpus", "rematerializar", "--help"])

    assert result.exit_code == 0
    assert "persistida" in result.stdout
    assert "sem acessar" in result.stdout
    assert "Planalto" in result.stdout


def test_cli_index_build(cli_runner, cli_app, monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.main.index_builder",
        lambda: SimpleNamespace(
            execute=lambda: SimpleNamespace(
                embedded=3, model="nomic-embed-text", dimensions=768
            )
        ),
    )
    result = cli_runner.invoke(cli_app, ["indice", "construir"])
    assert result.exit_code == 0
    assert "3" in result.stdout
    assert "768" in result.stdout


def test_cli_retrieval_trace_shows_all_ranks(cli_runner, cli_app, monkeypatch):
    candidate = EvidenceCandidate(
        "E1",
        "Texto constitucional.",
        "CF88/ARTICLE:14",
        "block:1",
        search_unit_type="ARTICLE",
        legal_act_code="CF88",
        stable_reference="CF88/ARTICLE:14",
        lexical_rank=2,
        vector_rank=1,
        fused_rank=1,
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.main.candidate_retriever",
        lambda: SimpleNamespace(retrieve=lambda _question, _limit: (candidate,)),
    )
    result = cli_runner.invoke(
        cli_app, ["retrieval", "rastrear", "O voto é facultativo?"]
    )
    assert result.exit_code == 0
    assert "CF88/ARTICLE:14" in result.stdout
    assert "ARTICLE" in result.stdout


def test_cli_has_no_v01_public_pipeline(cli_runner, cli_app):
    for legacy in ("ingest", "parse", "index", "consult"):
        result = cli_runner.invoke(cli_app, [legacy, "--help"])
        assert result.exit_code != 0


def test_cli_consultar_verbose_uses_real_diagnostic_entrypoint(
    cli_runner, cli_app, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.run_question",
        lambda question, *, verbose=False: calls.append((question, verbose)),
    )

    result = cli_runner.invoke(
        cli_app,
        ["consultar", "Alistamento militar é obrigatório?", "--verbose"],
    )

    assert result.exit_code == 0
    assert calls == [("Alistamento militar é obrigatório?", True)]


def test_verbose_diagnostics_never_exposes_prompts(monkeypatch):
    from consultor_juridico.cli.interactive import app as interactive_app

    output = StringIO()
    diagnostics = WorkflowDiagnostics()
    diagnostics.add_provider_call(
        ProviderCall(
            "chat",
            "consultation_model",
            1.0,
            321,
            "VALID",
            "PROVIDER_ERROR",
            model="ministral-3:3b",
            provider_error_category="HTTP_ERROR",
            provider_http_status=400,
            provider_message="Failed to initialize samplers: bad grammar",
        )
    )
    diagnostics.add_detail(
        "consultation_model", decision="ANSWER", selected_evidence_ids=("E1",)
    )
    monkeypatch.setattr(
        interactive_app,
        "console",
        Console(file=output, force_terminal=False, width=200),
    )

    interactive_app._show_diagnostics(diagnostics, "Pergunta de teste?")

    rendered = output.getvalue()
    assert "decision=ANSWER" in rendered
    assert "Ollama native" in rendered
    assert "consultation_model" in rendered
    assert "ministral-3:3b" in rendered
    assert "category=HTTP_ERROR" in rendered
    assert "status=400" in rendered
    assert "Failed to initialize samplers: bad grammar" in rendered
    assert "total=N/A" in rendered
    assert "Julgue somente se as evidências" not in rendered
    assert "system prompt" not in rendered.lower()
