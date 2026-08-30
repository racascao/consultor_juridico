"""Entidades jurídicas e suas identidades normativas."""

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
    provisions: Mapped[list["LegalProvision"]] = relationship(
        "LegalProvision", back_populates="legal_act"
    )


class LegalProvision(Base):
    """Identidade normativa estável de um dispositivo dentro de um ato."""

    __tablename__ = "legal_provisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    legal_act_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    element_type: Mapped[str] = mapped_column(String(50), nullable=False)
    number_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    identity_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    legal_act: Mapped["LegalAct"] = relationship(
        "LegalAct", back_populates="provisions"
    )
    parent: Mapped["LegalProvision | None"] = relationship(
        "LegalProvision",
        remote_side=[id, legal_act_id],
        foreign_keys=[parent_id, legal_act_id],
        back_populates="children",
        overlaps="legal_act,provisions",
    )
    children: Mapped[list["LegalProvision"]] = relationship(
        "LegalProvision",
        foreign_keys=[parent_id, legal_act_id],
        back_populates="parent",
        overlaps="legal_act,provisions",
    )
    occurrences: Mapped[list["LegalElement"]] = relationship(
        "LegalElement",
        primaryjoin=(
            "and_(LegalProvision.id == LegalElement.legal_provision_id, "
            "LegalProvision.legal_act_id == LegalElement.legal_act_id, "
            "LegalProvision.element_type == LegalElement.element_type)"
        ),
        foreign_keys=(
            "[LegalElement.legal_provision_id, LegalElement.legal_act_id, "
            "LegalElement.element_type]"
        ),
        back_populates="legal_provision",
        overlaps="legal_act,provisions",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["legal_act_id"],
            ["legal_acts.id"],
            name="fk_legal_provisions_legal_act_id_legal_acts",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        UniqueConstraint(
            "legal_act_id",
            "identity_key",
            name="uq_legal_provisions_act_identity_key",
        ),
        UniqueConstraint("id", "legal_act_id", name="uq_legal_provisions_id_legal_act"),
        UniqueConstraint(
            "id",
            "legal_act_id",
            "element_type",
            name="uq_legal_provisions_id_legal_act_type",
        ),
        ForeignKeyConstraint(
            ["parent_id", "legal_act_id"],
            ["legal_provisions.id", "legal_provisions.legal_act_id"],
            name="fk_legal_provisions_parent_act",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name=conv("ck_legal_provisions_no_self_parent"),
        ),
        CheckConstraint(
            "element_type IN ('DOCUMENT_ROOT', 'PREAMBLE', 'TITLE', 'CHAPTER', "
            "'SECTION', 'SUBSECTION', 'ARTICLE', 'CAPUT', 'PARAGRAPH', 'INCISO', "
            "'ALINEA', 'ITEM')",
            name=conv("ck_legal_provisions_element_type"),
        ),
        CheckConstraint(
            "btrim(identity_key) <> ''",
            name=conv("ck_legal_provisions_identity_key_nonempty"),
        ),
        CheckConstraint(
            "(element_type = 'DOCUMENT_ROOT' AND parent_id IS NULL) OR "
            "(element_type <> 'DOCUMENT_ROOT' AND parent_id IS NOT NULL)",
            name=conv("ck_legal_provisions_root_shape"),
        ),
        CheckConstraint(
            "element_type NOT IN ('TITLE', 'CHAPTER', 'SECTION', 'SUBSECTION', "
            "'ARTICLE', 'PARAGRAPH', 'INCISO', 'ALINEA', 'ITEM') OR "
            "(number_label IS NOT NULL AND btrim(number_label) <> '')",
            name=conv("ck_legal_provisions_number_label"),
        ),
        Index(
            "uq_legal_provisions_one_root_per_act",
            "legal_act_id",
            unique=True,
            postgresql_where=text("element_type = 'DOCUMENT_ROOT'"),
        ),
        Index("ix_legal_provisions_parent_act", "parent_id", "legal_act_id"),
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
        "LegalElement",
        back_populates="legal_version",
        cascade="all, delete-orphan",
        overlaps="occurrences",
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="legal_version", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("id", "legal_act_id", name="uq_legal_versions_id_legal_act"),
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
        UUID(as_uuid=True), nullable=False
    )
    legal_act_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    legal_provision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
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
        "LegalVersion",
        back_populates="elements",
        primaryjoin=(
            "and_(LegalElement.legal_version_id == LegalVersion.id, "
            "LegalElement.legal_act_id == LegalVersion.legal_act_id)"
        ),
        foreign_keys=[legal_version_id, legal_act_id],
        overlaps="children,parent,legal_provision,occurrences",
    )
    legal_provision: Mapped["LegalProvision | None"] = relationship(
        "LegalProvision",
        primaryjoin=(
            "and_(LegalElement.legal_provision_id == LegalProvision.id, "
            "LegalElement.legal_act_id == LegalProvision.legal_act_id, "
            "LegalElement.element_type == LegalProvision.element_type)"
        ),
        foreign_keys=[legal_provision_id, legal_act_id, element_type],
        back_populates="occurrences",
        overlaps="legal_version,elements",
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
        ForeignKeyConstraint(
            ["legal_version_id", "legal_act_id"],
            ["legal_versions.id", "legal_versions.legal_act_id"],
            name="fk_legal_elements_version_act",
            ondelete="CASCADE",
            onupdate="NO ACTION",
        ),
        ForeignKeyConstraint(
            ["legal_provision_id", "legal_act_id", "element_type"],
            [
                "legal_provisions.id",
                "legal_provisions.legal_act_id",
                "legal_provisions.element_type",
            ],
            name="fk_legal_elements_provision_act_type",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
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
            "(element_type = 'NOTE' AND legal_provision_id IS NULL) OR "
            "(element_type <> 'NOTE' AND legal_provision_id IS NOT NULL)",
            name=conv("ck_legal_elements_provision_presence"),
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
        Index("ix_legal_elements_legal_provision_id", "legal_provision_id"),
        Index(
            "uq_legal_elements_one_current_per_version_provision",
            "legal_version_id",
            "legal_provision_id",
            unique=True,
            postgresql_where=text(
                "text_status = 'CURRENT' AND content_role = 'NORMATIVE' "
                "AND legal_provision_id IS NOT NULL"
            ),
        ),
    )
