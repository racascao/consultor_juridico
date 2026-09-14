from collections.abc import Iterator
from contextlib import contextmanager
from io import StringIO
from pathlib import Path

from rich.console import Console
from typer.testing import CliRunner

from consultor_juridico.cli.display import run_with_query_feedback
from consultor_juridico.cli.interactive import app as interactive
from consultor_juridico.cli.main import app
from consultor_juridico.domain.rag import QueryMode
from consultor_juridico.services.bootstrap import (
    BootstrapEvent,
    BootstrapFailure,
    BootstrapOrchestrator,
    BootstrapReadiness,
    BootstrapState,
)


def readiness(**overrides: bool) -> BootstrapReadiness:
    values = {
        "database": True,
        "migrations": True,
        "corpus": True,
        "retrieval": True,
        "ollama": True,
        "model": True,
    }
    values.update(overrides)
    return BootstrapReadiness(**values)


def test_console_script_has_only_official_name() -> None:
    pyproject = Path("pyproject.toml").read_text()
    scripts = pyproject.split("[project.scripts]", 1)[1].split("[", 1)[0]
    assert 'consultor_juridico = "consultor_juridico.cli.main:app"' in scripts
    assert "consultor-juridico" not in scripts


def test_help_exposes_product_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("bootstrap", "consult", "status", "tutorial"):
        assert command in result.stdout


def test_non_tty_without_command_fails_without_blocking() -> None:
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 2
    assert "requer um terminal" in result.stdout


def test_scriptable_case_application_never_opens_database(monkeypatch) -> None:
    monkeypatch.setattr(
        "consultor_juridico.cli.main._current_version_hash",
        lambda: (_ for _ in ()).throw(AssertionError("database accessed")),
    )
    result = CliRunner().invoke(
        app,
        ["consult", "Recebi uma decisão", "--mode", "case-application", "--trace"],
    )
    assert result.exit_code == 0
    assert "Decisão: CLARIFY" in result.stdout
    assert "retrieval=NOT_EXECUTED" in result.stdout
    assert "answerer=NOT_EXECUTED" in result.stdout


def test_bootstrap_is_noop_when_ready() -> None:
    calls: list[str] = []
    orchestrator = BootstrapOrchestrator(
        inspect=lambda: readiness(),
        migrate=lambda: calls.append("migrate"),
        prepare_corpus=lambda: calls.append("corpus"),
        prepare_model=lambda: calls.append("model"),
    )
    events = list(orchestrator.run())
    assert calls == []
    assert events[-1].message == "Já preparado"


def test_bootstrap_recovers_partial_state_in_order() -> None:
    states: Iterator[BootstrapReadiness] = iter(
        (
            readiness(migrations=False, corpus=False, retrieval=False, model=False),
            readiness(corpus=False, retrieval=False, model=False),
            readiness(model=False),
            readiness(),
            readiness(),
        )
    )
    calls: list[str] = []
    orchestrator = BootstrapOrchestrator(
        inspect=lambda: next(states),
        migrate=lambda: calls.append("migrate"),
        prepare_corpus=lambda: calls.append("corpus"),
        prepare_model=lambda: calls.append("model"),
    )
    events = list(orchestrator.run())
    assert calls == ["migrate", "corpus", "model"]
    assert events[-1].message == "Sistema pronto"


def test_bootstrap_fails_closed_without_database() -> None:
    orchestrator = BootstrapOrchestrator(
        inspect=lambda: readiness(database=False),
        migrate=lambda: None,
        prepare_corpus=lambda: None,
        prepare_model=lambda: None,
    )
    try:
        list(orchestrator.run())
    except BootstrapFailure as error:
        assert str(error) == "PostgreSQL indisponível"
    else:
        raise AssertionError("bootstrap deveria falhar fechado")


def test_bootstrap_reports_unavailable_official_source() -> None:
    orchestrator = BootstrapOrchestrator(
        inspect=lambda: readiness(corpus=False, retrieval=False),
        migrate=lambda: None,
        prepare_corpus=lambda: (_ for _ in ()).throw(RuntimeError("Planalto offline")),
        prepare_model=lambda: None,
    )
    try:
        list(orchestrator.run())
    except BootstrapFailure as error:
        assert "Planalto offline" in str(error)
    else:
        raise AssertionError("bootstrap deveria falhar fechado")


