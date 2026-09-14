"""Composição operacional do bootstrap do MVP2."""

import httpx

from consultor_juridico.application.corpus.catalog import LEI_9784_ACT, LEI_9784_SOURCE
from consultor_juridico.application.corpus.parser import PlanaltoLeiParser
from consultor_juridico.application.corpus.projection import ProvisionTextProjection
from consultor_juridico.application.corpus.services import (
    AcquireOfficialSource,
    MaterializeFromSnapshot,
)
from consultor_juridico.cli.interactive.readiness import check_readiness
from consultor_juridico.config import settings
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.evaluation.selected_answerer import SELECTED_MODEL
from consultor_juridico.infrastructure.corpus.http import HttpxSourceAcquirer
from consultor_juridico.infrastructure.corpus.materializer import (
    SqlAlchemyCorpusMaterializer,
)
from consultor_juridico.infrastructure.corpus.repositories import (
    SqlAlchemySnapshotRepository,
)
from consultor_juridico.services import db_service
from consultor_juridico.services.bootstrap import BootstrapOrchestrator


def _prepare_corpus() -> None:
    timeout = httpx.Timeout(
        connect=settings.ingestion_connect_timeout,
        read=settings.ingestion_read_timeout,
        write=settings.ingestion_write_timeout,
        pool=settings.ingestion_pool_timeout,
    )
    with httpx.Client(timeout=timeout) as client, SessionLocal() as session:
        repository = SqlAlchemySnapshotRepository(session)
        snapshot = repository.latest_for_source(LEI_9784_SOURCE)
        if snapshot is None:
            result = AcquireOfficialSource(
                HttpxSourceAcquirer(client, user_agent=settings.planalto_user_agent),
                repository,
            ).execute(LEI_9784_SOURCE)
            session.commit()
            snapshot = result.snapshot

    with SessionLocal() as read_session:
        MaterializeFromSnapshot(
            SqlAlchemySnapshotRepository(read_session),
            SqlAlchemyCorpusMaterializer(SessionLocal),
            PlanaltoLeiParser(),
            ProvisionTextProjection(),
        ).execute(
            snapshot_sha=snapshot.sha256,
            source=LEI_9784_SOURCE,
            act=LEI_9784_ACT,
        )


def _prepare_model() -> None:
    with httpx.stream(
        "POST",
        f"{settings.ollama_base_url.rstrip('/')}/api/pull",
        json={"name": SELECTED_MODEL, "stream": True},
        timeout=1800.0,
    ) as response:
        response.raise_for_status()
        for _ in response.iter_lines():
            pass


def compose_bootstrap() -> BootstrapOrchestrator:
    return BootstrapOrchestrator(
        inspect=check_readiness,
        migrate=db_service.run_migrations,
        prepare_corpus=_prepare_corpus,
        prepare_model=_prepare_model,
    )
