"""Create the frozen constitutional parsing persistence model.

Revision ID: 004_frozen_parsing_model
Revises: 003_ingestion_raw_storage
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_frozen_parsing_model"
down_revision: str | None = "003_ingestion_raw_storage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _count_rows(table_name: str) -> int:
    bind = op.get_bind()
    return bind.execute(sa.text(f"SELECT count(*) FROM {table_name}")).scalar_one()


def _guard_upgrade() -> None:
    legal_versions = _count_rows("legal_versions")
    legal_elements = _count_rows("legal_elements")
    if legal_versions or legal_elements:
        raise RuntimeError(
            "Upgrade 004 recusado: não há backfill aprovado para dados derivados "
            f"existentes (legal_versions={legal_versions}, "
            f"legal_elements={legal_elements})."
        )


def _guard_downgrade() -> None:
    parsing_runs = _count_rows("parsing_runs")
    legal_versions = _count_rows("legal_versions")
    legal_elements = _count_rows("legal_elements")
    if parsing_runs or legal_versions or legal_elements:
        raise RuntimeError(
            "Downgrade 004 recusado: dados derivados não podem ser convertidos "
            "fielmente para 003 "
            f"(parsing_runs={parsing_runs}, legal_versions={legal_versions}, "
            f"legal_elements={legal_elements})."
        )


def upgrade() -> None:
    """Materializa somente o modelo congelado, sem criar dados jurídicos."""
    _guard_upgrade()

    op.create_table(
        "parsing_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=False),
        sa.Column("parser_name", sa.String(length=100), nullable=False),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'RUNNING'"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name=op.f("ck_parsing_runs_status"),
        ),
        sa.CheckConstraint(
            "(status = 'RUNNING' AND finished_at IS NULL) OR "
            "(status IN ('COMPLETED', 'FAILED') AND finished_at IS NOT NULL)",
            name=op.f("ck_parsing_runs_status_finished_at"),
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_documents.id"],
            name="fk_parsing_runs_source_document_id_source_documents",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_parsing_runs"),
        sa.UniqueConstraint(
            "source_document_id",
            "parser_name",
            "parser_version",
            name="uq_parsing_runs_source_parser",
        ),
        sa.UniqueConstraint(
            "id",
            "source_document_id",
            name="uq_parsing_runs_id_source_document",
        ),
    )

    op.add_column(
        "legal_versions", sa.Column("parsing_run_id", sa.UUID(), nullable=False)
    )
    op.create_foreign_key(
        "fk_legal_versions_parsing_run_source_document",
        "legal_versions",
        "parsing_runs",
        ["parsing_run_id", "source_document_id"],
        ["id", "source_document_id"],
        ondelete="RESTRICT",
        onupdate="NO ACTION",
    )
    op.create_unique_constraint(
        "uq_legal_versions_parsing_run_legal_act",
        "legal_versions",
        ["parsing_run_id", "legal_act_id"],
    )
    op.alter_column(
        "legal_versions",
        "is_active_for_query",
        existing_type=sa.Boolean(),
        server_default=sa.text("false"),
        existing_nullable=False,
    )
    op.create_index(
        "uq_legal_versions_one_active_per_act",
        "legal_versions",
        ["legal_act_id"],
        unique=True,
        postgresql_where=sa.text("is_active_for_query IS TRUE"),
    )
    op.create_index(
        "ix_legal_versions_source_document_id",
        "legal_versions",
        ["source_document_id"],
        unique=False,
    )

    op.add_column(
        "legal_elements", sa.Column("document_order", sa.BigInteger(), nullable=False)
    )
    op.add_column(
        "legal_elements",
        sa.Column(
            "text_status",
            sa.String(length=20),
            server_default=sa.text("'UNRESOLVED'"),
            nullable=False,
        ),
    )
    op.add_column(
        "legal_elements",
        sa.Column(
            "content_role",
            sa.String(length=30),
            server_default=sa.text("'NORMATIVE'"),
            nullable=False,
        ),
    )
    op.add_column(
        "legal_elements",
        sa.Column("source_locator", postgresql.JSONB(), nullable=False),
    )
    op.add_column(
        "legal_elements",
        sa.Column("parser_metadata", postgresql.JSONB(), nullable=True),
    )
    op.alter_column(
        "legal_elements",
        "normalized_text",
        existing_type=sa.Text(),
        nullable=False,
        existing_nullable=True,
    )

    op.drop_constraint(
        "fk_legal_elements_parent_id_legal_elements",
        "legal_elements",
        type_="foreignkey",
    )
    op.create_unique_constraint(
        "uq_legal_elements_id_legal_version",
        "legal_elements",
        ["id", "legal_version_id"],
    )
    op.create_foreign_key(
        "fk_legal_elements_parent_version_composite",
        "legal_elements",
        "legal_elements",
        ["parent_id", "legal_version_id"],
        ["id", "legal_version_id"],
        ondelete="CASCADE",
        onupdate="NO ACTION",
    )
    op.create_unique_constraint(
        "uq_legal_elements_version_document_order",
        "legal_elements",
        ["legal_version_id", "document_order"],
    )
    op.create_check_constraint(
        op.f("ck_legal_elements_document_order_positive"),
        "legal_elements",
        "document_order >= 1",
    )
    op.create_check_constraint(
        op.f("ck_legal_elements_element_type"),
        "legal_elements",
        "element_type IN ('DOCUMENT_ROOT', 'PREAMBLE', 'TITLE', 'CHAPTER', "
        "'SECTION', 'SUBSECTION', 'ARTICLE', 'CAPUT', 'PARAGRAPH', 'INCISO', "
        "'ALINEA', 'ITEM', 'NOTE')",
    )
    op.create_check_constraint(
        op.f("ck_legal_elements_text_status"),
        "legal_elements",
        "text_status IN ('CURRENT', 'HISTORICAL', 'REVOKED', 'UNRESOLVED', "
        "'NOT_APPLICABLE')",
    )
    op.create_check_constraint(
        op.f("ck_legal_elements_content_role"),
        "legal_elements",
        "content_role IN ('NORMATIVE', 'AMENDMENT_NOTE', 'REFERENCE_NOTE', "
        "'EDITORIAL_NOTE')",
    )
    op.create_check_constraint(
        op.f("ck_legal_elements_role_status"),
        "legal_elements",
        "(content_role = 'NORMATIVE' AND text_status <> 'NOT_APPLICABLE') OR "
        "(content_role <> 'NORMATIVE' AND text_status = 'NOT_APPLICABLE')",
    )
    op.create_check_constraint(
        op.f("ck_legal_elements_note_role"),
        "legal_elements",
        "(element_type = 'NOTE' AND content_role <> 'NORMATIVE') OR "
        "(element_type <> 'NOTE' AND content_role = 'NORMATIVE')",
    )
    op.create_check_constraint(
        op.f("ck_legal_elements_root_shape"),
        "legal_elements",
        "(element_type = 'DOCUMENT_ROOT' AND parent_id IS NULL "
        "AND document_order = 1 AND content_role = 'NORMATIVE' "
        "AND text_status = 'CURRENT') OR "
        "(element_type <> 'DOCUMENT_ROOT' AND parent_id IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_legal_elements_number_label"),
        "legal_elements",
        "element_type NOT IN ('TITLE', 'CHAPTER', 'SECTION', 'SUBSECTION', "
        "'ARTICLE', 'PARAGRAPH', 'INCISO', 'ALINEA', 'ITEM') OR "
        "(number_label IS NOT NULL AND btrim(number_label) <> '')",
    )
    op.create_check_constraint(
        op.f("ck_legal_elements_raw_text_nonempty"),
        "legal_elements",
        "btrim(raw_text) <> ''",
    )
    op.create_check_constraint(
        op.f("ck_legal_elements_normalized_text_nonempty"),
        "legal_elements",
        "btrim(normalized_text) <> ''",
    )
    op.create_check_constraint(
        op.f("ck_legal_elements_source_locator_object"),
        "legal_elements",
        "jsonb_typeof(source_locator) = 'object' "
        "AND source_locator ? 'block_index' "
        "AND jsonb_typeof(source_locator -> 'block_index') = 'number'",
    )
    op.create_check_constraint(
        op.f("ck_legal_elements_parser_metadata_object"),
        "legal_elements",
        "parser_metadata IS NULL OR jsonb_typeof(parser_metadata) = 'object'",
    )
    op.create_index(
        "uq_legal_elements_one_root_per_version",
        "legal_elements",
        ["legal_version_id"],
        unique=True,
        postgresql_where=sa.text("element_type = 'DOCUMENT_ROOT'"),
    )

    op.drop_column("legal_elements", "ordinal")
    op.drop_column("legal_elements", "is_revoked")


def downgrade() -> None:
    """Retorna a 003 somente sem dados derivados, evitando perda silenciosa."""
    _guard_downgrade()

    op.drop_index("uq_legal_elements_one_root_per_version", table_name="legal_elements")
    for constraint_name in (
        "ck_legal_elements_parser_metadata_object",
        "ck_legal_elements_source_locator_object",
        "ck_legal_elements_normalized_text_nonempty",
        "ck_legal_elements_raw_text_nonempty",
        "ck_legal_elements_number_label",
        "ck_legal_elements_root_shape",
        "ck_legal_elements_note_role",
        "ck_legal_elements_role_status",
        "ck_legal_elements_content_role",
        "ck_legal_elements_text_status",
        "ck_legal_elements_element_type",
        "ck_legal_elements_document_order_positive",
    ):
        op.drop_constraint(op.f(constraint_name), "legal_elements", type_="check")
    op.drop_constraint(
        "uq_legal_elements_version_document_order",
        "legal_elements",
        type_="unique",
    )
    op.drop_constraint(
        "fk_legal_elements_parent_version_composite",
        "legal_elements",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_legal_elements_id_legal_version",
        "legal_elements",
        type_="unique",
    )
    op.create_foreign_key(
        "fk_legal_elements_parent_id_legal_elements",
        "legal_elements",
        "legal_elements",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.add_column("legal_elements", sa.Column("ordinal", sa.Integer(), nullable=True))
    op.add_column(
        "legal_elements",
        sa.Column(
            "is_revoked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.alter_column(
        "legal_elements",
        "normalized_text",
        existing_type=sa.Text(),
        nullable=True,
        existing_nullable=False,
    )
    op.drop_column("legal_elements", "parser_metadata")
    op.drop_column("legal_elements", "source_locator")
    op.drop_column("legal_elements", "content_role")
    op.drop_column("legal_elements", "text_status")
    op.drop_column("legal_elements", "document_order")

    op.drop_index("uq_legal_versions_one_active_per_act", table_name="legal_versions")
    op.drop_index("ix_legal_versions_source_document_id", table_name="legal_versions")
    op.drop_constraint(
        "uq_legal_versions_parsing_run_legal_act",
        "legal_versions",
        type_="unique",
    )
    op.drop_constraint(
        "fk_legal_versions_parsing_run_source_document",
        "legal_versions",
        type_="foreignkey",
    )
    op.alter_column(
        "legal_versions",
        "is_active_for_query",
        existing_type=sa.Boolean(),
        server_default=sa.text("true"),
        existing_nullable=False,
    )
    op.drop_column("legal_versions", "parsing_run_id")
    op.drop_table("parsing_runs")
