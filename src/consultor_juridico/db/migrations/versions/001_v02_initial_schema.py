"""Baseline limpa do corpus contextual v0.2."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001_v02_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("official_url", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sources"),
        sa.UniqueConstraint("official_url", name="uq_sources_official_url"),
    )
    op.create_table(
        "source_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_url", sa.Text(), nullable=False),
        sa.Column("final_url", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("etag", sa.Text()),
        sa.Column("last_modified", sa.Text()),
        sa.Column("content_type", sa.Text()),
        sa.CheckConstraint(
            "octet_length(raw_bytes) > 0", name="ck_source_snapshots_raw_nonempty"
        ),
        sa.CheckConstraint(
            "length(sha256) = 64", name="ck_source_snapshots_sha_length"
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_source_snapshots"),
        sa.UniqueConstraint("sha256", name="uq_source_snapshots_sha256"),
    )
    op.execute(
        "CREATE FUNCTION reject_source_snapshot_mutation() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'source_snapshots are immutable'; END; "
        "$$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER trg_source_snapshots_immutable BEFORE UPDATE OR DELETE "
        "ON source_snapshots FOR EACH ROW EXECUTE FUNCTION "
        "reject_source_snapshot_mutation()"
    )
    op.create_table(
        "legal_acts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("act_type", sa.String(50), nullable=False),
        sa.Column("promulgation_date", sa.Date()),
        sa.Column("promulgation_source_locator", sa.Text()),
        sa.PrimaryKeyConstraint("id", name="pk_legal_acts"),
        sa.UniqueConstraint("code", name="uq_legal_acts_code"),
    )
    op.create_table(
        "act_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_act_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_hash", sa.String(64), nullable=False),
        sa.Column("parser_version", sa.String(100), nullable=False),
        sa.Column(
            "parsed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(
            ["legal_act_id"], ["legal_acts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_act_versions"),
        sa.UniqueConstraint(
            "legal_act_id", "version_hash", name="uq_act_versions_act_hash"
        ),
    )
    op.create_index(
        "uq_act_versions_one_active_per_act",
        "act_versions",
        ["legal_act_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    _create_provisions()
    _create_search_units()
    op.create_table(
        "search_unit_provisions",
        sa.Column("search_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["provision_id"], ["provisions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["search_unit_id"], ["search_units.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint(
            "search_unit_id", "provision_id", name="pk_search_unit_provisions"
        ),
    )
    op.create_table(
        "search_unit_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("search_unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("vector", Vector(768), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "dimensions = 768", name="ck_search_unit_embeddings_dimensions"
        ),
        sa.CheckConstraint(
            "length(content_hash) = 64",
            name="ck_search_unit_embeddings_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["search_unit_id"], ["search_units.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_search_unit_embeddings"),
        sa.UniqueConstraint(
            "search_unit_id",
            "provider",
            "model",
            name="uq_search_unit_embeddings_unit_provider_model",
        ),
    )


def _create_provisions() -> None:
    op.create_table(
        "provisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("act_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True)),
        sa.Column("stable_key", sa.String(1000), nullable=False),
        sa.Column("provision_type", sa.String(30), nullable=False),
        sa.Column("label", sa.String(120)),
        sa.Column("document_order", sa.Integer(), nullable=False),
        sa.Column("citation_text", sa.Text(), nullable=False),
        sa.Column("source_locator", sa.Text()),
        sa.CheckConstraint("document_order > 0", name="ck_provisions_order_positive"),
        sa.CheckConstraint(
            "provision_type IN ('PREAMBLE','TITLE','CHAPTER','SECTION',"
            "'SUBSECTION','ARTICLE','CAPUT','PARAGRAPH','INCISO','ALINEA','ITEM')",
            name="ck_provisions_type",
        ),
        sa.CheckConstraint(
            "length(btrim(stable_key)) > 0", name="ck_provisions_key_nonempty"
        ),
        sa.CheckConstraint(
            "length(btrim(citation_text)) > 0",
            name="ck_provisions_citation_nonempty",
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_provisions_no_self_parent",
        ),
        sa.ForeignKeyConstraint(
            ["act_version_id"], ["act_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_provisions"),
        sa.UniqueConstraint("id", "act_version_id", name="uq_provisions_id_version"),
        sa.UniqueConstraint(
            "act_version_id", "stable_key", name="uq_provisions_version_key"
        ),
        sa.UniqueConstraint(
            "act_version_id", "document_order", name="uq_provisions_version_order"
        ),
    )
    op.create_foreign_key(
        "fk_provisions_parent_version",
        "provisions",
        "provisions",
        ["parent_id", "act_version_id"],
        ["id", "act_version_id"],
        ondelete="CASCADE",
    )


def _create_search_units() -> None:
    op.create_table(
        "search_units",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("act_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_type", sa.String(40), nullable=False),
        sa.Column("stable_reference", sa.String(1000), nullable=False),
        sa.Column("anchor_provision_id", postgresql.UUID(as_uuid=True)),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("document_order", sa.Integer(), nullable=False),
        sa.Column("source_locator", sa.Text()),
        sa.Column("source_excerpt", sa.Text()),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('portuguese', search_text)", persisted=True),
            nullable=False,
        ),
        sa.CheckConstraint("document_order > 0", name="ck_search_units_order_positive"),
        sa.CheckConstraint(
            "length(btrim(search_text)) > 0", name="ck_search_units_text_nonempty"
        ),
        sa.CheckConstraint(
            "length(content_hash) = 64", name="ck_search_units_hash_length"
        ),
        sa.CheckConstraint(
            "unit_type IN ('DOCUMENT_METADATA','ARTICLE','CONTEXTUAL_PROVISION')",
            name="ck_search_units_type",
        ),
        sa.ForeignKeyConstraint(
            ["act_version_id"], ["act_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_search_units"),
        sa.UniqueConstraint("id", "act_version_id", name="uq_search_units_id_version"),
        sa.UniqueConstraint(
            "act_version_id", "content_hash", name="uq_search_units_version_hash"
        ),
        sa.UniqueConstraint(
            "act_version_id",
            "stable_reference",
            name="uq_search_units_version_reference",
        ),
        sa.UniqueConstraint(
            "act_version_id", "document_order", name="uq_search_units_version_order"
        ),
    )
    op.create_foreign_key(
        "fk_search_units_anchor_version",
        "search_units",
        "provisions",
        ["anchor_provision_id", "act_version_id"],
        ["id", "act_version_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_search_units_search_vector",
        "search_units",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_table("search_unit_embeddings")
    op.drop_table("search_unit_provisions")
    op.drop_constraint(
        "fk_search_units_anchor_version", "search_units", type_="foreignkey"
    )
    op.drop_index("ix_search_units_search_vector", table_name="search_units")
    op.drop_table("search_units")
    op.drop_constraint("fk_provisions_parent_version", "provisions", type_="foreignkey")
    op.drop_table("provisions")
    op.drop_index("uq_act_versions_one_active_per_act", table_name="act_versions")
    op.drop_table("act_versions")
    op.drop_table("legal_acts")
    op.execute("DROP TRIGGER trg_source_snapshots_immutable ON source_snapshots")
    op.execute("DROP FUNCTION reject_source_snapshot_mutation()")
    op.drop_table("source_snapshots")
    op.drop_table("sources")
