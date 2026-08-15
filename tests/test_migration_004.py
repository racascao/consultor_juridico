"""Testes isolados de upgrade/downgrade da migration 004."""

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from consultor_juridico.db.session import get_database_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_EXECUTABLE = Path(sys.executable).with_name("alembic")


@pytest.fixture
def disposable_database_url():
    base_url = make_url(get_database_url())
    database_name = f"cj_m004_{uuid.uuid4().hex[:12]}"
    admin_url = base_url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    with admin_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')

    database_url = base_url.set(database=database_name)
    try:
        yield database_url
    finally:
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
        admin_engine.dispose()


def _run_alembic(database_url, *arguments: str, check: bool = True):
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url.render_as_string(hide_password=False)
    environment["DEBUG"] = "false"
    return subprocess.run(
        [str(ALEMBIC_EXECUTABLE), *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        check=check,
        capture_output=True,
        text=True,
    )


def _version(database_url) -> str:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        engine.dispose()


def _insert_document(connection, suffix: str):
    source_id = uuid.uuid4()
    document_id = uuid.uuid4()
    connection.execute(
        text("INSERT INTO sources (id, name, base_url) VALUES (:id, :name, :base_url)"),
        {
            "id": source_id,
            "name": f"Source {suffix}",
            "base_url": f"https://{suffix}.example",
        },
    )
    connection.execute(
        text(
            "INSERT INTO source_documents "
            "(id, source_id, url_source, raw_bytes, content_hash_sha256) "
            "VALUES (:id, :source_id, :url, :raw_bytes, :hash)"
        ),
        {
            "id": document_id,
            "source_id": source_id,
            "url": f"https://{suffix}.example/doc",
            "raw_bytes": b"document",
            "hash": f"hash-{suffix}",
        },
    )
    return document_id


def _insert_parsing_run(connection, document_id, suffix: str):
    parsing_run_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO parsing_runs "
            "(id, source_document_id, parser_name, parser_version) "
            "VALUES (:id, :document_id, 'parser', :version)"
        ),
        {"id": parsing_run_id, "document_id": document_id, "version": suffix},
    )
    return parsing_run_id


def _insert_legal_version(connection, document_id, parsing_run_id, suffix: str):
    legal_act_id = uuid.uuid4()
    version_id = uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO legal_acts (id, title, short_name, act_type) "
            "VALUES (:id, :title, :short_name, 'CONSTITUICAO')"
        ),
        {
            "id": legal_act_id,
            "title": f"Act {suffix}",
            "short_name": f"ACT-{suffix}",
        },
    )
    connection.execute(
        text(
            "INSERT INTO legal_versions "
            "(id, legal_act_id, source_document_id, parsing_run_id, version_label) "
            "VALUES (:id, :act_id, :document_id, :run_id, :label)"
        ),
        {
            "id": version_id,
            "act_id": legal_act_id,
            "document_id": document_id,
            "run_id": parsing_run_id,
            "label": f"Version {suffix}",
        },
    )
    return version_id


def test_migration_004_upgrade_downgrade_upgrade_cycle(disposable_database_url):
    _run_alembic(disposable_database_url, "upgrade", "003_ingestion_raw_storage")
    assert _version(disposable_database_url) == "003_ingestion_raw_storage"

    _run_alembic(disposable_database_url, "upgrade", "head")
    assert _version(disposable_database_url) == "004_frozen_parsing_model"

    _run_alembic(disposable_database_url, "downgrade", "003_ingestion_raw_storage")
    assert _version(disposable_database_url) == "003_ingestion_raw_storage"

    _run_alembic(disposable_database_url, "upgrade", "head")
    assert _version(disposable_database_url) == "004_frozen_parsing_model"


