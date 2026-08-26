"""Avaliação end-to-end para dataset real-world-short."""

import time
from typing import Any

from sqlalchemy.orm import Session

from consultor_juridico.consultation import (
    OllamaSemanticSupportValidator,
)
from consultor_juridico.consultation.llm import LegalGenerator
from consultor_juridico.consultation.selection import (
    select_evidence_candidates_with_diagnostics,
)
from consultor_juridico.consultation.sufficiency import assess_evidence_sufficiency
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.evaluation.target_fidelity import assess_target_fidelity
from consultor_juridico.evaluation.types import EvaluationCase
from consultor_juridico.models import EvidenceSet
from consultor_juridico.retrieval import (
    RetrievalCandidate,
    hybrid_search,
    lexical_search,
    vector_search,
)
from consultor_juridico.retrieval.embeddings import OllamaEmbeddingProvider


def _rank_of(candidates: tuple[RetrievalCandidate, ...], identity: str) -> int | None:
    for idx, cand in enumerate(candidates, start=1):
        if cand.identity_key == identity:
            return idx
    return None


def evaluate_real_world_case(
    session: Session,
    case: EvaluationCase,
    provider: OllamaEmbeddingProvider,
    generator: LegalGenerator,
    semantic_validator: OllamaSemanticSupportValidator,
    model_name: str,
    embedding_model: str,
) -> dict[str, Any]:
    started_total = time.perf_counter()
    # Retrieval
    lexical = lexical_search(session, case.question, limit=10)
    vector = vector_search(
        session, case.question, provider, model_name=embedding_model, limit=10
    )
    hybrid = hybrid_search(
        session, case.question, provider, model_name=embedding_model, limit=10
    )
    # Ranks for expected
    relevant = set(case.expected_provisions + case.acceptable_provisions)
    retrieval_ranks = {}
    for prov in relevant:
        retrieval_ranks[prov] = {
            "lexical": _rank_of(lexical, prov),
            "vector": _rank_of(vector, prov),
            "hybrid": _rank_of(hybrid, prov),
        }
    # Also check hybrid top10 hit
    ranked_hybrid_ids = tuple(c.identity_key for c in hybrid)
    hit = any(p in ranked_hybrid_ids for p in relevant) if case.expect_answer else None

    # Evidence selection (using hybrid as retriever, limit top_k)
    from consultor_juridico.config import settings

    # Re-run hybrid with consultation_top_k limit to simulate service
    retrieved_for_selection = hybrid_search(
        session,
        case.question,
        provider,
        model_name=embedding_model,
        limit=settings.consultation_top_k,
    )
    selection = select_evidence_candidates_with_diagnostics(
        retrieved_for_selection,
        limit=settings.consultation_evidence_limit,
        question=case.question,
    )
    selected = selection.candidates
    suff = assess_evidence_sufficiency(case.question, selected)

    # Build evidence set (to get items) if sufficient
    # We need to actually run the full pipeline via run_consultation for final outcome,
    # but we also want to record intermediate.
    from consultor_juridico.consultation.service import run_consultation

    # Need to run with same retrieved_for_selection via custom retriever
    # Use the same provider and settings
    final_result = run_consultation(
        session,
        case.question,
        retriever=lambda q: hybrid_search(
            session,
            q,
            provider,
            model_name=embedding_model,
            limit=settings.consultation_top_k,
        ),
        generator=generator,
        model_name=model_name,
        semantic_validator=semantic_validator,
        max_generation_attempts=settings.consultation_max_attempts,
        evidence_limit=settings.consultation_evidence_limit,
    )

    evidence_set = session.get(EvidenceSet, final_result.evidence_set_id)
    evidence_by_code = (
        {item.evidence_code: item for item in evidence_set.items}
        if evidence_set
        else {}
    )
    cited_codes = tuple(
        code for claim in final_result.claims for code in claim.evidence_codes
    )
    used_identity_keys = tuple(
        str((evidence_by_code[code].validation_metadata or {}).get("identity_key", ""))
        for code in cited_codes
        if code in evidence_by_code
    )
    target_fidelity = assess_target_fidelity(case, used_identity_keys)

    # Determine classification
    # CORRECT_ANSWER: expect True + ANSWERED + valid citations
    # CORRECT_ABSTENTION: expect False + ABSTAINED
    # FALSE_ABSTENTION: expect True + ABSTAINED
    # UNSAFE_ANSWER: expect False + ANSWERED
    outcome = final_result.outcome.value
    expect = case.expect_answer
    if expect and outcome == "ANSWERED":
        classification = "CORRECT_ANSWER" if target_fidelity.passed else "WRONG_TARGET"
    elif not expect and outcome == "ABSTAINED":
        classification = "CORRECT_ABSTENTION"
    elif expect and outcome == "ABSTAINED":
        classification = "FALSE_ABSTENTION"
    elif not expect and outcome == "ANSWERED":
        classification = "UNSAFE_ANSWER"
    else:
        classification = "TECHNICAL_FAILURE"

    # Determine failure stage
    failure_stage = None
    if classification == "WRONG_TARGET":
        failure_stage = "TARGET_FIDELITY"
    if classification == "FALSE_ABSTENTION":
        if not hit:
            failure_stage = "RETRIEVAL_MISS"
        elif not selected or not any(c.identity_key in relevant for c in selected):
            failure_stage = "EVIDENCE_SELECTION_MISS"
        elif not suff.is_sufficient:
            failure_stage = "SUFFICIENCY_FALSE_NEGATIVE"
        elif final_result.validation_errors and "PARTIALLY" in str(
            final_result.validation_errors
        ):
            failure_stage = "SEMANTIC_FALSE_NEGATIVE"
        elif final_result.validation_errors:
            # Could be citation or generation
            if "Citação" in str(final_result.validation_errors) or "Citation" in str(
                final_result.validation_errors
            ):
                failure_stage = "CITATION_FAILURE"
            else:
                failure_stage = final_result.validation_stage or "VALIDATION_ABSTENTION"
        else:
            failure_stage = final_result.validation_stage or "EBCG_CONSTRUCTION"

    # Build detailed record
    elapsed = time.perf_counter() - started_total
    return {
        "case_id": case.id,
        "question": case.question,
        "expect_answer": case.expect_answer,
        "expected_provisions": list(case.expected_provisions),
        "acceptable_provisions": list(case.acceptable_provisions),
        "retrieval": {
            "lexical_top": [
                {
                    "identity_key": c.identity_key,
                    "rank": c.lexical_rank,
                    "score": c.lexical_score,
                }
                for c in lexical[:5]
            ],
            "vector_top": [
                {
                    "identity_key": c.identity_key,
                    "rank": c.vector_rank,
                    "score": c.vector_score,
                }
                for c in vector[:5]
            ],
            "hybrid_top": [
                {
                    "identity_key": c.identity_key,
                    "rrf": c.rrf_score,
                    "lex_rank": c.lexical_rank,
                    "vec_rank": c.vector_rank,
                }
                for c in hybrid[:10]
            ],
            "ranks": retrieval_ranks,
            "hit": hit,
        },
        "evidence_selection": {
            "received": len(retrieved_for_selection),
            "selected": len(selected),
            "items": [
                {
                    "identity_key": c.identity_key,
                    "element_type": c.element_type,
                    "lexical_rank": c.lexical_rank,
                    "vector_rank": c.vector_rank,
                    "rrf": c.rrf_score,
                }
                for c in selected
            ],
            "diagnostics": [
                {
                    "identity_key": item.identity_key,
                    "base_relevance": item.base_relevance,
                    "query_coverage": item.query_coverage,
                    "marginal_coverage": item.marginal_coverage,
                    "redundancy": item.redundancy,
                    "final_score": item.final_score,
                    "selected_position": item.selected_position,
                    "decision_reason": item.decision_reason,
                }
                for item in selection.diagnostics
            ],
        },
        "sufficiency": {
            "decision": suff.decision.value,
            "is_sufficient": suff.is_sufficient,
            "reasons": list(suff.reasons),
            "lexical_score": suff.lexical_score,
            "vector_score": suff.vector_score,
        },
        "generation": {
            "outcome": outcome,
            "claims": [
                {"code": c.claim_code, "text": c.text, "ev": list(c.evidence_codes)}
                for c in final_result.claims
            ],
            "citations": [
                {"code": c.evidence_code, "label": c.citation_label}
                for c in final_result.citations
            ],
            "validation_errors": list(final_result.validation_errors),
            "evidence_set_id": str(final_result.evidence_set_id),
            "attribution": [
                {
                    "claim_code": item.claim_code,
                    "mode": item.mode.value,
                    "status": item.status.value,
                    "evidence_codes": list(item.evidence_codes),
                    "reason": item.reason,
                    "clauses": [
                        {
                            "index": clause.clause.index,
                            "text": clause.clause.text,
                            "start": clause.clause.start,
                            "end": clause.clause.end,
                            "evidence_codes": list(clause.evidence_codes),
                            "score": clause.score,
                            "reason": clause.reason,
                        }
                        for clause in item.clauses
                    ],
                }
                for item in final_result.attribution_diagnostics
            ],
        },
        "target_fidelity": {
            "allowed_targets": list(target_fidelity.allowed_targets),
            "used_evidence_identity_keys": list(
                target_fidelity.used_evidence_identity_keys
            ),
            "passed": target_fidelity.passed,
            "reason": target_fidelity.reason,
        },
        "semantic_validation": {
            "errors": list(final_result.validation_errors),
        },
        "result": {
            "outcome": outcome,
            "classification": classification,
            "failure_stage": failure_stage,
            "elapsed_seconds": elapsed,
        },
    }


