"""Entidades jurídicas (LegalAct, LegalVersion e LegalElement)."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import conv

from consultor_juridico.db.base import Base

if TYPE_CHECKING:
    from consultor_juridico.models.chunk import Chunk, ChunkLegalElement
    from consultor_juridico.models.parsing import ParsingRun
    from consultor_juridico.models.source import SourceDocument


class LegalAct(Base):
    """Identifica a norma jurídica em abstrato (ex.: CF/88, ADCT)."""

    __tablename__ = "legal_acts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
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
    parsing_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(100), nullable=False)
    parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active_for_query: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    legal_act: Mapped["LegalAct"] = relationship("LegalAct", back_populates="versions")
    source_document: Mapped["SourceDocument"] = relationship(
        "SourceDocument",
        back_populates="legal_versions",
        foreign_keys=[source_document_id],
        overlaps="legal_versions,parsing_run,source_document",
    )
    parsing_run: Mapped["ParsingRun"] = relationship(
        "ParsingRun",
        back_populates="legal_versions",
        primaryjoin=(
            "and_(LegalVersion.parsing_run_id == ParsingRun.id, "
            "LegalVersion.source_document_id == ParsingRun.source_document_id)"
        ),
        foreign_keys=[parsing_run_id, source_document_id],
        overlaps="legal_versions,source_document",
    )
    elements: Mapped[list["LegalElement"]] = relationship(
        "LegalElement", back_populates="legal_version", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="legal_version", cascade="all, delete-orphan"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["parsing_run_id", "source_document_id"],
            ["parsing_runs.id", "parsing_runs.source_document_id"],
            name="fk_legal_versions_parsing_run_source_document",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        UniqueConstraint(
            "parsing_run_id",
            "legal_act_id",
            name="uq_legal_versions_parsing_run_legal_act",
        ),
        Index(
            "uq_legal_versions_one_active_per_act",
            "legal_act_id",
            unique=True,
            postgresql_where=text("is_active_for_query IS TRUE"),
        ),
        Index("ix_legal_versions_source_document_id", "source_document_id"),
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
        UUID(as_uuid=True), nullable=True
    )
    element_type: Mapped[str] = mapped_column(String(50), nullable=False)
    number_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_order: Mapped[int] = mapped_column(BigInteger, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_status: Mapped[str] = mapped_column(
        String(20),
        default="UNRESOLVED",
        server_default="UNRESOLVED",
        nullable=False,
    )
    content_role: Mapped[str] = mapped_column(
        String(30), default="NORMATIVE", server_default="NORMATIVE", nullable=False
    )
    path: Mapped[str | None] = mapped_column(String(500), index=True, nullable=True)
    source_locator: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    parser_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    legal_version: Mapped["LegalVersion"] = relationship(
        "LegalVersion", back_populates="elements", overlaps="children,parent"
    )
    parent: Mapped["LegalElement | None"] = relationship(
        "LegalElement",
        remote_side=[id, legal_version_id],
        foreign_keys=[parent_id, legal_version_id],
        back_populates="children",
        overlaps="elements,legal_version",
    )
    children: Mapped[list["LegalElement"]] = relationship(
        "LegalElement",
        foreign_keys=[parent_id, legal_version_id],
        back_populates="parent",
        cascade="all, delete-orphan",
        overlaps="elements,legal_version",
    )
    chunk_links: Mapped[list["ChunkLegalElement"]] = relationship(
        "ChunkLegalElement",
        back_populates="legal_element",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "legal_version_id",
            "document_order",
            name="uq_legal_elements_version_document_order",
        ),
        UniqueConstraint(
            "id",
            "legal_version_id",
            name="uq_legal_elements_id_legal_version",
        ),
        ForeignKeyConstraint(
            ["parent_id", "legal_version_id"],
            ["legal_elements.id", "legal_elements.legal_version_id"],
            name="fk_legal_elements_parent_version_composite",
            ondelete="CASCADE",
            onupdate="NO ACTION",
        ),
        CheckConstraint(
            "parent_id <> id", name=conv("ck_legal_elements_no_self_parent")
        ),
        CheckConstraint(
            "document_order >= 1",
            name=conv("ck_legal_elements_document_order_positive"),
        ),
        CheckConstraint(
            "element_type IN ('DOCUMENT_ROOT', 'PREAMBLE', 'TITLE', 'CHAPTER', "
            "'SECTION', 'SUBSECTION', 'ARTICLE', 'CAPUT', 'PARAGRAPH', 'INCISO', "
            "'ALINEA', 'ITEM', 'NOTE')",
            name=conv("ck_legal_elements_element_type"),
        ),
        CheckConstraint(
            "text_status IN ('CURRENT', 'HISTORICAL', 'REVOKED', 'UNRESOLVED', "
            "'NOT_APPLICABLE')",
            name=conv("ck_legal_elements_text_status"),
        ),
        CheckConstraint(
            "content_role IN ('NORMATIVE', 'AMENDMENT_NOTE', 'REFERENCE_NOTE', "
            "'EDITORIAL_NOTE')",
            name=conv("ck_legal_elements_content_role"),
        ),
        CheckConstraint(
            "(content_role = 'NORMATIVE' AND text_status <> 'NOT_APPLICABLE') OR "
            "(content_role <> 'NORMATIVE' AND text_status = 'NOT_APPLICABLE')",
            name=conv("ck_legal_elements_role_status"),
        ),
        CheckConstraint(
            "(element_type = 'NOTE' AND content_role <> 'NORMATIVE') OR "
            "(element_type <> 'NOTE' AND content_role = 'NORMATIVE')",
            name=conv("ck_legal_elements_note_role"),
        ),
        CheckConstraint(
            "(element_type = 'DOCUMENT_ROOT' AND parent_id IS NULL "
            "AND document_order = 1 AND content_role = 'NORMATIVE' "
            "AND text_status = 'CURRENT') OR "
            "(element_type <> 'DOCUMENT_ROOT' AND parent_id IS NOT NULL)",
            name=conv("ck_legal_elements_root_shape"),
        ),
        CheckConstraint(
            "element_type NOT IN ('TITLE', 'CHAPTER', 'SECTION', 'SUBSECTION', "
            "'ARTICLE', 'PARAGRAPH', 'INCISO', 'ALINEA', 'ITEM') OR "
            "(number_label IS NOT NULL AND btrim(number_label) <> '')",
            name=conv("ck_legal_elements_number_label"),
        ),
        CheckConstraint(
            "btrim(raw_text) <> ''",
            name=conv("ck_legal_elements_raw_text_nonempty"),
        ),
        CheckConstraint(
            "btrim(normalized_text) <> ''",
            name=conv("ck_legal_elements_normalized_text_nonempty"),
        ),
        CheckConstraint(
            "jsonb_typeof(source_locator) = 'object' "
            "AND source_locator ? 'block_index' "
            "AND jsonb_typeof(source_locator -> 'block_index') = 'number'",
            name=conv("ck_legal_elements_source_locator_object"),
        ),
        CheckConstraint(
            "parser_metadata IS NULL OR jsonb_typeof(parser_metadata) = 'object'",
            name=conv("ck_legal_elements_parser_metadata_object"),
        ),
        Index(
            "uq_legal_elements_one_root_per_version",
            "legal_version_id",
            unique=True,
            postgresql_where=text("element_type = 'DOCUMENT_ROOT'"),
        ),
    )
