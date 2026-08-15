"""Fixtures globais do pytest."""

import pytest
from typer.testing import CliRunner

from consultor_juridico.cli.main import app


@pytest.fixture
def cli_runner() -> CliRunner:
    """Retorna um runner de testes para a CLI Typer."""
    return CliRunner()


@pytest.fixture
def cli_app():
    """Retorna a instância da aplicação Typer CLI."""
    return app
