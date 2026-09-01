"""Índice GIN do baseline lexical PostgreSQL FTS.

Revision ID: 002_v02_postgresql_fts
Revises: 001_v02_foundation_corpus
"""

from collections.abc import Sequence

from alembic import op

revision: str = "002_v02_postgresql_fts"
down_revision: str | None = "001_v02_foundation_corpus"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX ix_search_units_fts_portuguese
        ON search_units
        USING gin (to_tsvector('portuguese'::regconfig, search_text))
        """
    )


def downgrade() -> None:
    op.drop_index("ix_search_units_fts_portuguese", table_name="search_units")
