"""Testes transacionais da materialização constitucional."""

import hashlib
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from consultor_juridico.db.session import get_database_url
from consultor_juridico.models import (
    LegalAct,
    LegalElement,
    LegalProvision,
    LegalVersion,
    ParsingRun,
    Source,
    SourceDocument,
)
from consultor_juridico.parsing.materialization import (
    ParsingOutcome,
    materialize_constitution,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC = Path(sys.executable).with_name("alembic")


@pytest.fixture
def database_url():
    base = make_url(get_database_url())
    name = f"cj_materialize_{uuid.uuid4().hex[:10]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
    url = base.set(database=name)
    environment = os.environ.copy()
    environment["DATABASE_URL"] = url.render_as_string(hide_password=False)
    environment["DEBUG"] = "false"
    subprocess.run(
        [str(ALEMBIC), "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        yield url
    finally:
        with admin.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=:name AND pid<>pg_backend_pid()"
                ),
                {"name": name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{name}"')
        admin.dispose()


def _document(session: Session) -> SourceDocument:
    html = (
        "<p>PREÂMBULO</p><p>Texto preambular.</p>"
        "<p>TÍTULO I</p><p>Dos princípios.</p>"
        "<p><strike>Art. 1º Redação histórica.</strike></p>"
        "<p>Art. 1º Redação corrente.</p><p>Art. 250. Fecho.</p>"
        "<p>Assinaturas</p>"
        "<p>ATO DAS DISPOSIÇÕES CONSTITUCIONAIS TRANSITÓRIAS</p>"
        "<p>Art. 1º ADCT.</p><p>Art. 138. Fecho.</p>"
    ).encode("windows-1252")
    source = Source(name="Planalto", base_url="https://www.planalto.gov.br")
    session.add(source)
    session.flush()
    document = SourceDocument(
        source_id=source.id,
        url_source="https://www.planalto.gov.br/constituicao.htm",
        raw_bytes=html,
        content_hash_sha256=hashlib.sha256(html).hexdigest(),
    )
    session.add(document)
    session.commit()
    return document


def _count(session: Session, model) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_materialization_is_atomic_auditable_and_idempotent(database_url):
    engine = create_engine(database_url)
    with Session(engine) as session:
        document = _document(session)
        first = materialize_constitution(session, document.id)
        assert first.outcome == ParsingOutcome.CREATED
        assert len(first.legal_version_ids) == 2
        assert first.provision_count > 0
        assert first.element_count > first.provision_count
        assert _count(session, ParsingRun) == 1
        assert _count(session, LegalAct) == 2
        assert _count(session, LegalVersion) == 2
        assert _count(session, LegalProvision) == first.provision_count
        assert _count(session, LegalElement) == first.element_count
        assert (
            session.scalar(
                select(func.count())
                .select_from(LegalVersion)
                .where(LegalVersion.is_active_for_query.is_(True))
            )
            == 2
        )

        second = materialize_constitution(session, document.id)
        assert second.outcome == ParsingOutcome.ALREADY_PARSED
        assert second.parsing_run_id == first.parsing_run_id
        assert _count(session, LegalVersion) == 2
        assert _count(session, LegalElement) == first.element_count
    engine.dispose()


def test_tx2_failure_rolls_back_all_derived_rows_and_retry_succeeds(database_url):
    engine = create_engine(database_url)
    with Session(engine) as session:
        document = _document(session)

        def fail(_session: Session) -> None:
            raise RuntimeError("falha injetada em TX2")

        with pytest.raises(RuntimeError, match="falha injetada"):
            materialize_constitution(session, document.id, before_complete=fail)
        run = session.scalar(select(ParsingRun))
        assert run is not None and run.status == "FAILED"
        assert _count(session, LegalAct) == 0
        assert _count(session, LegalVersion) == 0
        assert _count(session, LegalProvision) == 0
        assert _count(session, LegalElement) == 0

        retry = materialize_constitution(session, document.id)
        assert retry.outcome == ParsingOutcome.CREATED
        assert retry.parsing_run_id == run.id
        assert _count(session, LegalVersion) == 2
    engine.dispose()
