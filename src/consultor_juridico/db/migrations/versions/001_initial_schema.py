"""Initial schema setup with pgvector and legal domain tables

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-08-14 18:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Habilitar a extensão pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Criar tabelas documentais (sources e source_documents)
    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
    )

    op.create_table(
        "source_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("url_source", sa.Text(), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("content_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "http_headers", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name=op.f("fk_source_documents_source_id_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_documents")),
        sa.UniqueConstraint(
            "content_hash_sha256", name=op.f("uq_source_documents_content_hash_sha256")
        ),
    )
    op.create_index(
        op.f("ix_source_documents_content_hash_sha256"),
        "source_documents",
        ["content_hash_sha256"],
        unique=True,
    )

    # 3. Criar tabelas jurídicas (legal_acts, legal_versions, legal_elements)
    op.create_table(
        "legal_acts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("short_name", sa.String(length=50), nullable=False),
        sa.Column("act_type", sa.String(length=50), nullable=False),
        sa.Column("official_number", sa.String(length=50), nullable=True),
        sa.Column("enactment_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_acts")),
        sa.UniqueConstraint("short_name", name=op.f("uq_legal_acts_short_name")),
    )
    op.create_index(
        op.f("ix_legal_acts_short_name"),
        "legal_acts",
        ["short_name"],
        unique=True,
    )

    op.create_table(
        "legal_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("legal_act_id", sa.UUID(), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=False),
        sa.Column("version_label", sa.String(length=100), nullable=False),
        sa.Column(
            "parsed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "is_active_for_query",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["legal_act_id"],
            ["legal_acts.id"],
            name=op.f("fk_legal_versions_legal_act_id_legal_acts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_documents.id"],
            name=op.f("fk_legal_versions_source_document_id_source_documents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_versions")),
    )

    op.create_table(
        "legal_elements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("legal_version_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("element_type", sa.String(length=50), nullable=False),
        sa.Column("number_label", sa.String(length=100), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column(
            "is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("path", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["legal_version_id"],
            ["legal_versions.id"],
            name=op.f("fk_legal_elements_legal_version_id_legal_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["legal_elements.id"],
            name=op.f("fk_legal_elements_parent_id_legal_elements"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_elements")),
        sa.CheckConstraint(
            "parent_id <> id", name=op.f("ck_legal_elements_no_self_parent")
        ),
    )
    op.create_index(
        op.f("ix_legal_elements_parent_id"),
        "legal_elements",
        ["parent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legal_elements_legal_version_id"),
        "legal_elements",
        ["legal_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_legal_elements_path"),
        "legal_elements",
        ["path"],
        unique=False,
    )

    # 4. Criar tabelas de indexação (chunks, chunk_legal_elements, embeddings)
    op.create_table(
        "chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("legal_version_id", sa.UUID(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("strategy_name", sa.String(length=100), nullable=True),
        sa.Column("tsv_content", postgresql.TSVECTOR(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["legal_version_id"],
            ["legal_versions.id"],
            name=op.f("fk_chunks_legal_version_id_legal_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chunks")),
    )
    op.create_index(
        op.f("ix_chunks_legal_version_id"),
        "chunks",
        ["legal_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_chunks_tsv_content",
        "chunks",
        ["tsv_content"],
        postgresql_using="gin",
    )

    op.create_table(
        "chunk_legal_elements",
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("legal_element_id", sa.UUID(), nullable=False),
        sa.Column(
            "is_primary", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["chunks.id"],
            name=op.f("fk_chunk_legal_elements_chunk_id_chunks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["legal_element_id"],
            ["legal_elements.id"],
            name=op.f("fk_chunk_legal_elements_legal_element_id_legal_elements"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "chunk_id", "legal_element_id", name=op.f("pk_chunk_legal_elements")
        ),
    )

    op.create_table(
        "embeddings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column(
            "model_version", sa.String(length=50), server_default="v1", nullable=False
        ),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("vector", Vector(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["chunks.id"],
            name=op.f("fk_embeddings_chunk_id_chunks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_embeddings")),
        sa.UniqueConstraint(
            "chunk_id",
            "provider_name",
            "model_name",
            "model_version",
            name=op.f("uq_embeddings_chunk_id"),
        ),
        sa.CheckConstraint(
            "dimensions > 0", name=op.f("ck_embeddings_dimensions_positive")
        ),
    )
    op.create_index(
        op.f("ix_embeddings_chunk_id"),
        "embeddings",
        ["chunk_id"],
        unique=False,
    )

    # 5. Criar tabelas de evidência (evidence_sets, evidence_items)
    op.create_table(
        "evidence_sets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("retrieval_strategy", sa.String(length=100), nullable=False),
        sa.Column("validation_status", sa.String(length=50), nullable=False),
        sa.Column("total_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_sets")),
    )

    op.create_table(
        "evidence_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("evidence_set_id", sa.UUID(), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("legal_element_id", sa.UUID(), nullable=False),
        sa.Column("evidence_code", sa.String(length=50), nullable=False),
        sa.Column("citation_label", sa.String(length=255), nullable=False),
        sa.Column("text_snapshot", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column(
            "is_validated",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "validation_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["chunks.id"],
            name=op.f("fk_evidence_items_chunk_id_chunks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_set_id"],
            ["evidence_sets.id"],
            name=op.f("fk_evidence_items_evidence_set_id_evidence_sets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["legal_element_id"],
            ["legal_elements.id"],
            name=op.f("fk_evidence_items_legal_element_id_legal_elements"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_items")),
        sa.UniqueConstraint(
            "evidence_set_id",
            "evidence_code",
            name=op.f("uq_evidence_items_evidence_set_id"),
        ),
    )

    # 6. Criar tabelas de afirmações e citações (claims, citations)
    op.create_table(
        "claims",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_code", sa.String(length=50), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_claims")),
    )

    op.create_table(
        "citations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("evidence_item_id", sa.UUID(), nullable=False),
        sa.Column("evidence_set_id", sa.UUID(), nullable=False),
        sa.Column(
            "is_valid", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("validation_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["claims.id"],
            name=op.f("fk_citations_claim_id_claims"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_item_id"],
            ["evidence_items.id"],
            name=op.f("fk_citations_evidence_item_id_evidence_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_set_id"],
            ["evidence_sets.id"],
            name=op.f("fk_citations_evidence_set_id_evidence_sets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_citations")),
    )


def downgrade() -> None:
    # Removendo em ordem reversa às dependências
    op.drop_table("citations")
    op.drop_table("claims")
    op.drop_table("evidence_items")
    op.drop_table("evidence_sets")
    op.drop_table("embeddings")
    op.drop_table("chunk_legal_elements")
    op.drop_table("chunks")
    op.drop_table("legal_elements")
    op.drop_table("legal_versions")
    op.drop_table("legal_acts")
    op.drop_table("source_documents")
    op.drop_table("sources")
    op.execute("DROP EXTENSION IF EXISTS vector CASCADE;")
