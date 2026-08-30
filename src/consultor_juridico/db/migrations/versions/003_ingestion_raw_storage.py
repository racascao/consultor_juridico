"""Store canonical source payloads as bytes and scope hashes by source.

Revision ID: 003_ingestion_raw_storage
Revises: 002_schema_corrections
Create Date: 2026-08-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "003_ingestion_raw_storage"
down_revision: str | None = "002_schema_corrections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adapta o schema documental para preservação binária e proveniência."""
    op.drop_constraint(
        "uq_source_documents_content_hash_sha256",
        "source_documents",
        type_="unique",
    )
    op.alter_column(
        "source_documents",
        "raw_content",
        new_column_name="raw_bytes",
    )
    # O banco estava vazio no checkpoint. Para instalações com dados textuais,
    # convert_to preserva os bytes da representação UTF-8 existente.
    op.execute(
        "ALTER TABLE source_documents ALTER COLUMN raw_bytes TYPE BYTEA "
        "USING convert_to(raw_bytes, 'UTF8')"
    )
    op.create_unique_constraint(
        "uq_source_documents_source_hash",
        "source_documents",
        ["source_id", "content_hash_sha256"],
    )
    op.create_unique_constraint(
        "uq_sources_base_url",
        "sources",
        ["base_url"],
    )


def downgrade() -> None:
    """Restaura TEXT somente se todos os bytes armazenados forem UTF-8 válidos.

    ``convert_from`` falha de forma explícita diante de bytes arbitrários que não
    sejam UTF-8. Isso evita substituição, perda ou conversão silenciosa de dados.
    """
    op.drop_constraint("uq_sources_base_url", "sources", type_="unique")
    op.drop_constraint(
        "uq_source_documents_source_hash",
        "source_documents",
        type_="unique",
    )
    op.execute(
        "ALTER TABLE source_documents ALTER COLUMN raw_bytes TYPE TEXT "
        "USING convert_from(raw_bytes, 'UTF8')"
    )
    op.alter_column(
        "source_documents",
        "raw_bytes",
        new_column_name="raw_content",
    )
    op.create_unique_constraint(
        "uq_source_documents_content_hash_sha256",
        "source_documents",
        ["content_hash_sha256"],
    )
