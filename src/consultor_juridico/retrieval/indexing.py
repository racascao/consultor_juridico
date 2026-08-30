"""Persistência idempotente de chunks, FTS e embeddings."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from consultor_juridico.models import Chunk, ChunkLegalElement, Embedding, LegalVersion
from consultor_juridico.retrieval.chunking import CHUNK_STRATEGY, build_chunk_drafts
from consultor_juridico.retrieval.embeddings import OllamaEmbeddingProvider
from consultor_juridico.retrieval.types import IndexingOutcome, IndexingResult

PROVIDER_NAME = "ollama"
MODEL_VERSION = "latest"


def build_search_index(
    session: Session,
    provider: OllamaEmbeddingProvider,
    *,
    model_name: str,
    batch_size: int = 32,
) -> IndexingResult:
    """Cria o índice uma vez para o snapshot ativo; falhas causam rollback total."""
    active_versions = tuple(
        session.scalars(
            select(LegalVersion.id).where(LegalVersion.is_active_for_query.is_(True))
        )
    )
    if len(active_versions) != 2:
        raise RuntimeError(
            "Indexação exige as versões ativas conjuntas de CF/88 e ADCT."
        )
    existing = int(
        session.scalar(
            select(func.count())
            .select_from(Chunk)
            .where(
                Chunk.legal_version_id.in_(active_versions),
                Chunk.strategy_name == CHUNK_STRATEGY,
            )
        )
        or 0
    )
    if existing:
        embedding_count = int(
            session.scalar(
                select(func.count())
                .select_from(Embedding)
                .join(Chunk, Embedding.chunk_id == Chunk.id)
                .where(
                    Chunk.legal_version_id.in_(active_versions),
                    Chunk.strategy_name == CHUNK_STRATEGY,
                    Embedding.provider_name == PROVIDER_NAME,
                    Embedding.model_name == model_name,
                    Embedding.model_version == MODEL_VERSION,
                )
            )
            or 0
        )
        dimensions = int(
            session.scalar(
                select(Embedding.dimensions)
                .join(Chunk, Embedding.chunk_id == Chunk.id)
                .where(
                    Chunk.legal_version_id.in_(active_versions),
                    Embedding.provider_name == PROVIDER_NAME,
                    Embedding.model_name == model_name,
                    Embedding.model_version == MODEL_VERSION,
                )
                .limit(1)
            )
            or 0
        )
        if embedding_count != existing:
            raise RuntimeError(
                "Índice parcial detectado; reconstrução automática recusada."
            )
        return IndexingResult(
            IndexingOutcome.ALREADY_INDEXED,
            existing,
            embedding_count,
            dimensions,
            CHUNK_STRATEGY,
            PROVIDER_NAME,
            model_name,
            MODEL_VERSION,
        )

    drafts = build_chunk_drafts(session)
    if not drafts:
        raise RuntimeError("Nenhum elemento corrente elegível para chunking.")
    chunks: list[Chunk] = []
    try:
        for draft in drafts:
            chunk = Chunk(
                legal_version_id=draft.legal_version_id,
                chunk_text=draft.chunk_text,
                token_count=draft.token_count,
                strategy_name=CHUNK_STRATEGY,
            )
            session.add(chunk)
            session.flush()
            session.add(
                ChunkLegalElement(
                    chunk_id=chunk.id,
                    legal_element_id=draft.legal_element_id,
                    is_primary=True,
                )
            )
            chunks.append(chunk)
        session.flush()
        session.execute(
            update(Chunk)
            .where(Chunk.id.in_([chunk.id for chunk in chunks]))
            .values(tsv_content=func.to_tsvector("portuguese", Chunk.chunk_text))
        )

        dimensions = 0
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            vectors = provider.embed(
                [f"search_document: {chunk.chunk_text}" for chunk in batch]
            )
            dimensions = len(vectors[0])
            for chunk, vector in zip(batch, vectors, strict=True):
                session.add(
                    Embedding(
                        chunk_id=chunk.id,
                        provider_name=PROVIDER_NAME,
                        model_name=model_name,
                        model_version=MODEL_VERSION,
                        dimensions=dimensions,
                        vector=list(vector),
                    )
                )
            session.flush()
        session.commit()
    except Exception:
        session.rollback()
        raise
    return IndexingResult(
        IndexingOutcome.CREATED,
        len(chunks),
        len(chunks),
        dimensions,
        CHUNK_STRATEGY,
        PROVIDER_NAME,
        model_name,
        MODEL_VERSION,
    )
