"""Retrievers lexical, vetorial e híbrido com ranking auditável."""

from dataclasses import replace

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from consultor_juridico.models import (
    Chunk,
    ChunkLegalElement,
    Embedding,
    LegalAct,
    LegalElement,
    LegalProvision,
    LegalVersion,
)
from consultor_juridico.retrieval.embeddings import OllamaEmbeddingProvider
from consultor_juridico.retrieval.indexing import MODEL_VERSION, PROVIDER_NAME
from consultor_juridico.retrieval.types import RetrievalCandidate, RetrievalFilters

RRF_K = 60
DEFAULT_FILTERS = RetrievalFilters()


def lexical_search(
    session: Session,
    query: str,
    *,
    limit: int = 20,
    filters: RetrievalFilters = DEFAULT_FILTERS,
) -> tuple[RetrievalCandidate, ...]:
    tsquery = func.websearch_to_tsquery("portuguese", query)
    score = func.ts_rank_cd(Chunk.tsv_content, tsquery).label("score")
    statement = (
        _candidate_select(score)
        .where(Chunk.tsv_content.op("@@")(tsquery), *_filter_conditions(filters))
        .order_by(score.desc(), LegalElement.document_order, Chunk.id)
        .limit(limit)
    )
    return tuple(
        _candidate(row, lexical_rank=rank, lexical_score=float(row.score))
        for rank, row in enumerate(session.execute(statement), start=1)
    )


def vector_search(
    session: Session,
    query: str,
    provider: OllamaEmbeddingProvider,
    *,
    model_name: str,
    limit: int = 20,
    filters: RetrievalFilters = DEFAULT_FILTERS,
) -> tuple[RetrievalCandidate, ...]:
    query_vector = list(provider.embed([f"search_query: {query}"])[0])
    distance = Embedding.vector.cosine_distance(query_vector).label("distance")
    statement = (
        _candidate_select(distance, include_embedding=True)
        .where(
            Embedding.provider_name == PROVIDER_NAME,
            Embedding.model_name == model_name,
            Embedding.model_version == MODEL_VERSION,
            Embedding.dimensions == len(query_vector),
            Embedding.vector.is_not(None),
            *_filter_conditions(filters),
        )
        .order_by(distance, LegalElement.document_order, Chunk.id)
        .limit(limit)
    )
    return tuple(
        _candidate(row, vector_rank=rank, vector_score=1.0 - float(row.distance))
        for rank, row in enumerate(session.execute(statement), start=1)
    )


def hybrid_search(
    session: Session,
    query: str,
    provider: OllamaEmbeddingProvider,
    *,
    model_name: str,
    limit: int = 10,
    candidate_limit: int = 50,
    filters: RetrievalFilters = DEFAULT_FILTERS,
) -> tuple[RetrievalCandidate, ...]:
    lexical = lexical_search(session, query, limit=candidate_limit, filters=filters)
    vector = vector_search(
        session,
        query,
        provider,
        model_name=model_name,
        limit=candidate_limit,
        filters=filters,
    )
    return reciprocal_rank_fusion(lexical, vector, limit=limit)


def reciprocal_rank_fusion(
    lexical: tuple[RetrievalCandidate, ...],
    vector: tuple[RetrievalCandidate, ...],
    *,
    limit: int,
    rrf_k: int = RRF_K,
) -> tuple[RetrievalCandidate, ...]:
    candidates = {item.chunk_id: item for item in lexical}
    for item in vector:
        previous = candidates.get(item.chunk_id)
        candidates[item.chunk_id] = (
            item
            if previous is None
            else replace(
                previous,
                vector_rank=item.vector_rank,
                vector_score=item.vector_score,
            )
        )
    fused = []
    for item in candidates.values():
        score = sum(
            1.0 / (rrf_k + rank)
            for rank in (item.lexical_rank, item.vector_rank)
            if rank is not None
        )
        fused.append(replace(item, rrf_score=score))
    return tuple(
        sorted(
            fused,
            key=lambda item: (-float(item.rrf_score or 0), str(item.chunk_id)),
        )[:limit]
    )


def _candidate_select(score, *, include_embedding: bool = False):
    statement = (
        select(
            Chunk.id.label("chunk_id"),
            LegalElement.id.label("legal_element_id"),
            LegalProvision.id.label("legal_provision_id"),
            LegalAct.short_name.label("legal_act"),
            LegalElement.element_type,
            LegalElement.number_label,
            LegalProvision.identity_key,
            Chunk.chunk_text,
            score,
        )
        .join(ChunkLegalElement, ChunkLegalElement.chunk_id == Chunk.id)
        .join(LegalElement, LegalElement.id == ChunkLegalElement.legal_element_id)
        .join(LegalProvision, LegalProvision.id == LegalElement.legal_provision_id)
        .join(LegalVersion, LegalVersion.id == Chunk.legal_version_id)
        .join(LegalAct, LegalAct.id == LegalElement.legal_act_id)
        .where(
            ChunkLegalElement.is_primary.is_(True),
            LegalVersion.is_active_for_query.is_(True),
        )
    )
    if include_embedding:
        statement = statement.join(Embedding, Embedding.chunk_id == Chunk.id)
    return statement


def _filter_conditions(filters: RetrievalFilters):
    conditions = [
        LegalElement.text_status == filters.text_status,
        LegalElement.content_role == filters.content_role,
    ]
    if filters.act:
        conditions.append(LegalAct.short_name == filters.act)
    if filters.element_types:
        conditions.append(LegalElement.element_type.in_(filters.element_types))
    return conditions


def _candidate(row, **scores) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=row.chunk_id,
        legal_element_id=row.legal_element_id,
        legal_provision_id=row.legal_provision_id,
        legal_act=row.legal_act,
        element_type=row.element_type,
        number_label=row.number_label,
        identity_key=row.identity_key,
        chunk_text=row.chunk_text,
        **scores,
    )
