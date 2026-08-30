"""Script de ambiente de migrações do Alembic."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, inspect, pool, text

from consultor_juridico.db.session import get_database_url
from consultor_juridico.infrastructure.corpus.models import CorpusBase

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = CorpusBase.metadata


def run_migrations_offline() -> None:
    """Executa migrações no modo offline."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrações no modo online conectando ao banco de dados."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _reject_legacy_database(connection)
        connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


def _reject_legacy_database(connection) -> None:
    if not inspect(connection).has_table("alembic_version"):
        return
    current = connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar()
    if current and current != "001_v02_initial_schema":
        raise RuntimeError(
            "Banco v0.1 detectado. A arquitetura v0.2 utiliza uma nova baseline "
            "de dados. Recrie deliberadamente o volume PostgreSQL para continuar."
        )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
