"""Testes unitários para a CLI interativa, readiness e bootstrap."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
from typer.testing import CliRunner

from consultor_juridico.cli.interactive.bootstrap import (
    BootstrapEvent,
    pull_ollama_model,
    run_bootstrap,
)
from consultor_juridico.cli.interactive.readiness import (
    SystemReadiness,
    check_readiness,
)
from consultor_juridico.consultation.types import (
    CitationReference,
    ConsultationOutcome,
    ConsultationResult,
    GeneratedClaim,
)
from consultor_juridico.retrieval.types import IndexingResult, RetrievalCandidate


def _ready(**overrides) -> SystemReadiness:
    values = {
        "database_connected": True,
        "schema_ready": True,
        "ollama_connected": True,
        "llm_model_ready": True,
        "embedding_model_ready": True,
        "source_ready": True,
        "parsing_ready": True,
        "index_ready": True,
    }
    values.update(overrides)
    return SystemReadiness(**values)


def _prompt_sequence(answers: list[str]):
    remaining = list(answers)

    def ask(*_args, **kwargs):
        if remaining:
            return remaining.pop(0)
        return kwargs.get("default", "0")

    return ask


class _SessionContext:
    def __init__(self, session=None):
        self.session = session or MagicMock()

    def __enter__(self):
        return self.session

    def __exit__(self, *_args):
        return None


def _ready_cli(monkeypatch, cli_runner: CliRunner, cli_app, answers: list[str]):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.check_readiness",
        lambda: _ready(),
    )
    monkeypatch.setattr("rich.prompt.Prompt.ask", _prompt_sequence(answers))
    return cli_runner.invoke(cli_app, [], obj={"force_interactive": True})


def test_system_readiness_requires_all_flags():
    assert _ready().is_ready is True
    assert _ready(index_ready=False).is_ready is False


def test_check_readiness_reports_disconnected_database(monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.readiness.db_service.check_db_status",
        lambda: {
            "connected": False,
            "tables": [],
            "alembic_version": None,
        },
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.readiness.httpx.get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(httpx.ConnectError("offline")),
    )

    readiness = check_readiness()
    assert readiness.database_connected is False
    assert readiness.schema_ready is False
    assert readiness.ollama_connected is False
    assert readiness.is_ready is False


def test_check_readiness_detects_models_and_index(monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.readiness.db_service.check_db_status",
        lambda: {
            "connected": True,
            "tables": [
                "alembic_version",
                "source_documents",
                "legal_acts",
                "legal_versions",
                "legal_provisions",
                "legal_elements",
                "chunks",
                "embeddings",
            ],
            "alembic_version": "005_normative_identity_occurrences",
        },
    )
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "models": [{"name": "llama3.2:latest"}, {"name": "nomic-embed-text:latest"}]
    }
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.readiness.httpx.get",
        lambda *_args, **_kwargs: response,
    )

    session = MagicMock()
    session.scalar.side_effect = [
        1,
        SimpleNamespace(status="COMPLETED"),
        3389,
        3389,
    ]
    session.scalars.return_value.all.return_value = [
        SimpleNamespace(id=uuid.uuid4()),
        SimpleNamespace(id=uuid.uuid4()),
    ]
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.readiness.SessionLocal",
        lambda: _SessionContext(session),
    )

    readiness = check_readiness()
    assert readiness.ollama_connected is True
    assert readiness.llm_model_ready is True
    assert readiness.embedding_model_ready is True
    assert readiness.source_ready is True
    assert readiness.parsing_ready is True
    assert readiness.index_ready is True
    assert readiness.is_ready is True


def test_run_bootstrap_is_noop_when_ready(monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.check_readiness",
        lambda: _ready(),
    )
    events = list(run_bootstrap())
    assert len(events) == 1
    assert events[0].step == "all"
    assert events[0].state == "success"


def test_run_bootstrap_fails_when_database_is_offline(monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.check_readiness",
        lambda: _ready(database_connected=False, schema_ready=False),
    )
    events = list(run_bootstrap())
    assert events[0].step == "db"
    assert events[0].state == "failed"


def test_run_bootstrap_fails_when_ollama_is_offline(monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.check_readiness",
        lambda: _ready(ollama_connected=False, llm_model_ready=False),
    )
    events = list(run_bootstrap())
    assert events[0].step == "ollama"
    assert events[0].state == "failed"


def test_run_bootstrap_applies_pending_steps(monkeypatch):
    states = [
        _ready(
            schema_ready=False,
            llm_model_ready=False,
            embedding_model_ready=False,
            source_ready=False,
            parsing_ready=False,
            index_ready=False,
        ),
        _ready(parsing_ready=False, index_ready=False),
        _ready(index_ready=False),
    ]

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.check_readiness",
        lambda: states.pop(0),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.db_service.run_migrations",
        lambda: None,
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.pull_ollama_model",
        lambda _name: None,
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.run_planalto_ingestion",
        lambda: SimpleNamespace(document_id="doc-id", sha256="a" * 64),
    )
    session = MagicMock()
    session.scalar.return_value = SimpleNamespace(id="doc-id")
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.SessionLocal",
        lambda: _SessionContext(session),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.materialize_constitution",
        lambda *_args, **_kwargs: SimpleNamespace(provision_count=4096),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.build_search_index",
        lambda *_args, **_kwargs: IndexingResult(
            outcome="CREATED",
            chunks=3389,
            embeddings=3389,
            dimensions=768,
            strategy_name="legal_occurrence_current_v1",
            provider_name="ollama",
            model_name="nomic-embed-text",
            model_version="latest",
        ),
    )

    events = list(run_bootstrap())
    steps = [(event.step, event.state) for event in events]
    assert ("db", "success") in steps
    assert ("models", "success") in steps
    assert ("ingest", "success") in steps
    assert ("parse", "success") in steps
    assert ("index", "success") in steps
    assert steps[-1] == ("all", "success")


def test_pull_ollama_model_consumes_stream(monkeypatch):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.iter_lines.return_value = iter(["{}", "{}"])
    stream = _SessionContext(response)
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.httpx.stream",
        lambda *_args, **_kwargs: stream,
    )
    pull_ollama_model("llama3.2")


def test_interactive_non_tty(cli_runner: CliRunner, cli_app, monkeypatch):
    """Se o stdin/stdout não for TTY, deve exibir help e sair sem iniciar o loop."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)

    result = cli_runner.invoke(cli_app, [])
    assert result.exit_code == 0
    assert "Mecanismo CLI-first de consulta jurídica" in result.stdout
    assert "Comandos" in result.stdout


