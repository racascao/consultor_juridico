"""Testes para os comandos da CLI."""

from typer.testing import CliRunner

from consultor_juridico import __version__


def test_cli_version(cli_runner: CliRunner, cli_app):
    """Testa se o comando `version` exibe a versão correta."""
    result = cli_runner.invoke(cli_app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_cli_db_status(cli_runner: CliRunner, cli_app):
    """Testa se o subcomando `db status` executa sem erros."""
    result = cli_runner.invoke(cli_app, ["db", "status"])
    assert result.exit_code == 0
    assert "Status do Banco de Dados" in result.stdout


def test_cli_ingest_status(cli_runner: CliRunner, cli_app):
    """Testa se o subcomando `ingest status` executa sem erros."""
    result = cli_runner.invoke(cli_app, ["ingest", "status"])
    assert result.exit_code == 0
    assert "Status das Ingestões" in result.stdout


def test_cli_document_list(cli_runner: CliRunner, cli_app):
    """Testa se o subcomando `document list` executa sem erros."""
    result = cli_runner.invoke(cli_app, ["document", "list"])
    assert result.exit_code == 0
    assert "Documentos armazenados" in result.stdout


def test_cli_search(cli_runner: CliRunner, cli_app):
    """Testa o comando `search`."""
    result = cli_runner.invoke(cli_app, ["search", "direitos fundamentais"])
    assert result.exit_code == 0
    assert "Buscando por" in result.stdout


def test_cli_consult(cli_runner: CliRunner, cli_app):
    """Testa o comando `consult`."""
    result = cli_runner.invoke(cli_app, ["consult", "Quais os direitos fundamentais?"])
    assert result.exit_code == 0
    assert "Consultando" in result.stdout
