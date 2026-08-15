"""Entidades de origem e documentos brutos (Source e SourceDocument)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from consultor_juridico.db.base import Base

if TYPE_CHECKING:
    from consultor_juridico.models.legal import LegalVersion


class Source(Base):
    """Representa a autoridade/fonte oficial do documento (ex.: Portal do Planalto)."""

    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("base_url", name="uq_sources_base_url"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    documents: Mapped[list["SourceDocument"]] = relationship(
        "SourceDocument", back_populates="source", cascade="all, delete-orphan"
    )


class SourceDocument(Base):
    """Armazena o documento bruto imutável baixado da fonte oficial."""

    __tablename__ = "source_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    url_source: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "content_hash_sha256",
            name="uq_source_documents_source_hash",
        ),
    )

    raw_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    http_headers: Mapped[list[list[str]] | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    source: Mapped["Source"] = relationship("Source", back_populates="documents")
    legal_versions: Mapped[list["LegalVersion"]] = relationship(
        "LegalVersion", back_populates="source_document"
    )
