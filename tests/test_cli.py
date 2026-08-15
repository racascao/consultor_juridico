"""Testes para os comandos da CLI."""

import uuid
from types import SimpleNamespace

from typer.testing import CliRunner

from consultor_juridico import __version__
from consultor_juridico.ingestion.types import IngestionOutcome


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


def test_cli_ingest_status(cli_runner: CliRunner, cli_app, monkeypatch):
    """Testa se o subcomando `ingest status` executa sem erros."""
    monkeypatch.setattr("consultor_juridico.cli.main.get_ingestion_status", lambda: [])
    result = cli_runner.invoke(cli_app, ["ingest", "status"])
    assert result.exit_code == 0
    assert "Status das Ingestões" in result.stdout


def test_cli_ingest_constitution_delegates_to_service(
    cli_runner: CliRunner, cli_app, monkeypatch
):
    """A CLI apresenta o resultado produzido pelo serviço de aplicação."""
    download = SimpleNamespace(
        requested_url="https://example.test/doc",
        final_url="https://example.test/final",
        status_code=200,
        canonical_bytes=b"payload",
    )
    result_value = SimpleNamespace(
        outcome=IngestionOutcome.CREATED,
        document_id=uuid.uuid4(),
        sha256="a" * 64,
        download=download,
    )
    monkeypatch.setattr(
        "consultor_juridico.cli.main.run_planalto_ingestion", lambda: result_value
    )

    result = cli_runner.invoke(cli_app, ["ingest", "constitution"])
    assert result.exit_code == 0
    assert "CREATED" in result.stdout
    assert "a" * 64 in result.stdout


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
