"""Schema corrections: rename constraints, remove redundant indexes, add composite FK

Revision ID: 002_schema_corrections
Revises: 001_initial_schema
Create Date: 2026-08-14 19:00:00.000000

Changes:
- Rename uq_embedding_chunk_model
  → uq_embeddings_chunk_provider_model_version
- ck_embeddings_dimensions_positive (already correct, no rename needed)
- Add ck_embeddings_vector_dimensions_match
  CHECK (vector IS NULL OR dimensions = vector_dims(vector))
- Remove redundant index ix_source_documents_content_hash_sha256
- Remove redundant index ix_legal_acts_short_name
- Add uq_evidence_items_id_evidence_set UNIQUE(id, evidence_set_id)
- Drop simple FK fk_citations_evidence_item_id_evidence_items
- Add composite FK fk_citations_evidence_item_set_composite
  (evidence_item_id, evidence_set_id)
  → evidence_items(id, evidence_set_id) ON DELETE RESTRICT

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_schema_corrections"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Renomear constraint de unicidade de embeddings
    op.execute(
        "ALTER TABLE embeddings RENAME CONSTRAINT "
        '"uq_embeddings_chunk_id" TO "uq_embeddings_chunk_provider_model_version";'
    )

    # 2. O nome ck_embeddings_dimensions_positive já é o nome correto no banco.
    #    Não há necessidade de renomear.

    # 3. Adicionar CHECK constraint: dimensões do vetor devem bater com o vetor real
    op.execute(
        "ALTER TABLE embeddings ADD CONSTRAINT ck_embeddings_vector_dimensions_match "
        "CHECK (vector IS NULL OR dimensions = vector_dims(vector));"
    )

    # 4. Remover índice único redundante em source_documents
    #    (UniqueConstraint uq_source_documents_content_hash_sha256 já cobre)
    op.drop_index(
        "ix_source_documents_content_hash_sha256",
        table_name="source_documents",
        if_exists=True,
    )

    # 5. Remover índice único redundante em legal_acts
    #    (a UniqueConstraint uq_legal_acts_short_name já cobre a unicidade)
    op.drop_index(
        "ix_legal_acts_short_name",
        table_name="legal_acts",
        if_exists=True,
    )

    # 6. Adicionar constraint única composta em evidence_items (id, evidence_set_id)
    #    necessária para que Citation possa referenciar este par via FK composta
    op.create_unique_constraint(
        "uq_evidence_items_id_evidence_set",
        "evidence_items",
        ["id", "evidence_set_id"],
    )

    # 7. Remover a FK simples de citations → evidence_items
    op.drop_constraint(
        "fk_citations_evidence_item_id_evidence_items",
        "citations",
        type_="foreignkey",
    )

    # 8. Criar FK composta de citations → evidence_items(id, evidence_set_id)
    #    Garante fisicamente que Citation.evidence_set_id coincide com o
    #    EvidenceSet ao qual o EvidenceItem pertence.
    op.create_foreign_key(
        "fk_citations_evidence_item_set_composite",
        "citations",
        "evidence_items",
        ["evidence_item_id", "evidence_set_id"],
        ["id", "evidence_set_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # 8. Remover FK composta
    op.drop_constraint(
        "fk_citations_evidence_item_set_composite",
        "citations",
        type_="foreignkey",
    )

    # 7. Restaurar FK simples de citations → evidence_items
    op.create_foreign_key(
        "fk_citations_evidence_item_id_evidence_items",
        "citations",
        "evidence_items",
        ["evidence_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 6. Remover constraint única composta em evidence_items
    op.drop_constraint(
        "uq_evidence_items_id_evidence_set",
        "evidence_items",
        type_="unique",
    )

    # 5. Restaurar índice único em legal_acts
    op.create_index(
        "ix_legal_acts_short_name",
        "legal_acts",
        ["short_name"],
        unique=True,
    )

    # 4. Restaurar índice único em source_documents
    op.create_index(
        "ix_source_documents_content_hash_sha256",
        "source_documents",
        ["content_hash_sha256"],
        unique=True,
    )

    # 3. Remover CHECK constraint de dimensões do vetor
    op.execute(
        "ALTER TABLE embeddings DROP CONSTRAINT IF EXISTS"
        " ck_embeddings_vector_dimensions_match;"
    )

    # 1. Restaurar nome original da constraint de unicidade de embeddings
    op.execute(
        "ALTER TABLE embeddings RENAME CONSTRAINT "
        '"uq_embeddings_chunk_provider_model_version" TO "uq_embeddings_chunk_id";'
    )