def test_migration_004_schema_names(disposable_database_url):
    _run_alembic(disposable_database_url, "upgrade", "head")
    engine = create_engine(disposable_database_url)
    try:
        inspector = inspect(engine)
        assert "parsing_runs" in inspector.get_table_names()
        columns = {c["name"]: c for c in inspector.get_columns("legal_elements")}
        assert columns["document_order"]["nullable"] is False
        assert columns["normalized_text"]["nullable"] is False
        assert "ordinal" not in columns
        assert "is_revoked" not in columns

        constraint_names = {
            constraint["name"]
            for table in ("parsing_runs", "legal_versions", "legal_elements")
            for getter in (
                inspector.get_check_constraints,
                inspector.get_unique_constraints,
                inspector.get_foreign_keys,
            )
            for constraint in getter(table)
        }
        assert "uq_parsing_runs_source_parser" in constraint_names
        assert "fk_legal_versions_parsing_run_source_document" in constraint_names
        assert "fk_legal_elements_parent_version_composite" in constraint_names
        assert "ck_legal_elements_source_locator_object" in constraint_names

        index_names = {
            index["name"]
            for table in ("legal_versions", "legal_elements")
            for index in inspector.get_indexes(table)
        }
        assert "uq_legal_versions_one_active_per_act" in index_names
        assert "uq_legal_elements_one_root_per_version" in index_names
    finally:
        engine.dispose()


@pytest.mark.parametrize("derived_level", ["version", "element"])
def test_migration_004_upgrade_guard_rejects_legacy_data(
    disposable_database_url, derived_level: str
):
    _run_alembic(disposable_database_url, "upgrade", "003_ingestion_raw_storage")
    engine = create_engine(disposable_database_url)
    try:
        with engine.begin() as connection:
            document_id = _insert_document(connection, "legacy")
            legal_act_id = uuid.uuid4()
            connection.execute(
                text(
                    "INSERT INTO legal_acts (id, title, short_name, act_type) "
                    "VALUES (:id, 'Legacy', 'LEGACY', 'CONSTITUICAO')"
                ),
                {"id": legal_act_id},
            )
            version_id = uuid.uuid4()
            connection.execute(
                text(
                    "INSERT INTO legal_versions "
                    "(id, legal_act_id, source_document_id, version_label) "
                    "VALUES (:id, :act_id, :document_id, 'Legacy')"
                ),
                {
                    "id": version_id,
                    "act_id": legal_act_id,
                    "document_id": document_id,
                },
            )
            if derived_level == "element":
                connection.execute(
                    text(
                        "INSERT INTO legal_elements "
                        "(id, legal_version_id, element_type, raw_text) "
                        "VALUES (:id, :version_id, 'ARTICLE', 'Art. 1º')"
                    ),
                    {"id": uuid.uuid4(), "version_id": version_id},
                )
    finally:
        engine.dispose()

    result = _run_alembic(disposable_database_url, "upgrade", "head", check=False)
    assert result.returncode != 0
    assert "Upgrade 004 recusado" in result.stderr
    assert _version(disposable_database_url) == "003_ingestion_raw_storage"


@pytest.mark.parametrize("derived_level", ["run", "version", "element"])
def test_migration_004_downgrade_guard_rejects_derived_data(
    disposable_database_url, derived_level: str
):
    _run_alembic(disposable_database_url, "upgrade", "head")
    engine = create_engine(disposable_database_url)
    try:
        with engine.begin() as connection:
            document_id = _insert_document(connection, derived_level)
            parsing_run_id = _insert_parsing_run(connection, document_id, derived_level)
            if derived_level in {"version", "element"}:
                version_id = _insert_legal_version(
                    connection, document_id, parsing_run_id, derived_level
                )
            if derived_level == "element":
                connection.execute(
                    text(
                        "INSERT INTO legal_elements "
                        "(id, legal_version_id, element_type, document_order, "
                        "raw_text, normalized_text, text_status, source_locator) "
                        "VALUES (:id, :version_id, 'DOCUMENT_ROOT', 1, "
                        "'Root', 'Root', 'CURRENT', CAST(:locator AS jsonb))"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "version_id": version_id,
                        "locator": '{"block_index": 0}',
                    },
                )
    finally:
        engine.dispose()

    result = _run_alembic(
        disposable_database_url,
        "downgrade",
        "003_ingestion_raw_storage",
        check=False,
    )
    assert result.returncode != 0
    assert "Downgrade 004 recusado" in result.stderr
    assert _version(disposable_database_url) == "004_frozen_parsing_model"
