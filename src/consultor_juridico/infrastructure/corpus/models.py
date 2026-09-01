"""Modelos SQLAlchemy do baseline v0.2."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from consultor_juridico.db.base import Base


class SourceModel(Base):
    __tablename__ = "sources"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    authority_code: Mapped[str] = mapped_column(String(80), nullable=False)
    official_url: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class SourceSnapshotModel(Base):
    __tablename__ = "source_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    byte_length: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LegalActModel(Base):
    __tablename__ = "legal_acts"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    act_code: Mapped[str] = mapped_column(String(120), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(120), nullable=False)
    act_type: Mapped[str] = mapped_column(String(80), nullable=False)
    number: Mapped[str] = mapped_column(String(40), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)


class ActVersionModel(Base):
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
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    projection_name: Mapped[str] = mapped_column(String(100), nullable=False)
    projection_version: Mapped[str] = mapped_column(String(40), nullable=False)
    version_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    materialized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProvisionModel(Base):
    __tablename__ = "provisions"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    act_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("act_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    stable_key: Mapped[str] = mapped_column(String(500), nullable=False)
    provision_type: Mapped[str] = mapped_column(String(30), nullable=False)
    number_label: Mapped[str | None] = mapped_column(String(80))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    document_order: Mapped[int] = mapped_column(BigInteger, nullable=False)
    citation_text: Mapped[str | None] = mapped_column(Text)
    source_locator: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    legal_status: Mapped[str] = mapped_column(String(20), nullable=False)


class SearchUnitModel(Base):
    __tablename__ = "search_units"
    __table_args__ = (
        Index(
            "ix_search_units_fts_portuguese",
            text("to_tsvector('portuguese'::regconfig, search_text)"),
            postgresql_using="gin",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    act_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("act_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    unit_key: Mapped[str] = mapped_column(String(500), nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class SearchUnitProvisionModel(Base):
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
    position: Mapped[int] = mapped_column(Integer, nullable=False)
