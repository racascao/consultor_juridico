"""Diagnóstico estruturado e verificação de prontidão do sistema."""

from dataclasses import dataclass

import httpx
from sqlalchemy import func, select

from consultor_juridico.config import settings
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.models import (
    Chunk,
    Embedding,
    LegalVersion,
    ParsingRun,
    SourceDocument,
)
from consultor_juridico.retrieval.chunking import CHUNK_STRATEGY
from consultor_juridico.retrieval.indexing import MODEL_VERSION, PROVIDER_NAME
from consultor_juridico.services import db_service


@dataclass(frozen=True, slots=True)
class SystemReadiness:
    database_connected: bool
    schema_ready: bool
    ollama_connected: bool
    llm_model_ready: bool
    embedding_model_ready: bool
    source_ready: bool
    parsing_ready: bool
    index_ready: bool
    semantic_judge_model_ready: bool = True

    @property
    def is_ready(self) -> bool:
        return (
            self.database_connected
            and self.schema_ready
            and self.ollama_connected
            and self.embedding_model_ready
            and self.semantic_judge_model_ready
            and self.source_ready
            and self.parsing_ready
            and self.index_ready
        )


def check_readiness() -> SystemReadiness:
    """Verifica o estado atual do sistema sem causar efeitos colaterais."""
    # 1. Banco de Dados e Migrations
    db_status = db_service.check_db_status()
    db_connected = db_status.get("connected", False)
    schema_ready = False

    required_tables = {
        "alembic_version",
        "source_documents",
        "legal_acts",
        "legal_versions",
        "legal_provisions",
        "legal_elements",
        "chunks",
        "embeddings",
    }

    if db_connected:
        tables = db_status.get("tables", [])
        if required_tables.issubset(set(tables)):
            schema_ready = (
                db_status.get("alembic_version") == db_service.get_alembic_head()
            )

    # 2. Ollama e Modelos
    ollama_connected = False
    llm_model_ready = False
    embedding_model_ready = False
    ollama_models = []

    try:
        url = settings.ollama_base_url.rstrip("/")
        response = httpx.get(f"{url}/api/tags", timeout=2.0)
        if response.status_code == 200:
            ollama_connected = True
            ollama_models = [m["name"] for m in response.json().get("models", [])]
    except Exception:
        pass

    if ollama_connected:
        # Verifica se o modelo do LLM está instalado (com ou sem a tag :latest)
        llm_name = settings.ollama_model
        llm_model_ready = any(
            m == llm_name or m.split(":")[0] == llm_name.split(":")[0]
            for m in ollama_models
        )
        # Verifica se o modelo de embedding está instalado
        emb_name = settings.embedding_model
        embedding_model_ready = any(
            m == emb_name or m.split(":")[0] == emb_name.split(":")[0]
            for m in ollama_models
        )
        # Verifica juiz semântico quando configurado de forma independente
        judge_name = settings.semantic_judge_model
        if judge_name and judge_name != llm_name:
            semantic_judge_model_ready = any(
                m == judge_name or m.split(":")[0] == judge_name.split(":")[0]
                for m in ollama_models
            )
        else:
            semantic_judge_model_ready = llm_model_ready
    else:
        semantic_judge_model_ready = False

    # 3. Dados (Ingestão, Parsing, Indexação)
    source_ready = False
    parsing_ready = False
    index_ready = False

    if db_connected and schema_ready:
        try:
            with SessionLocal() as session:
                # Ingestão: existe captura não vazia com hash SHA-256 completo.
                doc_count = int(
                    session.scalar(
                        select(func.count())
                        .select_from(SourceDocument)
                        .where(
                            func.octet_length(SourceDocument.raw_bytes) > 0,
                            func.length(SourceDocument.content_hash_sha256) == 64,
                        )
                    )
                    or 0
                )
                source_ready = doc_count > 0

                # Parsing: as duas versões ativas pertencem ao mesmo run
                # concluído e à mesma captura processada.
                parsing_completed = session.scalar(
                    select(ParsingRun)
                    .where(ParsingRun.status == "COMPLETED")
                    .order_by(ParsingRun.finished_at.desc())
                )
                active_versions = []
                if parsing_completed is not None:
                    active_versions = session.scalars(
                        select(LegalVersion).where(
                            LegalVersion.is_active_for_query.is_(True),
                            LegalVersion.parsing_run_id == parsing_completed.id,
                            LegalVersion.source_document_id
                            == parsing_completed.source_document_id,
                        )
                    ).all()
                parsing_ready = len(active_versions) == 2

                # Indexação: chunks existem para as versões ativas e possuem
                # embeddings correspondentes
                if parsing_ready:
                    active_version_ids = [v.id for v in active_versions]
                    chunks_count = int(
                        session.scalar(
                            select(func.count())
                            .select_from(Chunk)
                            .where(Chunk.legal_version_id.in_(active_version_ids))
                            .where(Chunk.strategy_name == CHUNK_STRATEGY)
                        )
                        or 0
                    )
                    indexed_versions_count = int(
                        session.scalar(
                            select(
                                func.count(func.distinct(Chunk.legal_version_id))
                            ).where(
                                Chunk.legal_version_id.in_(active_version_ids),
                                Chunk.strategy_name == CHUNK_STRATEGY,
                            )
                        )
                        or 0
                    )
                    embeddings_count = int(
                        session.scalar(
                            select(func.count())
                            .select_from(Embedding)
                            .join(Chunk, Embedding.chunk_id == Chunk.id)
                            .where(
                                Chunk.legal_version_id.in_(active_version_ids),
                                Chunk.strategy_name == CHUNK_STRATEGY,
                                Embedding.provider_name == PROVIDER_NAME,
                                Embedding.model_name == settings.embedding_model,
                                Embedding.model_version == MODEL_VERSION,
                                Embedding.vector.is_not(None),
                            )
                        )
                        or 0
                    )
                    index_ready = (
                        chunks_count > 0
                        and indexed_versions_count == 2
                        and embeddings_count == chunks_count
                    )
        except Exception:
            pass

    return SystemReadiness(
        database_connected=db_connected,
        schema_ready=schema_ready,
        ollama_connected=ollama_connected,
        llm_model_ready=llm_model_ready,
        embedding_model_ready=embedding_model_ready,
        source_ready=source_ready,
        parsing_ready=parsing_ready,
        index_ready=index_ready,
        semantic_judge_model_ready=semantic_judge_model_ready,
    )
