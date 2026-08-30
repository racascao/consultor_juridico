"""Serviço de gerenciamento do banco de dados e execução de migrations."""

from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from consultor_juridico.db.session import engine, get_database_url


def get_alembic_config() -> Config:
    """Carrega e retorna a configuração do Alembic para o projeto."""
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    alembic_ini_path = root_dir / "alembic.ini"
    if not alembic_ini_path.exists():
        alembic_ini_path = Path("alembic.ini").resolve()

    config = Config(str(alembic_ini_path))
    config.set_main_option("sqlalchemy.url", get_database_url())
    return config


def run_migrations() -> None:
    """Executa as migrations pendentes no banco de dados para a versão 'head'."""
    config = get_alembic_config()
    command.upgrade(config, "head")


def check_db_status() -> dict[str, Any]:
    """Verifica a conexão com o banco de dados e retorna o status atual."""
    status_info: dict[str, Any] = {
        "connected": False,
        "database_url": get_database_url(),
        "tables": [],
        "alembic_version": None,
    }

    try:
        with engine.connect() as connection:
            status_info["connected"] = True

            # Lista de tabelas existentes
            inspector = inspect(connection)
            status_info["tables"] = inspector.get_table_names()

            # Versão do Alembic
            if "alembic_version" in status_info["tables"]:
                result = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).fetchone()
                if result:
                    status_info["alembic_version"] = result[0]

    except Exception as exc:
        status_info["error"] = str(exc)

    return status_info