def evaluate_real_world(
    cases: tuple[EvaluationCase, ...],
    provider: OllamaEmbeddingProvider,
    generator: LegalGenerator,
    semantic_validator: OllamaSemanticSupportValidator,
    model_name: str,
    embedding_model: str,
) -> dict[str, Any]:
    results = []
    # Fresh session per case for evidence building
    for case in cases:
        with SessionLocal() as session:
            res = evaluate_real_world_case(
                session,
                case,
                provider,
                generator,
                semantic_validator,
                model_name,
                embedding_model,
            )
            results.append(res)
    # Metrics
    correct_answers = sum(
        1 for r in results if r["result"]["classification"] == "CORRECT_ANSWER"
    )
    correct_abstentions = sum(
        1 for r in results if r["result"]["classification"] == "CORRECT_ABSTENTION"
    )
    false_abstentions = sum(
        1 for r in results if r["result"]["classification"] == "FALSE_ABSTENTION"
    )
    wrong_targets = sum(
        1 for r in results if r["result"]["classification"] == "WRONG_TARGET"
    )
    unsafe_answers = sum(
        1 for r in results if r["result"]["classification"] == "UNSAFE_ANSWER"
    )
    # Retrieval hit for respondíveis
    respondiveis = [r for r in results if r["expect_answer"]]
    hits = sum(1 for r in respondiveis if r["retrieval"]["hit"])
    total_resp = len(respondiveis)
    retrieval_hit_rate = hits / total_resp if total_resp else 0
    return {
        "cases": len(cases),
        "correct_answers": correct_answers,
        "correct_abstentions": correct_abstentions,
        "false_abstentions": false_abstentions,
        "wrong_targets": wrong_targets,
        "unsafe_answers": unsafe_answers,
        "answered_cases": sum(
            1
            for r in results
            if r["result"]["classification"] in {"CORRECT_ANSWER", "WRONG_TARGET"}
        ),
        "target_fidelity_passes": sum(
            r["target_fidelity"]["passed"] is True for r in results
        ),
        "target_fidelity_failures": sum(
            r["target_fidelity"]["passed"] is False for r in results
        ),
        "retrieval_hit_rate": retrieval_hit_rate,
        "results": results,
    }
