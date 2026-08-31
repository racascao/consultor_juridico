"""Baseline limpo do corpus auditável do MVP2.

Revision ID: 001_v02_foundation_corpus
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_v02_foundation_corpus"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("authority_code", sa.String(80), nullable=False),
        sa.Column("official_url", sa.Text(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sources"),
        sa.UniqueConstraint(
            "authority_code", "official_url", name="uq_sources_authority_url"
        ),
    )
    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("raw_bytes", postgresql.BYTEA(), nullable=False),
        sa.Column("byte_length", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.Text(), nullable=True),
        sa.Column(
            "acquired_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'", name="ck_source_snapshots_sha256_hex"
        ),
        sa.CheckConstraint(
            "byte_length = octet_length(raw_bytes)",
            name="ck_source_snapshots_byte_length",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="fk_snapshots_source",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_snapshots"),
        sa.UniqueConstraint("source_id", "sha256", name="uq_snapshots_source_sha"),
    )
    op.execute(
        """
        CREATE FUNCTION reject_source_snapshot_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'source_snapshots are immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_source_snapshots_immutable
        BEFORE UPDATE OR DELETE ON source_snapshots
        FOR EACH ROW EXECUTE FUNCTION reject_source_snapshot_mutation()
        """
    )
    op.create_table(
        "legal_acts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("act_code", sa.String(120), nullable=False),
        sa.Column("jurisdiction", sa.String(120), nullable=False),
        sa.Column("act_type", sa.String(80), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.CheckConstraint("year >= 1", name="ck_legal_acts_year_positive"),
        sa.PrimaryKeyConstraint("id", name="pk_legal_acts"),
        sa.UniqueConstraint("act_code", name="uq_legal_acts_act_code"),
    )
    op.create_table(
        "act_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("legal_act_id", sa.UUID(), nullable=False),
        sa.Column("source_snapshot_id", sa.UUID(), nullable=False),
        sa.Column("parser_name", sa.String(100), nullable=False),
        sa.Column("parser_version", sa.String(40), nullable=False),
        sa.Column("projection_name", sa.String(100), nullable=False),
        sa.Column("projection_version", sa.String(40), nullable=False),
        sa.Column("version_hash", sa.String(64), nullable=False),
        sa.Column(
            "materialized_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "version_hash ~ '^[0-9a-f]{64}$'", name="ck_act_versions_hash_hex"
        ),
        sa.ForeignKeyConstraint(
            ["legal_act_id"],
            ["legal_acts.id"],
            name="fk_act_versions_legal_act",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["source_snapshots.id"],
            name="fk_act_versions_snapshot",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_act_versions"),
        sa.UniqueConstraint(
            "legal_act_id",
            "source_snapshot_id",
            "parser_name",
            "parser_version",
            "projection_name",
            "projection_version",
            name="uq_act_versions_natural_identity",
        ),
        sa.UniqueConstraint("version_hash", name="uq_act_versions_version_hash"),
    )
    op.create_table(
        "provisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("act_version_id", sa.UUID(), nullable=False),
        sa.Column("stable_key", sa.String(500), nullable=False),
        sa.Column("provision_type", sa.String(30), nullable=False),
        sa.Column("number_label", sa.String(80), nullable=True),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("document_order", sa.BigInteger(), nullable=False),
        sa.Column("citation_text", sa.Text(), nullable=True),
        sa.Column("source_locator", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "legal_status", sa.String(20), server_default="IN_FORCE", nullable=False
        ),
        sa.CheckConstraint(
            "provision_type IN "
            "('DOCUMENT_ROOT','CHAPTER','ARTICLE','CAPUT','PARAGRAPH','INCISO')",
            name="ck_provisions_type",
        ),
        sa.CheckConstraint(
            "legal_status IN ('IN_FORCE','VETOED')", name="ck_provisions_status"
        ),
        sa.CheckConstraint("document_order >= 1", name="ck_provisions_order_positive"),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_provisions_content_hash_hex",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_locator) = 'object' "
            "AND source_locator ? 'paragraph_start' "
            "AND source_locator ? 'paragraph_end' "
            "AND (source_locator->>'paragraph_start')::bigint >= 0 "
            "AND (source_locator->>'paragraph_end')::bigint >= "
            "(source_locator->>'paragraph_start')::bigint",
            name="ck_provisions_source_locator",
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_provisions_no_self_parent",
        ),
        sa.ForeignKeyConstraint(
            ["act_version_id"],
            ["act_versions.id"],
            name="fk_provisions_act_version",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_provisions"),
        sa.UniqueConstraint(
            "act_version_id", "stable_key", name="uq_provisions_stable_key"
        ),
        sa.UniqueConstraint(
            "act_version_id",
            "document_order",
            name="uq_provisions_document_order",
        ),
        sa.UniqueConstraint("id", "act_version_id", name="uq_provisions_id_version"),
    )
    op.create_foreign_key(
        "fk_provisions_parent_same_version",
        "provisions",
        "provisions",
        ["parent_id", "act_version_id"],
        ["id", "act_version_id"],
        ondelete="CASCADE",
    )
    op.create_table(
        "search_units",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("act_version_id", sa.UUID(), nullable=False),
        sa.Column("unit_key", sa.String(500), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "btrim(search_text) <> ''", name="ck_search_units_text_nonempty"
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_search_units_content_hash_hex",
        ),
        sa.ForeignKeyConstraint(
            ["act_version_id"],
            ["act_versions.id"],
            name="fk_search_units_act_version",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_search_units"),
        sa.UniqueConstraint(
            "act_version_id", "unit_key", name="uq_search_units_unit_key"
        ),
    )
    op.create_table(
        "search_unit_provisions",
        sa.Column("search_unit_id", sa.UUID(), nullable=False),
        sa.Column("provision_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_search_unit_provisions_position"),
        sa.ForeignKeyConstraint(
            ["provision_id"],
            ["provisions.id"],
            name="fk_search_unit_provisions_provision",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["search_unit_id"],
            ["search_units.id"],
            name="fk_search_unit_provisions_search_unit",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "search_unit_id", "provision_id", name="pk_search_unit_provisions"
        ),
        sa.UniqueConstraint(
            "search_unit_id", "position", name="uq_search_unit_provisions_position"
        ),
    )
    op.execute(
        """
        CREATE FUNCTION enforce_search_unit_provision_same_version() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE unit_version uuid; provision_version uuid;
        BEGIN
          SELECT act_version_id INTO unit_version
          FROM search_units WHERE id = NEW.search_unit_id;
          SELECT act_version_id INTO provision_version
          FROM provisions WHERE id = NEW.provision_id;
          IF unit_version IS DISTINCT FROM provision_version THEN
            RAISE EXCEPTION 'cross-version search unit link';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_search_unit_provision_same_version
        BEFORE INSERT OR UPDATE ON search_unit_provisions
        FOR EACH ROW EXECUTE FUNCTION enforce_search_unit_provision_same_version()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER trg_search_unit_provision_same_version ON search_unit_provisions"
    )
    op.execute("DROP FUNCTION enforce_search_unit_provision_same_version()")
    op.drop_table("search_unit_provisions")
    op.drop_table("search_units")
    op.drop_constraint(
        "fk_provisions_parent_same_version", "provisions", type_="foreignkey"
    )
    op.drop_table("provisions")
    op.drop_table("act_versions")
    op.drop_table("legal_acts")
    op.execute("DROP TRIGGER trg_source_snapshots_immutable ON source_snapshots")
    op.execute("DROP FUNCTION reject_source_snapshot_mutation()")
    op.drop_table("source_snapshots")
    op.drop_table("sources")
