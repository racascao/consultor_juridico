"""Bootstrap idempotente da baseline de corpus v0.2."""

from collections.abc import Generator
from dataclasses import dataclass

from consultor_juridico.application.corpus import (
    BuildCorpusUseCase,
    MaterializeCorpusUseCase,
    RematerializeCorpusFromSnapshotUseCase,
    SearchUnitBuilder,
)
from consultor_juridico.application.retrieval import BuildRetrievalIndex
from consultor_juridico.config import settings
from consultor_juridico.db.session import SessionLocal, get_database_url
from consultor_juridico.infrastructure.corpus import (
    PARSER_VERSION,
    ConstitutionCorpusParser,
    PlanaltoHttpSourceFetcher,
    SqlAlchemyCorpusRepository,
)
from consultor_juridico.infrastructure.retrieval import (
    OllamaEmbeddingProvider,
    PostgresRetrievalRepository,
)
from consultor_juridico.services import db_service


@dataclass(frozen=True, slots=True)
class BootstrapEvent:
    step: str
    state: str
    message: str


def corpus_repository() -> SqlAlchemyCorpusRepository:
    return SqlAlchemyCorpusRepository(SessionLocal)


def corpus_builder() -> BuildCorpusUseCase:
    return BuildCorpusUseCase(
        PlanaltoHttpSourceFetcher(),
        ConstitutionCorpusParser(),
        corpus_repository(),
        SearchUnitBuilder(),
    )


def corpus_rematerializer() -> RematerializeCorpusFromSnapshotUseCase:
    repository = corpus_repository()
    materializer = MaterializeCorpusUseCase(
        ConstitutionCorpusParser(), repository, SearchUnitBuilder()
    )
    return RematerializeCorpusFromSnapshotUseCase(repository, materializer)


def retrieval_index_builder() -> BuildRetrievalIndex:
    provider = OllamaEmbeddingProvider(
        settings.ollama_base_url,
        settings.ollama_embedding_model,
        settings.ollama_timeout,
        settings.embedding_dimensions,
    )
    return BuildRetrievalIndex(
        PostgresRetrievalRepository(SessionLocal), provider, progress=_index_progress
    )


def _index_progress(completed: int, total: int) -> None:
    if completed == total or completed % 256 == 0:
        print(f"index: Gerando embeddings {completed}/{total}...")


def run_bootstrap() -> Generator[BootstrapEvent]:
    """Prepara migrations, corpus e embeddings usando o PostgreSQL como estado."""
    status = db_service.check_db_status()
    if not status.get("connected"):
        yield BootstrapEvent(
            "db", "failed", f"PostgreSQL inacessível em {get_database_url()}."
        )
        return
    try:
        yield BootstrapEvent("db", "running", "Validando baseline v0.2...")
        db_service.run_migrations()
        yield BootstrapEvent("db", "success", "Baseline v0.2 pronta.")
    except Exception as exc:
        yield BootstrapEvent("db", "failed", f"Falha na migration: {exc}")
        return

    corpus_status = corpus_repository().status()
    if not corpus_status.ready or corpus_status.parser_version != PARSER_VERSION:
        try:
            yield BootstrapEvent(
                "corpus", "running", "Construindo corpus constitucional v0.2..."
            )
            result = corpus_builder().execute()
            yield BootstrapEvent(
                "corpus",
                "success",
                f"Corpus {result.outcome.value}: {result.provisions} provisions e "
                f"{result.search_units} SearchUnits.",
            )
        except Exception as exc:
            yield BootstrapEvent("corpus", "failed", f"Falha no corpus: {exc}")
            return
    try:
        yield BootstrapEvent("index", "running", "Validando embeddings do MVP2...")
        indexed = retrieval_index_builder().execute()
        yield BootstrapEvent(
            "index",
            "success",
            f"Índice pronto: {indexed.embedded} embeddings atualizadas.",
        )
    except Exception as exc:
        yield BootstrapEvent("index", "failed", f"Falha no índice: {exc}")
        return
    outcome = "ALREADY_READY" if indexed.embedded == 0 else "PREPARED"
    yield BootstrapEvent("all", "success", f"{outcome}: core v0.2 pronto.")