def test_interactive_tty_already_ready(cli_runner: CliRunner, cli_app, monkeypatch):
    """Se o ambiente estiver pronto, vai ao menu principal e permite sair (0)."""
    result = _ready_cli(monkeypatch, cli_runner, cli_app, ["0"])
    assert result.exit_code == 0
    assert "Menu Principal" in result.stdout
    assert "Saindo... Obrigado por usar o Consultor Jurídico!" in result.stdout


def test_interactive_keyboard_interrupt_exits_cleanly(
    cli_runner: CliRunner, cli_app, monkeypatch
):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.check_readiness",
        lambda: _ready(),
    )

    def ask(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("rich.prompt.Prompt.ask", ask)
    result = cli_runner.invoke(cli_app, [], obj={"force_interactive": True})
    assert result.exit_code == 0
    assert "Saindo... Obrigado por usar o Consultor Jurídico!" in result.stdout


def test_interactive_bootstrap_success(cli_runner: CliRunner, cli_app, monkeypatch):
    """Se o ambiente estiver incompleto, roda o bootstrap e vai para o menu."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.check_readiness",
        lambda: _ready(schema_ready=False, source_ready=False, parsing_ready=False),
    )

    def mock_bootstrap():
        yield BootstrapEvent("db", "running", "Aplicando migrations...")
        yield BootstrapEvent("db", "success", "Banco atualizado.")
        yield BootstrapEvent("all", "success", "Sistema totalmente preparado.")

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.run_bootstrap", mock_bootstrap
    )
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *_args, **_kwargs: "0")

    result = cli_runner.invoke(cli_app, [], obj={"force_interactive": True})
    assert result.exit_code == 0
    assert "Primeira execução ou ambiente incompleto detectado" in result.stdout
    assert "Aplicando migrations..." in result.stdout
    assert "Banco atualizado." in result.stdout
    assert "Sistema totalmente preparado." in result.stdout
    assert "Menu Principal" in result.stdout


def test_interactive_bootstrap_failed(cli_runner: CliRunner, cli_app, monkeypatch):
    """Se o bootstrap falhar, deve mostrar o painel de erro e sair com erro 1."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.check_readiness",
        lambda: _ready(database_connected=False, schema_ready=False),
    )

    def mock_bootstrap():
        yield BootstrapEvent(
            "db",
            "failed",
            "Banco de dados PostgreSQL inacessível.\n"
            "Verifique se o container está rodando.",
        )

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.run_bootstrap", mock_bootstrap
    )

    result = cli_runner.invoke(cli_app, [], obj={"force_interactive": True})
    assert result.exit_code == 1
    assert "Falha na Preparação" in result.stdout
    assert "Banco de dados PostgreSQL inacessível" in result.stdout


