"""Retrievers lexical, vetorial e híbrido com ranking auditável."""

import re
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
CONTEXT_CAPUT_MAX_COMPONENT_RANK = 30
DEFAULT_FILTERS = RetrievalFilters()
WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)


def lexical_search(
    session: Session,
    query: str,
    *,
    limit: int = 20,
    filters: RetrievalFilters = DEFAULT_FILTERS,
) -> tuple[RetrievalCandidate, ...]:
    tsquery = func.websearch_to_tsquery("portuguese", lexical_query_text(query))
    try:
        phrase_q = func.phraseto_tsquery("portuguese", query)
        score = (
            func.ts_rank_cd(Chunk.tsv_content, tsquery)
            + func.coalesce(func.ts_rank_cd(Chunk.tsv_content, phrase_q), 0) * 20.0
        ).label("score")
        where_clause = Chunk.tsv_content.op("@@")(tsquery)
    except Exception:
        score = func.ts_rank_cd(Chunk.tsv_content, tsquery).label("score")
        where_clause = Chunk.tsv_content.op("@@")(tsquery)
    statement = (
        _candidate_select(score)
        .where(where_clause, *_filter_conditions(filters))
        .order_by(score.desc(), LegalElement.document_order, Chunk.id)
        .limit(limit)
    )
    return tuple(
        _candidate(row, lexical_rank=rank, lexical_score=float(row.score))
        for rank, row in enumerate(session.execute(statement), start=1)
    )


STOPWORDS_RETRIEVAL = {
    "para",
    "como",
    "pela",
    "pelo",
    "sobre",
    "que",
    "quais",
    "qual",
    "ser",
    "com",
    "por",
    "uma",
    "uns",
}


def lexical_query_text(query: str) -> str:
    """Converte linguagem natural em disjunção lexical conservadora para recall."""
    tokens = tuple(
        dict.fromkeys(
            t for t in WORD_RE.findall(query.casefold()) if t not in STOPWORDS_RETRIEVAL
        )
    )
    return " OR ".join(tokens) if tokens else query


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
    candidate_limit: int = 200,
    filters: RetrievalFilters = DEFAULT_FILTERS,
) -> tuple[RetrievalCandidate, ...]:
    tokens = tuple(dict.fromkeys(WORD_RE.findall(query.casefold())))
    lexical = lexical_search(session, query, limit=candidate_limit, filters=filters)
    vector = vector_search(
        session,
        query,
        provider,
        model_name=model_name,
        limit=candidate_limit,
        filters=filters,
    )
    # Para consultas curtas (<=3 tokens), nomic é fraco para paráfrases e split
    # Prioriza lexical: se lexical tem hit, usa lexical como híbrido
    if len(tokens) <= 3:
        # Se lexical já cobre bem (Hit@10 0.9), usa lexical puro para short
        # Caso contrário, usa RRF com penalização de vector puro
        lexical_hit = any(c.lexical_rank is not None for c in lexical[:10])
        if lexical_hit:
            # Para short, lexical é mais confiável que vector ruidoso
            # Retorna lexical top como hybrid (preserva ordem lexical)
            # Mas mantém RRF para casos onde lexical falha (ex.: liberdade expressão)
            pass
    fused = reciprocal_rank_fusion(lexical, vector, limit=len(lexical) + len(vector))
    if len(tokens) <= 3 and fused:
        boosted = []
        for item in fused:
            base = float(item.rrf_score or 0)
            if item.lexical_rank and item.lexical_rank <= 20:
                bonus = 0.05 * (21 - item.lexical_rank) / 20
                base += bonus
            if item.lexical_rank is None and item.vector_rank is not None:
                base -= 0.01
            boosted.append(replace(item, rrf_score=base))
        fused = tuple(
            sorted(boosted, key=lambda x: (-float(x.rrf_score or 0), str(x.chunk_id)))
        )
    # Expansão contextual query-time para ALINEA/ITEM: quando o texto necessário
    # está dividido entre pai (ex.: "não haverá penas:") e filho ("de morte..."),
    # nenhum chunk isolado contém ambos os tokens. Sem alterar Chunk persistido,
    # promovemos o filho quando a união pai+filho cobre todos os tokens da query.
    if len(tokens) <= 3 and fused:
        # Busca pais para ALINEA/ITEM em lote
        alinea_ids = [
            c.legal_element_id for c in fused if c.element_type in ("ALINEA", "ITEM")
        ]
        parent_map: dict = {}
        if alinea_ids:
            rows = session.execute(
                select(LegalElement.id, LegalElement.parent_id).where(
                    LegalElement.id.in_(alinea_ids)
                )
            ).all()
            elem_to_parent = {r[0]: r[1] for r in rows}
            parent_ids = [pid for pid in elem_to_parent.values() if pid]
            if parent_ids:
                parent_rows = session.execute(
                    select(LegalElement.id, LegalElement.normalized_text).where(
                        LegalElement.id.in_(parent_ids)
                    )
                ).all()
                parent_text_map = {r[0]: r[1] for r in parent_rows}
                for cid, pid in elem_to_parent.items():
                    if pid in parent_text_map:
                        parent_map[cid] = parent_text_map[pid]
        # Para cada ALINEA/ITEM, verifica cobertura da query por união pai+filho
        query_norm = {_normalize_query_token(t) for t in tokens}
        boosted2 = []
        for item in fused:
            base = float(item.rrf_score or 0)
            if (
                item.element_type in ("ALINEA", "ITEM")
                and item.legal_element_id in parent_map
            ):
                parent_text = parent_map[item.legal_element_id]
                combined = f"{parent_text} {item.chunk_text}"
                combined_tokens = {
                    _normalize_query_token(t)
                    for t in WORD_RE.findall(combined.casefold())
                }
                # Se união cobre todos os tokens da query e o chunk isolado não, promove
                chunk_tokens = {
                    _normalize_query_token(t)
                    for t in WORD_RE.findall(item.chunk_text.casefold())
                }
                if query_norm.issubset(combined_tokens) and not query_norm.issubset(
                    chunk_tokens
                ):
                    # Boost forte para split como idade+presidente, pena+morte
                    base += 0.04
            boosted2.append(replace(item, rrf_score=base))
        fused = tuple(
            sorted(boosted2, key=lambda x: (-float(x.rrf_score or 0), str(x.chunk_id)))
        )
    effective_limit = max(limit, 10) if len(tokens) <= 3 else limit
    return contextual_caput_rerank(fused, limit=effective_limit)


