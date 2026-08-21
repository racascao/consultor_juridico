"""Integração opt-in da consulta local completa, sem acesso à internet."""

import os

import pytest
from sqlalchemy import select

from consultor_juridico.config import settings
from consultor_juridico.consultation import (
    ConsultationOutcome,
    OllamaLegalGenerator,
    OllamaSemanticSupportValidator,
    run_consultation,
)
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.models import Citation, Claim, EvidenceSet
from consultor_juridico.retrieval import (
    OllamaEmbeddingProvider,
    RetrievalFilters,
    hybrid_search,
)

pytestmark = [
    pytest.mark.consultation_integration,
    pytest.mark.skipif(
        os.getenv("RUN_CONSULTATION_INTEGRATION") != "1",
        reason="integração local de consulta é opt-in",
    ),
]


def test_local_consultation_persists_a_valid_traceability_chain():
    provider = OllamaEmbeddingProvider(
        settings.ollama_base_url, settings.embedding_model, settings.embedding_timeout
    )
    generator = OllamaLegalGenerator(
        settings.ollama_base_url,
        settings.ollama_model,
        settings.consultation_timeout,
        settings.consultation_max_tokens,
    )
    semantic_validator = OllamaSemanticSupportValidator(
        settings.ollama_base_url,
        settings.ollama_model,
        settings.consultation_timeout,
    )
    with SessionLocal() as session:
        result = run_consultation(
            session,
            "O que a Constituição estabelece sobre a manifestação do pensamento?",
            retriever=lambda query: hybrid_search(
                session,
                query,
                provider,
                model_name=settings.embedding_model,
                limit=5,
                filters=RetrievalFilters(act="CF/88"),
            ),
            generator=generator,
            model_name=settings.ollama_model,
            semantic_validator=semantic_validator,
        )
        assert result.outcome is ConsultationOutcome.ANSWERED
        evidence_set = session.get(EvidenceSet, result.evidence_set_id)
        assert evidence_set is not None
        assert evidence_set.validation_status == "VALIDATED"
        assert evidence_set.total_items == len(evidence_set.items) > 0
        citations = session.scalars(
            select(Citation).where(Citation.evidence_set_id == evidence_set.id)
        ).all()
        assert citations and all(citation.is_valid for citation in citations)
        claim_ids = {citation.claim_id for citation in citations}
        assert len(session.scalars(select(Claim).where(Claim.id.in_(claim_ids))).all())
        assert all(
            item.source_url and item.text_snapshot for item in evidence_set.items
        )