def test_interactive_routes_modes_explicitly(monkeypatch) -> None:
    answers = iter(("1", "Qual é o prazo?", "2", "Recebi uma decisão", "7"))
    monkeypatch.setattr(
        interactive.Prompt, "ask", lambda *args, **kwargs: next(answers)
    )
    calls: list[tuple[str, QueryMode]] = []
    interactive.run_interactive_cli(
        console=Console(file=StringIO()),
        readiness=readiness,
        consult=lambda question, mode: calls.append((question, mode)),
    )
    assert calls == [
        ("Qual é o prazo?", QueryMode.LEGAL_RULE),
        ("Recebi uma decisão", QueryMode.CASE_APPLICATION),
    ]


def test_header_contains_product_model_and_version() -> None:
    output = StringIO()
    interactive.show_banner(Console(file=output, force_terminal=False))
    rendered = output.getvalue()
    assert "CONSULTOR JURÍDICO" in rendered
    assert "MVP2" in rendered
    assert "Lei 9.784/1999" in rendered
    assert "Gemma4:12b" in rendered
    assert "0.2.0.dev0" in rendered


class FeedbackConsole:
    def __init__(self, *, terminal: bool) -> None:
        self.is_terminal = terminal
        self.status_calls = 0
        self.messages: list[str] = []

    @contextmanager
    def status(self, *args, **kwargs):
        self.status_calls += 1
        yield

    def print(self, message: str) -> None:
        self.messages.append(message)


def test_legal_rule_loading_is_tty_only() -> None:
    terminal = FeedbackConsole(terminal=True)
    plain = FeedbackConsole(terminal=False)
    assert run_with_query_feedback(terminal, QueryMode.LEGAL_RULE, lambda: 7) == 7
    assert run_with_query_feedback(plain, QueryMode.LEGAL_RULE, lambda: 8) == 8
    assert terminal.status_calls == 1
    assert any("Resposta preparada" in item for item in terminal.messages)
    assert plain.status_calls == 0
    assert plain.messages == []


def test_case_application_has_no_artificial_loading() -> None:
    terminal = FeedbackConsole(terminal=True)
    assert run_with_query_feedback(terminal, QueryMode.CASE_APPLICATION, lambda: 9) == 9
    assert terminal.status_calls == 0


def test_bootstrap_success_explains_one_shot_container(monkeypatch) -> None:
    class ReadyBootstrap:
        def run(self):
            return iter(())

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.compose_bootstrap",
        lambda: ReadyBootstrap(),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.readiness.check_readiness", readiness
    )
    result = CliRunner().invoke(app, ["bootstrap"])
    assert result.exit_code == 0
    assert "CONSULTOR JURÍDICO PRONTO" in result.stdout
    assert "encerrado" in result.stdout
    assert "código" in result.stdout
    assert "não é uma falha" in result.stdout
    assert "docker compose run --rm app consultor_juridico" in result.stdout


def test_bootstrap_highlights_operational_milestones(monkeypatch) -> None:
    class MilestoneBootstrap:
        def run(self):
            for step, running, complete in (
                ("migrations", "Aplicando", "Aplicadas"),
                ("corpus", "Preparando", "Preparado"),
                ("model", "Baixando", "Disponível"),
                ("system", "Validando", "Sistema pronto"),
            ):
                yield BootstrapEvent(step, BootstrapState.RUNNING, running)
                yield BootstrapEvent(step, BootstrapState.READY, complete)

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.bootstrap.compose_bootstrap",
        lambda: MilestoneBootstrap(),
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.readiness.check_readiness", readiness
    )
    result = CliRunner().invoke(app, ["bootstrap"])
    assert result.exit_code == 0
    for title in ("MIGRATIONS", "CORPUS", "MODELO", "SISTEMA"):
        assert title in result.stdout


def test_compose_preserves_ollama_gpu_configuration() -> None:
    compose = Path("docker-compose.yml").read_text()
    ollama = compose.split("  ollama:", 1)[1].split("  app:", 1)[0]
    assert "gpus: all" in ollama
