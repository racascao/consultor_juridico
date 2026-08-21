"""Orquestração da consulta fundamentada e persistência auditável."""

import hashlib
from collections.abc import Callable

from sqlalchemy.orm import Session

from consultor_juridico.consultation.errors import LLMResponseError
from consultor_juridico.consultation.evidence import build_evidence_set
from consultor_juridico.consultation.llm import OllamaLegalGenerator
from consultor_juridico.consultation.selection import select_evidence_candidates
from consultor_juridico.consultation.semantic import SemanticSupportValidator
from consultor_juridico.consultation.sufficiency import assess_evidence_sufficiency
from consultor_juridico.consultation.types import (
    CitationReference,
    ConsultationOutcome,
    ConsultationResult,
    GeneratedResponse,
)
from consultor_juridico.consultation.validator import validate_citations
from consultor_juridico.models import Citation, Claim
from consultor_juridico.retrieval import RetrievalCandidate

Retriever = Callable[[str], tuple[RetrievalCandidate, ...]]

ABSTENTION = (
    "Não há evidência constitucional oficial suficiente no corpus consultado "
    "para responder com segurança."
)


def run_consultation(
    session: Session,
    question: str,
    *,
    retriever: Retriever,
    generator: OllamaLegalGenerator,
    model_name: str,
    semantic_validator: SemanticSupportValidator,
    max_generation_attempts: int = 2,
    evidence_limit: int = 3,
) -> ConsultationResult:
    if not question.strip():
        raise ValueError("A pergunta não pode ser vazia.")
    retrieved = retriever(question)
    candidates = select_evidence_candidates(
        retrieved, limit=evidence_limit, question=question
    )
    sufficiency = assess_evidence_sufficiency(question, candidates)
    evidence_set = build_evidence_set(
        session,
        question,
        candidates,
        retrieval_metadata={
            "retrieved_candidate_count": len(retrieved),
            "selected_candidate_count": len(candidates),
            "removed_by_selection": len(retrieved) - len(candidates),
            "model": model_name,
            "sufficiency": {
                "decision": sufficiency.decision.value,
                "reasons": list(sufficiency.reasons),
                "lexical_score": sufficiency.lexical_score,
                "vector_score": sufficiency.vector_score,
                "retriever_agreement": sufficiency.retriever_agreement,
            },
        },
    )
    if not sufficiency.is_sufficient:
        evidence_set.validation_status = "INSUFFICIENT_EVIDENCE"
    session.commit()
    session.refresh(evidence_set)
    if not sufficiency.is_sufficient or not evidence_set.items:
        return ConsultationResult(
            ConsultationOutcome.ABSTAINED,
            evidence_set.id,
            ABSTENTION,
            (),
            (),
            sufficiency=sufficiency,
        )

    errors: tuple[str, ...] = ()
    response: GeneratedResponse | None = None
    for _attempt in range(max_generation_attempts):
        try:
            response = generator.generate(
                question, tuple(evidence_set.items), correction=errors
            )
        except LLMResponseError as exc:
            errors = (str(exc),)
            continue
        report = validate_citations(session, evidence_set, response)
        if report.is_valid:
            if response.abstain:
                evidence_set.validation_status = "ABSTAINED"
                evidence_set.metadata_json = {
                    **(evidence_set.metadata_json or {}),
                    "answer": response.answer,
                    "generation_attempts": _attempt + 1,
                }
                session.commit()
                return ConsultationResult(
                    ConsultationOutcome.ABSTAINED,
                    evidence_set.id,
                    response.answer or ABSTENTION,
                    (),
                    (),
                    sufficiency=sufficiency,
                )
            semantic = semantic_validator.validate(response, tuple(evidence_set.items))
            if semantic.is_valid:
                return _persist_valid_response(
                    session,
                    evidence_set,
                    response,
                    model_name,
                    _attempt + 1,
                    sufficiency,
                    semantic,
                )
            errors = semantic.errors
            continue
        errors = report.errors

    evidence_set.validation_status = "VALIDATION_FAILED"
    evidence_set.metadata_json = {
        **(evidence_set.metadata_json or {}),
        "validation_errors": list(errors),
        "generation_attempts": max_generation_attempts,
    }
    session.commit()
    return ConsultationResult(
        ConsultationOutcome.ABSTAINED,
        evidence_set.id,
        ABSTENTION,
        (),
        (),
        errors,
        sufficiency,
    )


def _persist_valid_response(
    session: Session,
    evidence_set,
    response: GeneratedResponse,
    model_name: str,
    attempts: int,
    sufficiency,
    semantic_support,
) -> ConsultationResult:
    items = {item.evidence_code: item for item in evidence_set.items}
    citation_pairs = []
    rendered_claims = []
    for generated in response.claims:
        claim = Claim(claim_code=generated.claim_code, text=generated.text)
        session.add(claim)
        session.flush()
        for evidence_code in generated.evidence_codes:
            item = items[evidence_code]
            session.add(
                Citation(
                    claim_id=claim.id,
                    evidence_item_id=item.id,
                    evidence_set_id=evidence_set.id,
                    is_valid=True,
                    validation_notes="Cadeia e snapshot validados deterministicamente.",
                )
            )
            citation_pairs.append(
                CitationReference(
                    generated.claim_code,
                    evidence_code,
                    item.citation_label,
                    item.source_url or "",
                )
            )
        rendered_claims.append(
            f"{generated.text} [{', '.join(generated.evidence_codes)}]"
        )
    final_answer = "\n\n".join(rendered_claims)
    evidence_set.validation_status = "VALIDATED"
    evidence_set.metadata_json = {
        **(evidence_set.metadata_json or {}),
        "answer": final_answer,
        "raw_llm_answer": response.answer,
        "answer_sha256": hashlib.sha256(final_answer.encode()).hexdigest(),
        "llm_model": model_name,
        "generation_attempts": attempts,
        "semantic_support": [
            {
                "claim_code": item.claim_code,
                "status": item.status.value,
                "evidence_codes": list(item.evidence_codes),
                "reason": item.reason,
            }
            for item in semantic_support.claims
        ],
    }
    session.commit()
    return ConsultationResult(
        ConsultationOutcome.ANSWERED,
        evidence_set.id,
        final_answer,
        response.claims,
        tuple(citation_pairs),
        sufficiency=sufficiency,
        semantic_support=semantic_support,
    )