def test_interactive_consultation_answered(cli_runner: CliRunner, cli_app, monkeypatch):
    session = MagicMock()
    session.scalars.return_value.all.return_value = [
        SimpleNamespace(id=uuid.uuid4()),
        SimpleNamespace(id=uuid.uuid4()),
    ]
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.SessionLocal",
        lambda: _SessionContext(session),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.run_consultation",
        lambda *_args, **_kwargs: ConsultationResult(
            ConsultationOutcome.ANSWERED,
            uuid.uuid4(),
            "A manifestação do pensamento é livre.",
            (GeneratedClaim("C1", "A manifestação é livre.", ("EV001",)),),
            (
                CitationReference(
                    "C1",
                    "EV001",
                    "CF/88, INCISO IV",
                    "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
                ),
            ),
        ),
    )

    result = _ready_cli(monkeypatch, cli_runner, cli_app, ["1", "liberdade", "", "0"])
    assert result.exit_code == 0
    assert "Fazer Consulta Jurídica" in result.stdout
    assert "Resposta Fundamentada" in result.stdout
    assert "EV001" in result.stdout
    assert "CF/88, INCISO IV" in result.stdout


def test_interactive_consultation_abstains(cli_runner: CliRunner, cli_app, monkeypatch):
    session = MagicMock()
    session.scalars.return_value.all.return_value = [
        SimpleNamespace(id=uuid.uuid4()),
        SimpleNamespace(id=uuid.uuid4()),
    ]
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.SessionLocal",
        lambda: _SessionContext(session),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.run_consultation",
        lambda *_args, **_kwargs: ConsultationResult(
            ConsultationOutcome.ABSTAINED,
            uuid.uuid4(),
            "Evidência insuficiente.",
            (),
            (),
        ),
    )

    result = _ready_cli(
        monkeypatch, cli_runner, cli_app, ["1", "fora do corpus", "", "0"]
    )
    assert result.exit_code == 0
    assert "Evidência Insuficiente" in result.stdout


def test_interactive_consultation_rejects_empty_question(
    cli_runner: CliRunner, cli_app, monkeypatch
):
    result = _ready_cli(monkeypatch, cli_runner, cli_app, ["1", "   ", "", "0"])
    assert result.exit_code == 0
    assert "Pergunta vazia" in result.stdout


def test_interactive_exploration_lists_candidates(
    cli_runner: CliRunner, cli_app, monkeypatch
):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.hybrid_search",
        lambda *_args, **_kwargs: [
            RetrievalCandidate(
                chunk_id=uuid.uuid4(),
                legal_element_id=uuid.uuid4(),
                legal_provision_id=uuid.uuid4(),
                legal_act="CF/88",
                element_type="INCISO",
                number_label="IV",
                identity_key="cf88:art5:iv",
                chunk_text=(
                    "é livre a manifestação do pensamento, sendo vedado o anonimato"
                ),
            )
        ],
    )
    result = _ready_cli(
        monkeypatch, cli_runner, cli_app, ["2", "manifestação do pensamento", "", "0"]
    )
    assert result.exit_code == 0
    assert "Explorar / Pesquisar a Constituição" in result.stdout
    assert "Principais dispositivos encontrados" in result.stdout
    assert "manifestação do pensamento" in result.stdout


def test_interactive_status_and_diagnostics(
    cli_runner: CliRunner, cli_app, monkeypatch
):
    session = MagicMock()
    session.scalars.return_value.all.return_value = [
        SimpleNamespace(id=uuid.uuid4()),
        SimpleNamespace(id=uuid.uuid4()),
    ]
    session.scalar.return_value = 3389
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.SessionLocal",
        lambda: _SessionContext(session),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.materialization_status",
        lambda _session: {"legal_elements": 6775, "legal_provisions": 4096},
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.db_service.check_db_status",
        lambda: {
            "database_url": "postgresql+psycopg://consultor@db/consultor_juridico",
            "alembic_version": "005",
        },
    )

    result = _ready_cli(
        monkeypatch, cli_runner, cli_app, ["3", "", "4", "", "5", "", "0"]
    )
    assert result.exit_code == 0
    assert "Estado da Base Jurídica" in result.stdout
    assert "6775 elementos jurídicos" in result.stdout
    assert "Diagnóstico Técnico do Sistema" in result.stdout
    assert "PostgreSQL (pgvector)" in result.stdout
    assert "Sobre o Projeto" in result.stdout
    assert "não substitui" in result.stdout


