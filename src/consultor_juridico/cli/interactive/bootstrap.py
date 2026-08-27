"""Orquestração de bootstrap automático e idempotente do sistema."""

from collections.abc import Generator

from sqlalchemy import select

from consultor_juridico.cli.interactive.readiness import check_readiness
from consultor_juridico.config import settings
from consultor_juridico.db.session import SessionLocal, get_database_url
from consultor_juridico.ingestion import run_planalto_ingestion
from consultor_juridico.models import SourceDocument
from consultor_juridico.parsing import materialize_constitution
from consultor_juridico.retrieval import OllamaEmbeddingProvider, build_search_index
from consultor_juridico.services import db_service


class BootstrapEvent:
    """Representa um evento de progresso durante o bootstrap."""

    def __init__(self, step: str, state: str, message: str):
        self.step = step  # "db", "ollama", "models", "ingest", "parse", "index"
        self.state = state  # "running", "success", "failed"
        self.message = message


def _embedding_provider() -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(
        settings.ollama_base_url,
        settings.embedding_model,
        settings.embedding_timeout,
    )


def run_bootstrap() -> Generator[BootstrapEvent]:
    """Orquestra a preparação idempotente da base jurídica emitindo eventos."""
    # 1. Verifica estado inicial
    readiness = check_readiness()

    if readiness.is_ready:
        yield BootstrapEvent(
            "all", "success", "ALREADY_READY: o ambiente já está preparado."
        )
        return

    # 2. Banco de Dados Offline
    if not readiness.database_connected:
        yield BootstrapEvent(
            "db",
            "failed",
            "Banco de dados PostgreSQL inacessível.\n"
            f"Verifique se o container do banco está rodando em: {get_database_url()}",
        )
        return

    # 3. Migrations do Banco
    if not readiness.schema_ready:
        yield BootstrapEvent(
            "db", "running", "Aplicando migrations no banco de dados..."
        )
        try:
            db_service.run_migrations()
            yield BootstrapEvent(
                "db", "success", "Banco de dados atualizado com sucesso."
            )
        except Exception as exc:
            yield BootstrapEvent("db", "failed", f"Falha ao executar migrations: {exc}")
            return

    # 4. O Compose provisiona os modelos antes de declarar o Ollama saudável.
    if not readiness.ollama_connected:
        yield BootstrapEvent(
            "ollama",
            "failed",
            "Serviço Ollama offline.\n"
            f"Verifique se o Ollama está ativo em: {settings.ollama_base_url}",
        )
        return

    missing_models = []
    if not readiness.embedding_model_ready:
        missing_models.append(settings.embedding_model)
    if not readiness.semantic_judge_model_ready:
        missing_models.append(settings.semantic_judge_model or settings.ollama_model)
    if missing_models:
        yield BootstrapEvent(
            "models",
            "failed",
            "Modelos obrigatórios ausentes no Ollama: "
            f"{', '.join(dict.fromkeys(missing_models))}. "
            "Consulte os logs do serviço Ollama.",
        )
        return

    # 5. Ingestão
    if not readiness.source_ready:
        yield BootstrapEvent(
            "ingest",
            "running",
            "Iniciando captura oficial da CF/88 e ADCT do Planalto...",
        )
        try:
            result = run_planalto_ingestion()
            yield BootstrapEvent(
                "ingest",
                "success",
                f"Ingestão concluída. ID: {result.document_id} | "
                f"Hash: {result.sha256[:12]}",
            )
        except Exception as exc:
            yield BootstrapEvent("ingest", "failed", f"Falha na captura oficial: {exc}")
            return

    # 6. Parsing e Materialização
    # Recalcula a prontidão dos dados porque a ingestão pode ter acabado de ocorrer
    with SessionLocal() as session:
        latest_doc = session.scalar(
            select(SourceDocument).order_by(SourceDocument.fetched_at.desc())
        )
        if latest_doc is None:
            yield BootstrapEvent(
                "parse", "failed", "Nenhum documento de fonte disponível para parsing."
            )
            return
        doc_id = latest_doc.id

    # O parsing em si precisa verificar a readiness novamente
    readiness = check_readiness()
    if not readiness.parsing_ready:
        yield BootstrapEvent(
            "parse", "running", "Processando e estruturando CF/88 e ADCT..."
        )
        try:
            with SessionLocal() as session:
                result = materialize_constitution(session, doc_id)
            yield BootstrapEvent(
                "parse",
                "success",
                f"Parsing concluído. {result.provision_count} dispositivos criados.",
            )
        except Exception as exc:
            yield BootstrapEvent(
                "parse", "failed", f"Falha no parsing/materialização: {exc}"
            )
            return

    # 7. Indexação (Chunks e Embeddings)
    readiness = check_readiness()
    if not readiness.index_ready:
        yield BootstrapEvent(
            "index", "running", "Gerando chunks e embeddings locais do índice..."
        )
        try:
            with SessionLocal() as session:
                result = build_search_index(
                    session,
                    _embedding_provider(),
                    model_name=settings.embedding_model,
                    batch_size=settings.embedding_batch_size,
                )
            yield BootstrapEvent(
                "index",
                "success",
                f"Índice gerado. {result.chunks} chunks e "
                f"{result.embeddings} embeddings criados.",
            )
        except Exception as exc:
            yield BootstrapEvent(
                "index", "failed", f"Falha na geração do índice: {exc}"
            )
            return

    yield BootstrapEvent(
        "all", "success", "PREPARED: sistema preparado para consultas."
    )