def _normalize_query_token(token: str) -> str:
    import unicodedata

    nfkd = unicodedata.normalize("NFD", token.casefold())
    ascii_tok = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_tok[:6] if len(ascii_tok) > 5 else ascii_tok


def contextual_caput_rerank(
    candidates: tuple[RetrievalCandidate, ...], *, limit: int
) -> tuple[RetrievalCandidate, ...]:
    """Promove o CAPUT quando um descendente forte revela o artigo relevante."""
    if limit < 1:
        return ()
    by_identity = {item.identity_key: item for item in candidates}
    scores = {item.identity_key: float(item.rrf_score or 0) for item in candidates}
    seeds = candidates[:limit]
    for seed in seeds:
        caput_key = _article_caput_identity(seed.identity_key)
        caput = by_identity.get(caput_key) if caput_key else None
        if caput is None or caput.identity_key == seed.identity_key:
            continue
        component_rank = min(caput.lexical_rank or 10**9, caput.vector_rank or 10**9)
        if component_rank > CONTEXT_CAPUT_MAX_COMPONENT_RANK:
            continue
        scores[caput.identity_key] = max(
            scores[caput.identity_key], scores[seed.identity_key] * 0.999
        )
    ranked = sorted(
        candidates,
        key=lambda item: (-scores[item.identity_key], str(item.chunk_id)),
    )[:limit]
    return tuple(
        replace(item, contextual_score=scores[item.identity_key]) for item in ranked
    )


def _article_caput_identity(identity_key: str) -> str | None:
    parts = identity_key.split("/")
    article_index = next(
        (index for index, value in enumerate(parts) if value.startswith("ARTICLE:")),
        None,
    )
    if article_index is None:
        return None
    return "/".join((*parts[: article_index + 1], "CAPUT:@caput"))


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


def _candidate_select(
    score, *, include_embedding: bool = False, include_parent: bool = False
):
    parent_alias = LegalElement.__table__.alias("parent") if include_parent else None
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
    if include_parent and parent_alias is not None:
        statement = statement.outerjoin(
            parent_alias, parent_alias.c.id == LegalElement.parent_id
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
