"""Entidades jurídicas (LegalAct, LegalVersion e LegalElement)."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from consultor_juridico.db.base import Base

if TYPE_CHECKING:
    from consultor_juridico.models.chunk import Chunk, ChunkLegalElement
    from consultor_juridico.models.source import SourceDocument


class LegalAct(Base):
    """Identifica a norma jurídica em abstrato (ex.: CF/88, ADCT)."""

    __tablename__ = "legal_acts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    act_type: Mapped[str] = mapped_column(String(50), nullable=False)
    official_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    enactment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    versions: Mapped[list["LegalVersion"]] = relationship(
        "LegalVersion", back_populates="legal_act"
    )


class LegalVersion(Base):
    """Representa uma versão/captura estrutural de um LegalAct."""

    __tablename__ = "legal_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    legal_act_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_acts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_label: Mapped[str] = mapped_column(String(100), nullable=False)
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active_for_query: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    legal_act: Mapped["LegalAct"] = relationship("LegalAct", back_populates="versions")
    source_document: Mapped["SourceDocument"] = relationship(
        "SourceDocument", back_populates="legal_versions"
    )
    elements: Mapped[list["LegalElement"]] = relationship(
        "LegalElement", back_populates="legal_version", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="legal_version", cascade="all, delete-orphan"
    )


class LegalElement(Base):
    """Representa um nó individual na árvore hierárquica do texto normativo.

    A identidade semântica da entidade é dada pela chave primária (id UUID).
    O campo path é um atributo denormalizado auxiliar de navegação.
    """

    __tablename__ = "legal_elements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    legal_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_elements.id", ondelete="CASCADE"),
        nullable=True,
    )
    element_type: Mapped[str] = mapped_column(String(50), nullable=False)
    number_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ordinal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    path: Mapped[str | None] = mapped_column(String(500), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    legal_version: Mapped["LegalVersion"] = relationship(
        "LegalVersion", back_populates="elements"
    )
    parent: Mapped["LegalElement | None"] = relationship(
        "LegalElement", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["LegalElement"]] = relationship(
        "LegalElement", back_populates="parent", cascade="all, delete-orphan"
    )
    chunk_links: Mapped[list["ChunkLegalElement"]] = relationship(
        "ChunkLegalElement",
        back_populates="legal_element",
        cascade="all, delete-orphan",
    )
