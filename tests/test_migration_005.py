"""Testes isolados da migration 005 e da acomodação do Alembic."""

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
    database_name = f"cj_m005_{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(
        base_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
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
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
        admin_engine.dispose()


def _alembic(database_url, *arguments: str, check: bool = True):
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


def _revision_and_length(database_url) -> tuple[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            revision = connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            length = connection.scalar(
                text(
                    "SELECT character_maximum_length FROM information_schema.columns "
                    "WHERE table_name='alembic_version' AND column_name='version_num'"
                )
            )
            return revision, length
    finally:
        engine.dispose()


def _insert_chain_004(
    connection, suffix: str
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    source_id = uuid.uuid4()
    document_id = uuid.uuid4()
    run_id = uuid.uuid4()
    act_id = uuid.uuid4()
    version_id = uuid.uuid4()
    connection.execute(
        text("INSERT INTO sources (id,name,base_url) VALUES (:id,:name,:url)"),
        {"id": source_id, "name": suffix, "url": f"https://{suffix}.example"},
    )
    connection.execute(
        text(
            "INSERT INTO source_documents "
            "(id,source_id,url_source,raw_bytes,content_hash_sha256) "
            "VALUES (:id,:source,:url,:raw,:hash)"
        ),
        {
            "id": document_id,
            "source": source_id,
            "url": f"https://{suffix}.example/doc",
            "raw": b"doc",
            "hash": f"hash-{suffix}",
        },
    )
    connection.execute(
        text(
            "INSERT INTO parsing_runs "
            "(id,source_document_id,parser_name,parser_version) "
            "VALUES (:id,:document,'parser',:version)"
        ),
        {"id": run_id, "document": document_id, "version": suffix},
    )
    connection.execute(
        text(
            "INSERT INTO legal_acts (id,title,short_name,act_type) "
            "VALUES (:id,:title,:short,'CONSTITUICAO')"
        ),
        {"id": act_id, "title": suffix, "short": f"A-{suffix}"},
    )
    connection.execute(
        text(
            "INSERT INTO legal_versions "
            "(id,legal_act_id,source_document_id,parsing_run_id,version_label) "
            "VALUES (:id,:act,:document,:run,:label)"
        ),
        {
            "id": version_id,
            "act": act_id,
            "document": document_id,
            "run": run_id,
            "label": suffix,
        },
    )
    return act_id, version_id, run_id


def test_upgrade_downgrade_upgrade_and_alembic_column(disposable_database_url):
    _alembic(disposable_database_url, "upgrade", "004_frozen_parsing_model")
    assert _revision_and_length(disposable_database_url) == (
        "004_frozen_parsing_model",
        32,
    )

    engine = create_engine(disposable_database_url)
    with engine.begin() as connection:
        _insert_chain_004(connection, "preserved")
    engine.dispose()

    _alembic(disposable_database_url, "upgrade", "head")
    assert _revision_and_length(disposable_database_url) == (
        "005_normative_identity_occurrences",
        64,
    )

    _alembic(disposable_database_url, "downgrade", "004_frozen_parsing_model")
    assert _revision_and_length(disposable_database_url) == (
        "004_frozen_parsing_model",
        64,
    )

    _alembic(disposable_database_url, "upgrade", "head")
    assert _revision_and_length(disposable_database_url) == (
        "005_normative_identity_occurrences",
        64,
    )
    engine = create_engine(disposable_database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM legal_versions")) == 1
            assert connection.scalar(text("SELECT count(*) FROM parsing_runs")) == 1
    finally:
        engine.dispose()


def test_schema_catalog_matches_frozen_names(disposable_database_url):
    _alembic(disposable_database_url, "upgrade", "head")
    engine = create_engine(disposable_database_url)
    try:
        inspector = inspect(engine)
        assert "legal_provisions" in inspector.get_table_names()
        columns = {
            column["name"]: column for column in inspector.get_columns("legal_elements")
        }
        assert columns["legal_act_id"]["nullable"] is False
        assert columns["legal_provision_id"]["nullable"] is True
        names = {
            item["name"]
            for table in ("legal_versions", "legal_provisions", "legal_elements")
            for getter in (
                inspector.get_check_constraints,
                inspector.get_unique_constraints,
                inspector.get_foreign_keys,
            )
            for item in getter(table)
        }
        assert {
            "uq_legal_versions_id_legal_act",
            "fk_legal_provisions_parent_act",
            "fk_legal_elements_version_act",
            "fk_legal_elements_provision_act_type",
            "ck_legal_elements_provision_presence",
        } <= names
        indexes = {
            item["name"]
            for table in ("legal_provisions", "legal_elements")
            for item in inspector.get_indexes(table)
        }
        assert "uq_legal_provisions_one_root_per_act" in indexes
        assert "uq_legal_elements_one_current_per_version_provision" in indexes
    finally:
        engine.dispose()


def test_upgrade_guard_rejects_existing_elements(disposable_database_url):
    _alembic(disposable_database_url, "upgrade", "004_frozen_parsing_model")
    engine = create_engine(disposable_database_url)
    with engine.begin() as connection:
        _, version_id, _ = _insert_chain_004(connection, "legacy-element")
        connection.execute(
            text(
                "INSERT INTO legal_elements "
                "(id,legal_version_id,element_type,document_order,raw_text,"
                "normalized_text,text_status,source_locator) VALUES "
                "(:id,:version,'DOCUMENT_ROOT',1,'Root','Root','CURRENT',"
                "CAST(:locator AS jsonb))"
            ),
            {"id": uuid.uuid4(), "version": version_id, "locator": '{"block_index":0}'},
        )
    engine.dispose()
    result = _alembic(disposable_database_url, "upgrade", "head", check=False)
    assert result.returncode != 0
    assert "Upgrade 005 recusado" in result.stderr
    assert (
        _revision_and_length(disposable_database_url)[0] == "004_frozen_parsing_model"
    )


def test_upgrade_allows_versions_without_elements(disposable_database_url):
    _alembic(disposable_database_url, "upgrade", "004_frozen_parsing_model")
    engine = create_engine(disposable_database_url)
    with engine.begin() as connection:
        _insert_chain_004(connection, "version-only")
    engine.dispose()
    _alembic(disposable_database_url, "upgrade", "head")
    assert _revision_and_length(disposable_database_url)[0] == (
        "005_normative_identity_occurrences"
    )


@pytest.mark.parametrize("derived", ["provision", "element"])
def test_downgrade_guard_rejects_normative_data(disposable_database_url, derived):
    _alembic(disposable_database_url, "upgrade", "head")
    engine = create_engine(disposable_database_url)
    with engine.begin() as connection:
        act_id, version_id, _ = _insert_chain_004(connection, f"down-{derived}")
        provision_id = uuid.uuid4()
        connection.execute(
            text(
                "INSERT INTO legal_provisions "
                "(id,legal_act_id,element_type,identity_key) "
                "VALUES (:id,:act,'DOCUMENT_ROOT','root')"
            ),
            {"id": provision_id, "act": act_id},
        )
        if derived == "element":
            connection.execute(
                text(
                    "INSERT INTO legal_elements "
                    "(id,legal_version_id,legal_act_id,legal_provision_id,element_type,"
                    "document_order,raw_text,normalized_text,text_status,"
                    "source_locator) "
                    "VALUES (:id,:version,:act,:provision,'DOCUMENT_ROOT',1,'Root',"
                    "'Root','CURRENT',CAST(:locator AS jsonb))"
                ),
                {
                    "id": uuid.uuid4(),
                    "version": version_id,
                    "act": act_id,
                    "provision": provision_id,
                    "locator": '{"block_index":0}',
                },
            )
    engine.dispose()
    result = _alembic(
        disposable_database_url,
        "downgrade",
        "004_frozen_parsing_model",
        check=False,
    )
    assert result.returncode != 0
    assert "Downgrade 005 recusado" in result.stderr
    assert _revision_and_length(disposable_database_url)[0] == (
        "005_normative_identity_occurrences"
    )
