"""Testes para os comandos da CLI."""

import uuid
from types import SimpleNamespace

from typer.testing import CliRunner

from consultor_juridico import __version__
from consultor_juridico.ingestion.types import IngestionOutcome
from consultor_juridico.parsing.materialization import ParsingOutcome


class _SessionContext:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


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


def test_cli_parse_constitution_delegates_to_materialization(
    cli_runner: CliRunner, cli_app, monkeypatch
):
    document_id = uuid.uuid4()
    run_id = uuid.uuid4()
    value = SimpleNamespace(
        outcome=ParsingOutcome.CREATED,
        parsing_run_id=run_id,
        legal_version_ids=(uuid.uuid4(), uuid.uuid4()),
        provision_count=4096,
        element_count=6775,
        audit_fingerprint="d" * 64,
    )
    monkeypatch.setattr("consultor_juridico.cli.main.SessionLocal", _SessionContext)
    monkeypatch.setattr(
        "consultor_juridico.cli.main.materialize_constitution",
        lambda _session, selected_id: value if selected_id == document_id else None,
    )

    result = cli_runner.invoke(
        cli_app, ["parse", "constitution", "--document-id", str(document_id)]
    )
    assert result.exit_code == 0
    assert "CREATED" in result.stdout
    assert "4096" in result.stdout
    assert "6775" in result.stdout


def test_cli_parse_status_is_read_only(cli_runner: CliRunner, cli_app, monkeypatch):
    monkeypatch.setattr("consultor_juridico.cli.main.SessionLocal", _SessionContext)
    monkeypatch.setattr(
        "consultor_juridico.cli.main.materialization_status",
        lambda _session: {"parsing_runs": 1, "latest_status": "COMPLETED"},
    )

    result = cli_runner.invoke(cli_app, ["parse", "status"])
    assert result.exit_code == 0
    assert "parsing_runs=1" in result.stdout
    assert "latest_status=COMPLETED" in result.stdout


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
