"""CLI da fundação documental do MVP2."""

from typing import Annotated

import httpx
import typer
from rich.console import Console

from consultor_juridico import __version__
from consultor_juridico.application.corpus.audit import (
    CorpusAuditor,
    list_versions,
    trace_unit,
)
from consultor_juridico.application.corpus.catalog import LEI_9784_ACT, LEI_9784_SOURCE
from consultor_juridico.application.corpus.parser import PlanaltoLeiParser
from consultor_juridico.application.corpus.projection import ProvisionTextProjection
from consultor_juridico.application.corpus.services import (
    AcquireOfficialSource,
    MaterializeFromSnapshot,
)
from consultor_juridico.config import settings
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.infrastructure.corpus.http import HttpxSourceAcquirer
from consultor_juridico.infrastructure.corpus.materializer import (
    SqlAlchemyCorpusMaterializer,
)
from consultor_juridico.infrastructure.corpus.repositories import (
    SqlAlchemySnapshotRepository,
)
from consultor_juridico.services import db_service

app = typer.Typer(
    name="consultor-juridico",
    help="Fundação documental auditável do Consultor Jurídico MVP2.",
    add_completion=False,
)
db_app = typer.Typer(help="Banco de dados e migrations.")
corpus_app = typer.Typer(help="Aquisição, materialização e auditoria do corpus.")
app.add_typer(db_app, name="db")
app.add_typer(corpus_app, name="corpus")
console = Console()


@app.command()
def version() -> None:
    """Exibe a versão do pacote."""
    console.print(f"Consultor Jurídico {__version__}")


@db_app.command("migrate")
def db_migrate() -> None:
    """Aplica migrations pendentes."""
    db_service.run_migrations()
    console.print("[green]Migrations aplicadas.[/green]")


@db_app.command("status")
def db_status() -> None:
    """Exibe conexão, revision e tabelas."""
    status = db_service.check_db_status()
    if not status.get("connected"):
        console.print(f"[red]Banco indisponível: {status.get('error')}[/red]")
        raise typer.Exit(1)
    console.print(f"database_url={status['database_url']}")
    console.print(f"alembic={status['alembic_version'] or 'NONE'}")
    console.print(f"tables={','.join(status['tables'])}")


@corpus_app.command("adquirir")
def corpus_acquire() -> None:
    """Adquire ou reutiliza captura oficial da Lei nº 9.784/1999."""
    timeout = httpx.Timeout(
        connect=settings.ingestion_connect_timeout,
        read=settings.ingestion_read_timeout,
        write=settings.ingestion_write_timeout,
        pool=settings.ingestion_pool_timeout,
    )
    with httpx.Client(timeout=timeout) as client, SessionLocal() as session:
        use_case = AcquireOfficialSource(
            HttpxSourceAcquirer(client, user_agent=settings.planalto_user_agent),
            SqlAlchemySnapshotRepository(session),
        )
        with session.begin():
            result = use_case.execute(LEI_9784_SOURCE)
    snapshot = result.snapshot
    console.print(f"source={LEI_9784_SOURCE.name}")
    console.print(f"url={LEI_9784_SOURCE.official_url}")
    console.print(f"http_status={result.status_code}")
    console.print(f"snapshot_id={snapshot.id}")
    console.print(f"sha256={snapshot.sha256}")
    console.print(f"byte_length={snapshot.byte_length}")
    console.print(f"etag={snapshot.etag}")
    console.print(f"last_modified={snapshot.last_modified}")
    console.print(f"acquired_at={snapshot.acquired_at.isoformat()}")
    console.print(f"outcome={'CREATED' if result.created else 'REUSED'}")


def _materialize(snapshot_sha: str):
    with SessionLocal() as read_session:
        use_case = MaterializeFromSnapshot(
            SqlAlchemySnapshotRepository(read_session),
            SqlAlchemyCorpusMaterializer(SessionLocal),
            PlanaltoLeiParser(),
            ProvisionTextProjection(),
        )
        return use_case.execute(
            snapshot_sha=snapshot_sha,
            source=LEI_9784_SOURCE,
            act=LEI_9784_ACT,
        )


def _show_materialization(result) -> None:
    console.print(f"legal_act={LEI_9784_ACT.act_code}")
    console.print(f"act_version_id={result.act_version_id}")
    console.print(f"version_hash={result.version_hash}")
    console.print("parser=planalto-lei-structural/1")
    console.print("projection=provision-text/1")
    console.print(f"provision_count={result.provision_count}")
    console.print(f"search_unit_count={result.search_unit_count}")
    console.print(f"outcome={'CREATED' if result.created else 'REUSED'}")


@corpus_app.command("materializar")
def corpus_materialize(
    snapshot_sha: Annotated[str, typer.Option("--snapshot-sha")],
) -> None:
    """Materializa explicitamente um snapshot persistido, sem HTTP."""
    _show_materialization(_materialize(snapshot_sha))


@corpus_app.command("reprojetar")
def corpus_reproject(
    snapshot_sha: Annotated[str, typer.Option("--snapshot-sha")],
) -> None:
    """Reexecuta parser/projeção correntes somente a partir do snapshot local."""
    _show_materialization(_materialize(snapshot_sha))


@corpus_app.command("versoes")
def corpus_versions() -> None:
    """Lista versões explícitas do corpus, sem conceito de versão ativa."""
    with SessionLocal() as session:
        rows = list_versions(session)
    for row in rows:
        console.print(" | ".join(f"{key}={value}" for key, value in row.items()))


@corpus_app.command("auditar")
def corpus_audit(
    version_hash: Annotated[str, typer.Option("--version-hash")],
) -> None:
    """Audita integridade, conteúdo, projeção e proveniência."""
    with SessionLocal() as session:
        report = CorpusAuditor(
            session, PlanaltoLeiParser(), ProvisionTextProjection()
        ).audit(version_hash, encoding=LEI_9784_SOURCE.encoding)
    for name, passed in report.checks.items():
        console.print(f"{name}={'PASS' if passed else 'FAIL'}")
    console.print(f"provisions={report.provision_count}")
    console.print(f"search_units={report.search_unit_count}")
    console.print(f"AUDIT={'PASS' if report.passed else 'FAIL'}")
    if not report.passed:
        raise typer.Exit(1)


@corpus_app.command("rastrear")
def corpus_trace(
    version_hash: Annotated[str, typer.Option("--version-hash")],
    unit_key: Annotated[str, typer.Option("--unit-key")],
) -> None:
    """Mostra a cadeia de uma SearchUnit até a fonte oficial."""
    with SessionLocal() as session:
        result = trace_unit(session, version_hash, unit_key)
    for key, value in result.items():
        console.print(f"{key}={value}")


if __name__ == "__main__":
    app()