def test_aliases_portuguese_ingest(cli_runner: CliRunner, cli_app, monkeypatch):
    """Testa se o alias 'ingest constituicao' funciona como 'ingest constitution'."""
    download = SimpleNamespace(
        requested_url="https://example.test/doc",
        final_url="https://example.test/final",
        status_code=200,
        canonical_bytes=b"payload",
    )
    result_value = SimpleNamespace(
        outcome=SimpleNamespace(value="CREATED"),
        document_id="some-uuid",
        sha256="a" * 64,
        download=download,
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.main.run_planalto_ingestion",
        lambda *args, **kwargs: result_value,
    )

    result = cli_runner.invoke(cli_app, ["ingest", "constituicao"])
    assert result.exit_code == 0
    assert "CREATED" in result.stdout
    assert "a" * 64 in result.stdout


def test_aliases_portuguese_parse(cli_runner: CliRunner, cli_app, monkeypatch):
    """Testa se o alias 'parse constituicao' funciona como 'parse constitution'."""
    value = SimpleNamespace(
        outcome=SimpleNamespace(value="CREATED"),
        parsing_run_id="run-uuid",
        legal_version_ids=("v1-uuid", "v2-uuid"),
        provision_count=100,
        element_count=200,
        audit_fingerprint="f" * 64,
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.main.materialize_constitution",
        lambda *args, **kwargs: value,
    )
    mock_session = MagicMock()
    mock_session.scalar.return_value = SimpleNamespace(id="doc-uuid")
    monkeypatch.setattr(
        "consultor_juridico.cli.main.SessionLocal", lambda: mock_session
    )

    result = cli_runner.invoke(cli_app, ["parse", "constituicao"])
    assert result.exit_code == 0
    assert "CREATED" in result.stdout
    assert "100" in result.stdout
    assert "200" in result.stdout


def test_interactive_exploration_rejects_empty_query(
    cli_runner: CliRunner, cli_app, monkeypatch
):
    result = _ready_cli(monkeypatch, cli_runner, cli_app, ["2", "   ", "", "0"])
    assert result.exit_code == 0
    assert "Pesquisa vazia" in result.stdout


def test_interactive_exploration_no_results(
    cli_runner: CliRunner, cli_app, monkeypatch
):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.hybrid_search",
        lambda *_args, **_kwargs: [],
    )
    result = _ready_cli(
        monkeypatch, cli_runner, cli_app, ["2", "termo inexistente", "", "0"]
    )
    assert result.exit_code == 0
    assert "Nenhum dispositivo relevante encontrado" in result.stdout


def test_interactive_exploration_handles_error(
    cli_runner: CliRunner, cli_app, monkeypatch
):
    def raising(*_args, **_kwargs):
        raise RuntimeError("falha de retrieval")

    monkeypatch.setattr("consultor_juridico.cli.interactive.app.hybrid_search", raising)
    result = _ready_cli(
        monkeypatch, cli_runner, cli_app, ["2", "qualquer termo", "", "0"]
    )
    assert result.exit_code == 0
    assert "Erro na pesquisa" in result.stdout


def test_interactive_consultation_handles_technical_error(
    cli_runner: CliRunner, cli_app, monkeypatch
):
    session = MagicMock()
    session.scalars.return_value.all.return_value = [
        SimpleNamespace(id=uuid.uuid4()),
        SimpleNamespace(id=uuid.uuid4()),
    ]
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.SessionLocal",
        lambda: _SessionContext(session),
    )

    def raising(*_args, **_kwargs):
        raise RuntimeError("ollama offline")

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.run_consultation", raising
    )
    result = _ready_cli(monkeypatch, cli_runner, cli_app, ["1", "pergunta", "", "0"])
    assert result.exit_code == 0
    assert "Falha Técnica" in result.stdout


