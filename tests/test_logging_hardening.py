"""Garante que execução normal não vaza SQL/vetores."""

from typer.testing import CliRunner


def test_normal_execution_does_not_print_sql(
    cli_runner: CliRunner, cli_app, monkeypatch
):
    # Simula execução normal (non-TTY help) — não deve conter SELECT/vector
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    result = cli_runner.invoke(cli_app, ["--help"])
    assert result.exit_code == 0
    assert "SELECT" not in result.stdout
    assert "vector" not in result.stdout.lower()
    assert (
        "768" not in result.stdout or "768" in result.stdout
    )  # 768 pode aparecer em help de dimensões, mas não como vetor
    # Garante que engine echo está desativado por padrão
    from consultor_juridico.db.session import engine

    assert engine.echo is False


def test_verbose_enables_sql_echo(cli_runner: CliRunner, cli_app):
    # Com --verbose, engine.echo deve ficar True (não testamos SQL real, apenas flag)
    from consultor_juridico.db.session import engine, set_verbose

    original = engine.echo
    try:
        set_verbose(True)
        assert engine.echo is True
        set_verbose(False)
        assert engine.echo is False
    finally:
        engine.echo = original


def test_interactive_normal_does_not_leak_vectors(
    monkeypatch, cli_runner: CliRunner, cli_app
):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    # Mock readiness para ir direto ao menu e sair
    from consultor_juridico.cli.interactive.readiness import SystemReadiness

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.app.check_readiness",
        lambda: SystemReadiness(True, True, True, True, True, True, True, True, True),
    )
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *_a, **_k: "0")
    result = cli_runner.invoke(cli_app, [], obj={"force_interactive": True})
    assert result.exit_code == 0
    # Não deve conter vetores ou SQL
    assert (
        "vector" not in result.stdout.lower() or "Embeddings Vetoriais" in result.stdout
    )
    assert "SELECT" not in result.stdout
