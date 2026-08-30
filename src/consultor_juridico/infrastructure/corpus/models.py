"""Mapeamento SQLAlchemy exclusivo da baseline de corpus v0.2."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class CorpusBase(DeclarativeBase):
    pass


class SourceRecord(CorpusBase):
    __tablename__ = "sources"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    official_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class SourceSnapshotRecord(CorpusBase):
    __tablename__ = "source_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requested_url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    raw_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint(
            "octet_length(raw_bytes) > 0", name="ck_source_snapshots_raw_nonempty"
        ),
        CheckConstraint("length(sha256) = 64", name="ck_source_snapshots_sha_length"),
    )


class LegalActRecord(CorpusBase):
    __tablename__ = "legal_acts"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    act_type: Mapped[str] = mapped_column(String(50), nullable=False)
    promulgation_date: Mapped[date | None] = mapped_column(Date)
    promulgation_source_locator: Mapped[str | None] = mapped_column(Text)


class ActVersionRecord(CorpusBase):
    __tablename__ = "act_versions"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    legal_act_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_acts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "legal_act_id", "version_hash", name="uq_act_versions_act_hash"
        ),
        Index(
            "uq_act_versions_one_active_per_act",
            "legal_act_id",
            unique=True,
            postgresql_where=active.is_(True),
        ),
    )


class ProvisionRecord(CorpusBase):
    __tablename__ = "provisions"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    act_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("act_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    stable_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    provision_type: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str | None] = mapped_column(String(120))
    document_order: Mapped[int] = mapped_column(Integer, nullable=False)
    citation_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_locator: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("document_order > 0", name="ck_provisions_order_positive"),
        CheckConstraint(
            "provision_type IN ('PREAMBLE','TITLE','CHAPTER','SECTION',"
            "'SUBSECTION','ARTICLE','CAPUT','PARAGRAPH','INCISO','ALINEA','ITEM')",
            name="ck_provisions_type",
        ),
        CheckConstraint(
            "length(btrim(stable_key)) > 0", name="ck_provisions_key_nonempty"
        ),
        CheckConstraint(
            "length(btrim(citation_text)) > 0",
            name="ck_provisions_citation_nonempty",
        ),
        CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_provisions_no_self_parent",
        ),
        UniqueConstraint(
            "act_version_id", "stable_key", name="uq_provisions_version_key"
        ),
        UniqueConstraint(
            "act_version_id", "document_order", name="uq_provisions_version_order"
        ),
        UniqueConstraint("id", "act_version_id", name="uq_provisions_id_version"),
        ForeignKeyConstraint(
            ["parent_id", "act_version_id"],
            ["provisions.id", "provisions.act_version_id"],
            name="fk_provisions_parent_version",
            ondelete="CASCADE",
        ),
    )


class SearchUnitRecord(CorpusBase):
    __tablename__ = "search_units"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    act_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("act_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    unit_type: Mapped[str] = mapped_column(String(40), nullable=False)
    stable_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    anchor_provision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document_order: Mapped[int] = mapped_column(Integer, nullable=False)
    source_locator: Mapped[str | None] = mapped_column(Text)
    source_excerpt: Mapped[str | None] = mapped_column(Text)
    search_vector: Mapped[object] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('portuguese', search_text)", persisted=True),
        nullable=False,
    )
    __table_args__ = (
        CheckConstraint("document_order > 0", name="ck_search_units_order_positive"),
        CheckConstraint(
            "length(btrim(search_text)) > 0", name="ck_search_units_text_nonempty"
        ),
        CheckConstraint(
            "length(content_hash) = 64", name="ck_search_units_hash_length"
        ),
        CheckConstraint(
            "unit_type IN ('DOCUMENT_METADATA','ARTICLE','CONTEXTUAL_PROVISION')",
            name="ck_search_units_type",
        ),
        UniqueConstraint(
            "act_version_id", "content_hash", name="uq_search_units_version_hash"
        ),
        UniqueConstraint(
            "act_version_id",
            "stable_reference",
            name="uq_search_units_version_reference",
        ),
        UniqueConstraint(
            "act_version_id", "document_order", name="uq_search_units_version_order"
        ),
        UniqueConstraint("id", "act_version_id", name="uq_search_units_id_version"),
        Index("ix_search_units_search_vector", "search_vector", postgresql_using="gin"),
        ForeignKeyConstraint(
            ["anchor_provision_id", "act_version_id"],
            ["provisions.id", "provisions.act_version_id"],
            name="fk_search_units_anchor_version",
            ondelete="RESTRICT",
        ),
    )


class SearchUnitProvisionRecord(CorpusBase):
    __tablename__ = "search_unit_provisions"
    search_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_units.id", ondelete="CASCADE"),
        primary_key=True,
    )
    provision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("provisions.id", ondelete="CASCADE"),
        primary_key=True,
    )


class SearchUnitEmbeddingRecord(CorpusBase):
    __tablename__ = "search_unit_embeddings"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    search_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_units.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    vector: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "dimensions = 768", name="ck_search_unit_embeddings_dimensions"
        ),
        CheckConstraint(
            "length(content_hash) = 64",
            name="ck_search_unit_embeddings_hash_length",
        ),
        UniqueConstraint(
            "search_unit_id",
            "provider",
            "model",
            name="uq_search_unit_embeddings_unit_provider_model",
        ),
    )


def _reject_snapshot_mutation(_mapper, _connection, _target) -> None:
    raise ValueError("SourceSnapshot é imutável.")


event.listen(SourceSnapshotRecord, "before_update", _reject_snapshot_mutation)
event.listen(SourceSnapshotRecord, "before_delete", _reject_snapshot_mutation)
