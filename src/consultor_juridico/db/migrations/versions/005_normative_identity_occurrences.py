"""Add normative identities and versioned document occurrences.

Revision ID: 005_normative_identity_occurrences
Revises: 004_frozen_parsing_model
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005_normative_identity_occurrences"
down_revision: str | None = "004_frozen_parsing_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _count_rows(table_name: str) -> int:
    return (
        op.get_bind()
        .execute(sa.text(f"SELECT count(*) FROM {table_name}"))
        .scalar_one()
    )


def _guard_upgrade() -> None:
    legal_elements = _count_rows("legal_elements")
    if legal_elements:
        raise RuntimeError(
            "Upgrade 005 recusado: não há backfill aprovado para LegalElements "
            f"existentes (legal_elements={legal_elements})."
        )


def _guard_downgrade() -> None:
    legal_provisions = _count_rows("legal_provisions")
    legal_elements = _count_rows("legal_elements")
    if legal_provisions or legal_elements:
        raise RuntimeError(
            "Downgrade 005 recusado: identidades/ocorrências não podem ser "
            "convertidas fielmente para 004 "
            f"(legal_provisions={legal_provisions}, legal_elements={legal_elements})."
        )


def upgrade() -> None:
    """Materializa identidades normativas sem criar dados jurídicos."""
    # O revision ID desta migration tem 34 caracteres. A ampliação é monotônica:
    # o downgrade preserva VARCHAR(64) para não tentar reduzir a coluna enquanto
    # o identificador 005 ainda está registrado pelo Alembic.
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    _guard_upgrade()

    op.create_unique_constraint(
        "uq_legal_versions_id_legal_act",
        "legal_versions",
        ["id", "legal_act_id"],
    )
    op.create_table(
        "legal_provisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("legal_act_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("element_type", sa.String(length=50), nullable=False),
        sa.Column("number_label", sa.String(length=100), nullable=True),
        sa.Column("identity_key", sa.String(length=1000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name=op.f("ck_legal_provisions_no_self_parent"),
        ),
        sa.CheckConstraint(
            "element_type IN ('DOCUMENT_ROOT', 'PREAMBLE', 'TITLE', 'CHAPTER', "
            "'SECTION', 'SUBSECTION', 'ARTICLE', 'CAPUT', 'PARAGRAPH', 'INCISO', "
            "'ALINEA', 'ITEM')",
            name=op.f("ck_legal_provisions_element_type"),
        ),
        sa.CheckConstraint(
            "btrim(identity_key) <> ''",
            name=op.f("ck_legal_provisions_identity_key_nonempty"),
        ),
        sa.CheckConstraint(
            "(element_type = 'DOCUMENT_ROOT' AND parent_id IS NULL) OR "
            "(element_type <> 'DOCUMENT_ROOT' AND parent_id IS NOT NULL)",
            name=op.f("ck_legal_provisions_root_shape"),
        ),
        sa.CheckConstraint(
            "element_type NOT IN ('TITLE', 'CHAPTER', 'SECTION', 'SUBSECTION', "
            "'ARTICLE', 'PARAGRAPH', 'INCISO', 'ALINEA', 'ITEM') OR "
            "(number_label IS NOT NULL AND btrim(number_label) <> '')",
            name=op.f("ck_legal_provisions_number_label"),
        ),
        sa.ForeignKeyConstraint(
            ["legal_act_id"],
            ["legal_acts.id"],
            name="fk_legal_provisions_legal_act_id_legal_acts",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_legal_provisions"),
        sa.UniqueConstraint(
            "legal_act_id",
            "identity_key",
            name="uq_legal_provisions_act_identity_key",
        ),
        sa.UniqueConstraint(
            "id", "legal_act_id", name="uq_legal_provisions_id_legal_act"
        ),
        sa.UniqueConstraint(
            "id",
            "legal_act_id",
            "element_type",
            name="uq_legal_provisions_id_legal_act_type",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id", "legal_act_id"],
            ["legal_provisions.id", "legal_provisions.legal_act_id"],
            name="fk_legal_provisions_parent_act",
            ondelete="RESTRICT",
            onupdate="NO ACTION",
        ),
    )
    op.create_index(
        "uq_legal_provisions_one_root_per_act",
        "legal_provisions",
        ["legal_act_id"],
        unique=True,
        postgresql_where=sa.text("element_type = 'DOCUMENT_ROOT'"),
    )
    op.create_index(
        "ix_legal_provisions_parent_act",
        "legal_provisions",
        ["parent_id", "legal_act_id"],
    )

    op.add_column(
        "legal_elements", sa.Column("legal_act_id", sa.UUID(), nullable=False)
    )
    op.add_column(
        "legal_elements", sa.Column("legal_provision_id", sa.UUID(), nullable=True)
    )
    op.drop_constraint(
        "fk_legal_elements_legal_version_id_legal_versions",
        "legal_elements",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_legal_elements_version_act",
        "legal_elements",
        "legal_versions",
        ["legal_version_id", "legal_act_id"],
        ["id", "legal_act_id"],
        ondelete="CASCADE",
        onupdate="NO ACTION",
    )
    op.create_foreign_key(
        "fk_legal_elements_provision_act_type",
        "legal_elements",
        "legal_provisions",
        ["legal_provision_id", "legal_act_id", "element_type"],
        ["id", "legal_act_id", "element_type"],
        ondelete="RESTRICT",
        onupdate="NO ACTION",
    )
    op.create_check_constraint(
        op.f("ck_legal_elements_provision_presence"),
        "legal_elements",
        "(element_type = 'NOTE' AND legal_provision_id IS NULL) OR "
        "(element_type <> 'NOTE' AND legal_provision_id IS NOT NULL)",
    )
    op.create_index(
        "ix_legal_elements_legal_provision_id",
        "legal_elements",
        ["legal_provision_id"],
    )
    op.create_index(
        "uq_legal_elements_one_current_per_version_provision",
        "legal_elements",
        ["legal_version_id", "legal_provision_id"],
        unique=True,
        postgresql_where=sa.text(
            "text_status = 'CURRENT' AND content_role = 'NORMATIVE' "
            "AND legal_provision_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    """Reverte somente quando não houver identidades ou ocorrências."""
    _guard_downgrade()
    op.drop_index(
        "uq_legal_elements_one_current_per_version_provision",
        table_name="legal_elements",
    )
    op.drop_index("ix_legal_elements_legal_provision_id", table_name="legal_elements")
    op.drop_constraint(
        op.f("ck_legal_elements_provision_presence"),
        "legal_elements",
        type_="check",
    )
    op.drop_constraint(
        "fk_legal_elements_provision_act_type", "legal_elements", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_legal_elements_version_act", "legal_elements", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_legal_elements_legal_version_id_legal_versions",
        "legal_elements",
        "legal_versions",
        ["legal_version_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_column("legal_elements", "legal_provision_id")
    op.drop_column("legal_elements", "legal_act_id")
    op.drop_index("ix_legal_provisions_parent_act", table_name="legal_provisions")
    op.drop_index("uq_legal_provisions_one_root_per_act", table_name="legal_provisions")
    op.drop_table("legal_provisions")
    op.drop_constraint(
        "uq_legal_versions_id_legal_act", "legal_versions", type_="unique"
    )
