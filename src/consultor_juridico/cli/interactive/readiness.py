"""Leitura leve e sem efeitos colaterais da prontidão do MVP2."""

import httpx
from alembic.script import ScriptDirectory
from sqlalchemy import func, select

from consultor_juridico.application.corpus.audit import CorpusAuditor, list_versions
from consultor_juridico.application.corpus.catalog import LEI_9784_ACT, LEI_9784_SOURCE
from consultor_juridico.application.corpus.parser import PlanaltoLeiParser
from consultor_juridico.application.corpus.projection import ProvisionTextProjection
from consultor_juridico.config import settings
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.evaluation.selected_answerer import (
    SELECTED_MODEL,
    SELECTED_MODEL_DIGEST,
)
from consultor_juridico.infrastructure.corpus.models import (
    LegalActModel,
    SearchUnitModel,
)
from consultor_juridico.services.bootstrap import BootstrapReadiness
from consultor_juridico.services.db_service import check_db_status, get_alembic_config


def _ollama_status() -> tuple[bool, bool]:
    try:
        response = httpx.get(
            f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=2.0
        )
        response.raise_for_status()
        models = response.json().get("models", [])
    except (httpx.HTTPError, ValueError, TypeError):
        return False, False
    selected = next(
        (
            item
            for item in models
            if SELECTED_MODEL in {item.get("name"), item.get("model")}
        ),
        None,
    )
    return True, bool(selected and selected.get("digest") == SELECTED_MODEL_DIGEST)


def check_readiness() -> BootstrapReadiness:
    """Confere schema, corpus auditável, SearchUnits e modelo congelado."""
    db = check_db_status()
    database = bool(db.get("connected"))
    head = ScriptDirectory.from_config(get_alembic_config()).get_current_head()
    migrations = database and db.get("alembic_version") == head
    corpus = retrieval = False
    if migrations:
        try:
            with SessionLocal() as session:
                act = session.scalar(
                    select(LegalActModel).where(
                        LegalActModel.act_code == LEI_9784_ACT.act_code
                    )
                )
                matching = [
                    row
                    for row in list_versions(session)
                    if row["act_code"] == LEI_9784_ACT.act_code
                ]
                if act is not None and matching:
                    current = matching[-1]
                    corpus = (
                        CorpusAuditor(
                            session, PlanaltoLeiParser(), ProvisionTextProjection()
                        )
                        .audit(
                            str(current["version_hash"]),
                            encoding=LEI_9784_SOURCE.encoding,
                        )
                        .passed
                    )
                    retrieval = bool(
                        session.scalar(
                            select(func.count())
                            .select_from(SearchUnitModel)
                            .where(
                                SearchUnitModel.act_version_id
                                == current["act_version_id"]
                            )
                        )
                    )
        except Exception:
            corpus = retrieval = False
    ollama, model = _ollama_status()
    return BootstrapReadiness(database, migrations, corpus, retrieval, ollama, model)
