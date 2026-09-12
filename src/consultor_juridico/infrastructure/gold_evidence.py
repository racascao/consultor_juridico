"""Leitura SQLAlchemy de Provisions para Gold Evidence explícita."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from consultor_juridico.application.gold_evidence.types import (
    GoldEvidenceContext,
    GoldEvidenceItem,
)
from consultor_juridico.infrastructure.corpus.models import (
    ActVersionModel,
    LegalActModel,
    ProvisionModel,
    SourceModel,
    SourceSnapshotModel,
)


class SqlAlchemyGoldEvidenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def context(self, version_hash: str) -> GoldEvidenceContext:
        row = self._session.execute(
            select(
                LegalActModel.act_code,
                ActVersionModel.version_hash,
                SourceSnapshotModel.sha256,
                SourceModel.official_url,
            )
            .join(
                LegalActModel,
                LegalActModel.id == ActVersionModel.legal_act_id,
            )
            .join(
                SourceSnapshotModel,
                SourceSnapshotModel.id == ActVersionModel.source_snapshot_id,
            )
            .join(SourceModel, SourceModel.id == SourceSnapshotModel.source_id)
            .where(ActVersionModel.version_hash == version_hash)
        ).one_or_none()
        if row is None:
            raise LookupError(f"ActVersion não encontrada: {version_hash}")
        return GoldEvidenceContext(
            legal_act_code=row.act_code,
            version_hash=row.version_hash,
            source_snapshot_sha256=row.sha256,
            official_url=row.official_url,
        )

    def materialize(
        self, version_hash: str, stable_keys: tuple[str, ...]
    ) -> tuple[GoldEvidenceItem, ...]:
        context = self.context(version_hash)
        if not stable_keys:
            return ()
        rows = self._session.execute(
            select(
                ProvisionModel.stable_key,
                ProvisionModel.provision_type,
                ProvisionModel.citation_text,
                ProvisionModel.source_locator,
                ProvisionModel.document_order,
            )
            .join(
                ActVersionModel,
                ActVersionModel.id == ProvisionModel.act_version_id,
            )
            .where(
                ActVersionModel.version_hash == version_hash,
                ProvisionModel.stable_key.in_(stable_keys),
            )
            .order_by(ProvisionModel.document_order.asc())
        )
        return tuple(
            GoldEvidenceItem(
                stable_key=row.stable_key,
                provision_type=row.provision_type,
                citation_text=row.citation_text or "",
                source_locator=dict(row.source_locator),
                source_snapshot_sha256=context.source_snapshot_sha256,
                official_url=context.official_url,
                document_order=row.document_order,
            )
            for row in rows
        )

    def provision_keys(self, version_hash: str) -> frozenset[str]:
        return frozenset(
            self._session.scalars(
                select(ProvisionModel.stable_key)
                .join(
                    ActVersionModel,
                    ActVersionModel.id == ProvisionModel.act_version_id,
                )
                .where(ActVersionModel.version_hash == version_hash)
            )
        )

    def validate_citation_namespace(self, citations: frozenset[str]) -> None:
        """O PostgreSQL possui o namespace integral da ActVersion."""
