"""Entidades para gerenciar afirmações e citações (Claim e Citation)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from consultor_juridico.db.base import Base

if TYPE_CHECKING:
    from consultor_juridico.models.evidence import EvidenceItem, EvidenceSet


class Claim(Base):
    """Afirmação factual gerada pelo LLM na resposta estruturada."""

    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    claim_code: Mapped[str] = mapped_column(String(50), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    citations: Mapped[list["Citation"]] = relationship(
        "Citation", back_populates="claim", cascade="all, delete-orphan"
    )


class Citation(Base):
    """Vínculo auditável entre uma Claim e o EvidenceItem correspondente.

    A FK composta (evidence_item_id, evidence_set_id) referencia a constraint
    única uq_evidence_items_id_evidence_set em EvidenceItem, garantindo
    fisicamente que uma Citation não pode apontar para um EvidenceItem que
    pertença a um EvidenceSet diferente do registrado em evidence_set_id.
    """

    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    evidence_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    validation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    claim: Mapped["Claim"] = relationship("Claim", back_populates="citations")
    evidence_item: Mapped["EvidenceItem"] = relationship(
        "EvidenceItem",
        back_populates="citations",
        primaryjoin="Citation.evidence_item_id == EvidenceItem.id",
        foreign_keys="[Citation.evidence_item_id]",
    )
    evidence_set: Mapped["EvidenceSet"] = relationship(
        "EvidenceSet", back_populates="citations"
    )

    __table_args__ = (
        # FK composta que garante que evidence_item_id pertence ao evidence_set_id
        # informado nesta Citation. Impede cruzamento de evidências entre
        # EvidenceSets distintos.
        ForeignKeyConstraint(
            ["evidence_item_id", "evidence_set_id"],
            ["evidence_items.id", "evidence_items.evidence_set_id"],
            ondelete="RESTRICT",
            name="fk_citations_evidence_item_set_composite",
        ),
    )
