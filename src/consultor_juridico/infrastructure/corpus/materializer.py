"""Materialização transacional e idempotente do corpus."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from consultor_juridico.application.corpus.ports import MaterializationResult
from consultor_juridico.domain.corpus import (
    LegalActIdentity,
    ParsedDocument,
    ProjectedSearchUnit,
    SnapshotData,
    VersionIdentity,
)
from consultor_juridico.infrastructure.corpus.models import (
    ActVersionModel,
    LegalActModel,
    ProvisionModel,
    SearchUnitModel,
    SearchUnitProvisionModel,
)


class SqlAlchemyCorpusMaterializer:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def materialize(
        self,
        *,
        act: LegalActIdentity,
        snapshot: SnapshotData,
        identity: VersionIdentity,
        parsed: ParsedDocument,
        projected: tuple[ProjectedSearchUnit, ...],
    ) -> MaterializationResult:
        self._validate(parsed, projected)
        with self._session_factory() as session, session.begin():
            existing = session.scalar(
                select(ActVersionModel).where(
                    ActVersionModel.version_hash == identity.version_hash
                )
            )
            if existing:
                return self._result(session, existing, created=False)
            legal_act = session.scalar(
                select(LegalActModel).where(LegalActModel.act_code == act.act_code)
            )
            if legal_act is None:
                legal_act = LegalActModel(
                    act_code=act.act_code,
                    jurisdiction=act.jurisdiction,
                    act_type=act.act_type,
                    number=act.number,
                    year=act.year,
                    title=act.title,
                )
                session.add(legal_act)
                session.flush()
            version = ActVersionModel(
                legal_act_id=legal_act.id,
                source_snapshot_id=snapshot.id,
                parser_name=identity.parser_name,
                parser_version=identity.parser_version,
                projection_name=identity.projection_name,
                projection_version=identity.projection_version,
                version_hash=identity.version_hash,
            )
            session.add(version)
            session.flush()
            provision_ids = {}
            for item in parsed.provisions:
                parent_id = provision_ids.get(item.parent_stable_key)
                model = ProvisionModel(
                    act_version_id=version.id,
                    stable_key=item.stable_key,
                    provision_type=item.provision_type.value,
                    number_label=item.number_label,
                    parent_id=parent_id,
                    document_order=item.document_order,
                    citation_text=item.citation_text,
                    source_locator=item.source_locator.as_dict(),
                    content_hash=item.content_hash,
                    legal_status=item.legal_status.value,
                )
                session.add(model)
                session.flush()
                provision_ids[item.stable_key] = model.id
            for item in projected:
                unit = SearchUnitModel(
                    act_version_id=version.id,
                    unit_key=item.unit_key,
                    search_text=item.search_text,
                    content_hash=item.content_hash,
                )
                session.add(unit)
                session.flush()
                for position, stable_key in enumerate(item.provision_stable_keys):
                    session.add(
                        SearchUnitProvisionModel(
                            search_unit_id=unit.id,
                            provision_id=provision_ids[stable_key],
                            position=position,
                        )
                    )
            session.flush()
            return MaterializationResult(
                version.id,
                version.version_hash,
                len(parsed.provisions),
                len(projected),
                created=True,
            )

    @staticmethod
    def _validate(
        parsed: ParsedDocument, projected: tuple[ProjectedSearchUnit, ...]
    ) -> None:
        keys = {item.stable_key for item in parsed.provisions}
        if len(keys) != len(parsed.provisions):
            raise ValueError("stable_key duplicada na árvore em memória")
        orders = {item.document_order for item in parsed.provisions}
        if len(orders) != len(parsed.provisions):
            raise ValueError("document_order duplicada na árvore em memória")
        if any(
            item.parent_stable_key is not None and item.parent_stable_key not in keys
            for item in parsed.provisions
        ):
            raise ValueError("parent_stable_key inexistente")
        if any(
            key not in keys for unit in projected for key in unit.provision_stable_keys
        ):
            raise ValueError("SearchUnit referencia Provision inexistente")

    @staticmethod
    def _result(
        session: Session, version: ActVersionModel, *, created: bool
    ) -> MaterializationResult:
        provisions = int(
            session.scalar(
                select(func.count())
                .select_from(ProvisionModel)
                .where(ProvisionModel.act_version_id == version.id)
            )
            or 0
        )
        units = int(
            session.scalar(
                select(func.count())
                .select_from(SearchUnitModel)
                .where(SearchUnitModel.act_version_id == version.id)
            )
            or 0
        )
        return MaterializationResult(
            version.id, version.version_hash, provisions, units, created
        )
