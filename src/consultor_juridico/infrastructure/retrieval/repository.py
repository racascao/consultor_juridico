"""Consultas PostgreSQL FTS/pgvector e persistência idempotente."""

from collections.abc import Callable, Generator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from consultor_juridico.application.retrieval.types import (
    EmbeddingDocument,
    RankedSearchUnit,
)
from consultor_juridico.domain import CitationItem
from consultor_juridico.infrastructure.corpus.models import (
    ActVersionRecord,
    LegalActRecord,
    ProvisionRecord,
    SearchUnitEmbeddingRecord,
    SearchUnitProvisionRecord,
    SearchUnitRecord,
    SourceRecord,
    SourceSnapshotRecord,
)

INDEX_BUILD_LOCK_ID = 0x494E444558


class PostgresRetrievalRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    @contextmanager
    def index_build_lock(self) -> Generator[None]:
        """Serializa indexadores e libera o lock mesmo quando o provider falha."""
        with self._session_factory() as session, session.begin():
            session.execute(select(func.pg_advisory_xact_lock(INDEX_BUILD_LOCK_ID)))
            yield

    def lexical(self, query: str, limit: int) -> tuple[RankedSearchUnit, ...]:
        with self._session_factory() as session:
            tsquery = func.websearch_to_tsquery("portuguese", query)
            rank = func.ts_rank_cd(SearchUnitRecord.search_vector, tsquery)
            ids = tuple(
                session.scalars(
                    select(SearchUnitRecord.id)
                    .join(
                        ActVersionRecord,
                        SearchUnitRecord.act_version_id == ActVersionRecord.id,
                    )
                    .where(
                        ActVersionRecord.active.is_(True),
                        SearchUnitRecord.search_vector.op("@@")(tsquery),
                    )
                    .order_by(rank.desc(), SearchUnitRecord.document_order)
                    .limit(limit)
                ).all()
            )
            return self._hydrate(session, ids)

    def vector(
        self, query_vector: tuple[float, ...], model: str, limit: int
    ) -> tuple[RankedSearchUnit, ...]:
        with self._session_factory() as session:
            distance = SearchUnitEmbeddingRecord.vector.cosine_distance(
                list(query_vector)
            )
            ids = tuple(
                session.scalars(
                    select(SearchUnitRecord.id)
                    .join(
                        SearchUnitEmbeddingRecord,
                        SearchUnitEmbeddingRecord.search_unit_id == SearchUnitRecord.id,
                    )
                    .join(
                        ActVersionRecord,
                        SearchUnitRecord.act_version_id == ActVersionRecord.id,
                    )
                    .where(
                        ActVersionRecord.active.is_(True),
                        SearchUnitEmbeddingRecord.model == model,
                    )
                    .order_by(distance, SearchUnitRecord.document_order)
                    .limit(limit)
                ).all()
            )
            return self._hydrate(session, ids)

    def embedding_documents(
        self, provider: str, model: str
    ) -> tuple[EmbeddingDocument, ...]:
        with self._session_factory() as session:
            existing = (
                select(
                    SearchUnitEmbeddingRecord.search_unit_id,
                    SearchUnitEmbeddingRecord.content_hash,
                )
                .where(
                    SearchUnitEmbeddingRecord.provider == provider,
                    SearchUnitEmbeddingRecord.model == model,
                )
                .subquery()
            )
            rows = session.execute(
                select(
                    SearchUnitRecord.id,
                    SearchUnitRecord.search_text,
                    SearchUnitRecord.content_hash,
                )
                .join(
                    ActVersionRecord,
                    SearchUnitRecord.act_version_id == ActVersionRecord.id,
                )
                .outerjoin(existing, existing.c.search_unit_id == SearchUnitRecord.id)
                .where(
                    ActVersionRecord.active.is_(True),
                    (existing.c.content_hash.is_(None))
                    | (existing.c.content_hash != SearchUnitRecord.content_hash),
                )
                .order_by(
                    ActVersionRecord.legal_act_id, SearchUnitRecord.document_order
                )
            ).all()
            return tuple(
                EmbeddingDocument(str(row.id), row.search_text, row.content_hash)
                for row in rows
            )

    def save_embeddings(
        self,
        documents: tuple[EmbeddingDocument, ...],
        vectors: tuple[tuple[float, ...], ...],
        provider: str,
        model: str,
        dimensions: int,
    ) -> None:
        if len(documents) != len(vectors):
            raise ValueError("Documentos e vetores devem possuir o mesmo tamanho.")
        with self._session_factory() as session, session.begin():
            for document, vector in zip(documents, vectors, strict=True):
                statement = insert(SearchUnitEmbeddingRecord).values(
                    search_unit_id=UUID(document.search_unit_id),
                    provider=provider,
                    model=model,
                    dimensions=dimensions,
                    content_hash=document.content_hash,
                    vector=list(vector),
                )
                statement = statement.on_conflict_do_update(
                    constraint="uq_search_unit_embeddings_unit_provider_model",
                    set_={
                        "dimensions": dimensions,
                        "content_hash": document.content_hash,
                        "vector": list(vector),
                        "created_at": func.now(),
                    },
                )
                session.execute(statement)

    @staticmethod
    def _hydrate(
        session: Session, ids: tuple[UUID, ...]
    ) -> tuple[RankedSearchUnit, ...]:
        if not ids:
            return ()
        rows = session.execute(
            select(
                SearchUnitRecord,
                LegalActRecord.code,
                SourceSnapshotRecord.sha256,
                SourceRecord.official_url,
            )
            .join(
                ActVersionRecord,
                SearchUnitRecord.act_version_id == ActVersionRecord.id,
            )
            .join(
                LegalActRecord,
                ActVersionRecord.legal_act_id == LegalActRecord.id,
            )
            .join(
                SourceSnapshotRecord,
                ActVersionRecord.source_snapshot_id == SourceSnapshotRecord.id,
            )
            .join(SourceRecord, SourceSnapshotRecord.source_id == SourceRecord.id)
            .where(SearchUnitRecord.id.in_(ids))
        ).all()
        by_id = {row[0].id: row for row in rows}
        citations = PostgresRetrievalRepository._citations(session, ids)
        return tuple(
            PostgresRetrievalRepository._ranked(by_id[item_id], citations)
            for item_id in ids
        )

    @staticmethod
    def _citations(
        session: Session, ids: tuple[UUID, ...]
    ) -> dict[UUID, tuple[CitationItem, ...]]:
        rows = session.execute(
            select(SearchUnitProvisionRecord.search_unit_id, ProvisionRecord)
            .join(
                ProvisionRecord,
                SearchUnitProvisionRecord.provision_id == ProvisionRecord.id,
            )
            .where(SearchUnitProvisionRecord.search_unit_id.in_(ids))
            .order_by(
                SearchUnitProvisionRecord.search_unit_id,
                ProvisionRecord.document_order,
            )
        ).all()
        grouped: dict[UUID, list[CitationItem]] = {item_id: [] for item_id in ids}
        for unit_id, provision in rows:
            grouped[unit_id].append(
                CitationItem(
                    provision.stable_key,
                    provision.label,
                    provision.citation_text,
                    provision.source_locator,
                )
            )
        return {key: tuple(value) for key, value in grouped.items()}

    @staticmethod
    def _ranked(row, citations) -> RankedSearchUnit:
        unit, act_code, snapshot_sha, source_url = row
        reference = unit.stable_reference
        article = _article_reference(reference)
        return RankedSearchUnit(
            search_unit_id=str(unit.id),
            search_unit_type=unit.unit_type,
            legal_act_code=act_code,
            stable_reference=reference,
            article_reference=article,
            search_text=unit.search_text,
            citation_items=citations[unit.id],
            source_locator=unit.source_locator or "",
            source_url=source_url,
            source_snapshot_sha=snapshot_sha,
        )


def _article_reference(reference: str) -> str | None:
    parts = reference.split("/")
    article = next((part for part in parts if part.startswith("ARTICLE:")), None)
    if article is None:
        return None
    return "/".join(parts[: parts.index(article) + 1])
