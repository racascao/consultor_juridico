"""Entidades de chunking e associação N:N (Chunk e ChunkLegalElement)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from consultor_juridico.db.base import Base

if TYPE_CHECKING:
    from consultor_juridico.models.embedding import Embedding
    from consultor_juridico.models.legal import LegalElement, LegalVersion


class Chunk(Base):
    """Unidade de texto delimitada para indexação e busca (lexical e semântica)."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    legal_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strategy_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tsv_content: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    legal_version: Mapped["LegalVersion"] = relationship(
        "LegalVersion", back_populates="chunks"
    )
    element_links: Mapped[list["ChunkLegalElement"]] = relationship(
        "ChunkLegalElement", back_populates="chunk", cascade="all, delete-orphan"
    )
    embeddings: Mapped[list["Embedding"]] = relationship(
        "Embedding", back_populates="chunk", cascade="all, delete-orphan"
    )


class ChunkLegalElement(Base):
    """Tabela de junção N:N entre Chunk e LegalElement."""

    __tablename__ = "chunk_legal_elements"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    legal_element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_elements.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    chunk: Mapped["Chunk"] = relationship("Chunk", back_populates="element_links")
    legal_element: Mapped["LegalElement"] = relationship(
        "LegalElement", back_populates="chunk_links"
    )
