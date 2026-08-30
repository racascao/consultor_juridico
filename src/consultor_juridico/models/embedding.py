"""Entidade para armazenamento de vetores de embeddings (Embedding)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from consultor_juridico.db.base import Base

if TYPE_CHECKING:
    from consultor_juridico.models.chunk import Chunk


class Embedding(Base):
    """Vetor de embeddings gerado para um Chunk por um provedor e modelo.

    Suporta múltiplos embeddings para o mesmo Chunk (modelos diferentes).
    """

    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), default="v1", nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    vector: Mapped[Any | None] = mapped_column(Vector(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunk: Mapped["Chunk"] = relationship("Chunk", back_populates="embeddings")

    __table_args__ = (
        UniqueConstraint(
            "chunk_id",
            "provider_name",
            "model_name",
            "model_version",
            name="uq_embeddings_chunk_provider_model_version",
        ),
        CheckConstraint("dimensions > 0", name="ck_embeddings_dimensions_positive"),
        CheckConstraint(
            text("vector IS NULL OR dimensions = vector_dims(vector)"),
            name="ck_embeddings_vector_dimensions_match",
        ),
    )
