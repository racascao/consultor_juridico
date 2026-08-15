"""Entidades para gerenciar conjuntos de evidências e snapshots."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from consultor_juridico.db.base import Base

if TYPE_CHECKING:
    from consultor_juridico.models.chunk import Chunk
    from consultor_juridico.models.claim import Citation
    from consultor_juridico.models.legal import LegalElement


class EvidenceSet(Base):
    """Representa a seleção concreta de evidências gerada para uma consulta."""

    __tablename__ = "evidence_sets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_strategy: Mapped[str] = mapped_column(String(100), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(50), nullable=False)
    total_items: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items: Mapped[list["EvidenceItem"]] = relationship(
        "EvidenceItem", back_populates="evidence_set", cascade="all, delete-orphan"
    )
    citations: Mapped[list["Citation"]] = relationship(
        "Citation", back_populates="evidence_set", cascade="all, delete-orphan"
    )


class EvidenceItem(Base):
    """Snapshot congelado de uma evidência enviada ao LLM."""

    __tablename__ = "evidence_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evidence_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    legal_element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_elements.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evidence_code: Mapped[str] = mapped_column(String(50), nullable=False)
    citation_label: Mapped[str] = mapped_column(String(255), nullable=False)
    text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validation_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    evidence_set: Mapped["EvidenceSet"] = relationship(
        "EvidenceSet", back_populates="items"
    )
    chunk: Mapped["Chunk"] = relationship("Chunk")
    legal_element: Mapped["LegalElement"] = relationship("LegalElement")
    citations: Mapped[list["Citation"]] = relationship(
        "Citation",
        back_populates="evidence_item",
        cascade="all, delete-orphan",
        overlaps="evidence_set,citations",
    )

    __table_args__ = (
        UniqueConstraint(
            "evidence_set_id", "evidence_code", name="uq_evidence_item_code"
        ),
        # Chave única composta necessária para que Citation.evidence_set_id
        # possa referenciar este par via FK composta, garantindo que a
        # Citation só pode apontar para EvidenceItems do mesmo EvidenceSet.
        UniqueConstraint(
            "id", "evidence_set_id", name="uq_evidence_items_id_evidence_set"
        ),
    )