def test_interactive_consultation_missing_active_versions(
    cli_runner: CliRunner, cli_app, monkeypatch
):
    session = MagicMock()
    session.scalars.return_value.all.return_value = [SimpleNamespace(id=uuid.uuid4())]
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.SessionLocal",
        lambda: _SessionContext(session),
    )
    result = _ready_cli(monkeypatch, cli_runner, cli_app, ["1", "pergunta", "", "0"])
    assert result.exit_code == 0
    assert "índice jurídico não possui versões ativas" in result.stdout


def test_interactive_eof_exits_cleanly(cli_runner: CliRunner, cli_app, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.check_readiness",
        lambda: _ready(),
    )

    def ask(*_args, **_kwargs):
        raise EOFError

    monkeypatch.setattr("rich.prompt.Prompt.ask", ask)
    result = cli_runner.invoke(cli_app, [], obj={"force_interactive": True})
    assert result.exit_code == 0
    assert "Saindo... Obrigado por usar o Consultor Jurídico!" in result.stdout


def test_check_readiness_handles_session_exception(monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.readiness.db_service.check_db_status",
        lambda: {
            "connected": True,
            "tables": [
                "alembic_version",
                "source_documents",
                "legal_acts",
                "legal_versions",
                "legal_provisions",
                "legal_elements",
                "chunks",
                "embeddings",
            ],
            "alembic_version": "005_normative_identity_occurrences",
        },
    )
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "models": [{"name": "llama3.2:latest"}, {"name": "nomic-embed-text:latest"}]
    }
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.readiness.httpx.get",
        lambda *_args, **_kwargs: response,
    )

    def raising_session():
        raise RuntimeError("db failure")

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.readiness.SessionLocal", raising_session
    )
    readiness = check_readiness()
    assert readiness.source_ready is False
    assert readiness.parsing_ready is False
    assert readiness.index_ready is False


def test_run_bootstrap_fails_when_migration_fails(monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.check_readiness",
        lambda: _ready(schema_ready=False),
    )

    def failing_migration():
        raise RuntimeError("migration error")

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.db_service.run_migrations",
        failing_migration,
    )
    events = list(run_bootstrap())
    assert any(event.step == "db" and event.state == "failed" for event in events)


def test_run_bootstrap_fails_when_model_pull_fails(monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.check_readiness",
        lambda: _ready(llm_model_ready=False),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.pull_ollama_model",
        lambda _name: (_ for _ in ()).throw(RuntimeError("pull failed")),
    )
    events = list(run_bootstrap())
    assert any(event.step == "models" and event.state == "failed" for event in events)


def test_run_bootstrap_fails_when_ingest_fails(monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.check_readiness",
        lambda: _ready(source_ready=False),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.run_planalto_ingestion",
        lambda: (_ for _ in ()).throw(RuntimeError("ingest failed")),
    )
    events = list(run_bootstrap())
    assert any(event.step == "ingest" and event.state == "failed" for event in events)


def test_run_bootstrap_fails_when_parse_fails(monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.check_readiness",
        lambda: _ready(parsing_ready=False),
    )
    session = MagicMock()
    session.scalar.return_value = SimpleNamespace(id="doc-id")
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.SessionLocal",
        lambda: _SessionContext(session),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.materialize_constitution",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("parse failed")),
    )
    events = list(run_bootstrap())
    assert any(event.step == "parse" and event.state == "failed" for event in events)


def test_run_bootstrap_fails_when_index_fails(monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.check_readiness",
        lambda: _ready(index_ready=False),
    )
    session = MagicMock()
    session.scalar.return_value = SimpleNamespace(id="doc-id")
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.SessionLocal",
        lambda: _SessionContext(session),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.build_search_index",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("index failed")),
    )
    events = list(run_bootstrap())
    assert any(event.step == "index" and event.state == "failed" for event in events)


def test_interactive_status_handles_db_error(
    cli_runner: CliRunner, cli_app, monkeypatch
):
    def raising_status(_session):
        raise RuntimeError("db down")

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.materialization_status", raising_status
    )
    session = MagicMock()
    session.scalars.return_value.all.return_value = []
    session.scalar.return_value = 0
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.SessionLocal",
        lambda: _SessionContext(session),
    )
    result = _ready_cli(monkeypatch, cli_runner, cli_app, ["3", "", "0"])
    assert result.exit_code == 0
    assert "Erro ao recuperar informações do banco" in result.stdout
