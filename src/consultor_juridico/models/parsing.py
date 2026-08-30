"""Entidade de execução lógica do parsing documental."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import conv
from sqlalchemy.sql import func

from consultor_juridico.db.base import Base

if TYPE_CHECKING:
    from consultor_juridico.models.legal import LegalVersion
    from consultor_juridico.models.source import SourceDocument


class ParsingRun(Base):
    """Processamento lógico de uma captura por uma versão específica do parser."""

    __tablename__ = "parsing_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "source_documents.id",
            name="fk_parsing_runs_source_document_id_source_documents",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        nullable=False,
    )
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="RUNNING", server_default="RUNNING", nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    source_document: Mapped["SourceDocument"] = relationship(
        "SourceDocument",
        back_populates="parsing_runs",
        foreign_keys=[source_document_id],
        overlaps="legal_versions,parsing_run",
    )
    legal_versions: Mapped[list["LegalVersion"]] = relationship(
        "LegalVersion",
        back_populates="parsing_run",
        primaryjoin=(
            "and_(ParsingRun.id == LegalVersion.parsing_run_id, "
            "ParsingRun.source_document_id == LegalVersion.source_document_id)"
        ),
        foreign_keys=("[LegalVersion.parsing_run_id, LegalVersion.source_document_id]"),
        overlaps="source_document,legal_versions",
    )

    __table_args__ = (
        UniqueConstraint(
            "source_document_id",
            "parser_name",
            "parser_version",
            name="uq_parsing_runs_source_parser",
        ),
        UniqueConstraint(
            "id",
            "source_document_id",
            name="uq_parsing_runs_id_source_document",
        ),
        CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name=conv("ck_parsing_runs_status"),
        ),
        CheckConstraint(
            "(status = 'RUNNING' AND finished_at IS NULL) OR "
            "(status IN ('COMPLETED', 'FAILED') AND finished_at IS NOT NULL)",
            name=conv("ck_parsing_runs_status_finished_at"),
        ),
    )
