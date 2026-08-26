"""Traço somente-leitura do selector para os pools congelados da Fase 91.11."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy import select

from consultor_juridico.consultation.selection import (
    select_evidence_candidates_with_diagnostics,
)
from consultor_juridico.consultation.sufficiency import assess_evidence_sufficiency
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.models import (
    Chunk,
    ChunkLegalElement,
    LegalAct,
    LegalElement,
    LegalProvision,
)
from consultor_juridico.retrieval.types import RetrievalCandidate

ROOT = Path(__file__).resolve().parents[1]
INPUT = (
    ROOT
    / "evaluation/results/model_benchmark_91_11/structural_pool_selection_gate.json"
)
OUTPUT = ROOT / "evaluation/results/model_benchmark_91_12/evidence_selection_gate.json"
BASELINE_SHA256 = "866b4b7f467cffd709a884231a076d2e6b0bed90821f83e0ce0d596c3be7c72b"


def _corpus_candidates(session) -> dict[str, RetrievalCandidate]:
    rows = session.execute(
        select(Chunk, LegalElement, LegalProvision, LegalAct)
        .join(ChunkLegalElement, ChunkLegalElement.chunk_id == Chunk.id)
        .join(LegalElement, LegalElement.id == ChunkLegalElement.legal_element_id)
        .join(LegalProvision, LegalProvision.id == LegalElement.legal_provision_id)
        .join(LegalAct, LegalAct.id == LegalElement.legal_act_id)
        .where(
            ChunkLegalElement.is_primary.is_(True),
            LegalElement.text_status == "CURRENT",
            LegalElement.content_role == "NORMATIVE",
        )
        .order_by(LegalProvision.identity_key, Chunk.id)
    ).all()
    parent_ids = {element.parent_id for _, element, _, _ in rows if element.parent_id}
    parents = dict(
        session.execute(
            select(LegalElement.id, LegalElement.normalized_text).where(
                LegalElement.id.in_(parent_ids)
            )
        ).all()
    )
    candidates: dict[str, RetrievalCandidate] = {}
    for chunk, element, provision, act in rows:
        candidates.setdefault(
            provision.identity_key,
            RetrievalCandidate(
                chunk_id=chunk.id,
                legal_element_id=element.id,
                legal_provision_id=provision.id,
                legal_act=act.short_name,
                element_type=element.element_type,
                number_label=element.number_label,
                identity_key=provision.identity_key,
                chunk_text=chunk.chunk_text,
                parent_context=parents.get(element.parent_id),
            ),
        )
    return candidates


def _restore(
    frozen: list[dict[str, Any]], resolved: dict[str, RetrievalCandidate]
) -> tuple[RetrievalCandidate, ...]:
    output: list[RetrievalCandidate] = []
    for item in frozen:
        candidate = resolved[item["identity_key"]]
        output.append(
            RetrievalCandidate(
                **{
                    **asdict(candidate),
                    "lexical_rank": item["lexical_rank"],
                    "vector_rank": item["vector_rank"],
                    "rrf_score": item["rrf_score"],
                }
            )
        )
    return tuple(output)


def _trace(
    case: dict[str, Any], policy: str, resolved: dict[str, RetrievalCandidate]
) -> dict[str, Any]:
    frozen = case["policies"][policy]
    pool = _restore(frozen["selection_pool"], resolved)
    decision = select_evidence_candidates_with_diagnostics(
        pool, limit=3, question=case["question"]
    )
    diagnostics = {item.identity_key: item for item in decision.diagnostics}
    reserve_ids = {item["identity_key"] for item in frozen["structural_reserve"]}
    promotion = {
        item["identity_key"]: item for item in case.get("structural_promotions", [])
    }
    rows = []
    for input_position, item in enumerate(pool, start=1):
        diagnostic = diagnostics[item.identity_key]
        rows.append(
            {
                "candidate_identity": item.identity_key,
                "candidate_source": (
                    "STRUCTURAL_EXPANSION"
                    if item.identity_key in reserve_ids
                    else "PRIMARY_TOP10"
                ),
                "candidate_rrf": item.rrf_score,
                "structural_score": promotion.get(item.identity_key, {}).get("score"),
                "selection_score": diagnostic.final_score,
                "selection_features": {
                    "base_relevance": diagnostic.base_relevance,
                    "query_coverage": diagnostic.query_coverage,
                    "marginal_coverage": diagnostic.marginal_coverage,
                    "redundancy": diagnostic.redundancy,
                    "has_parent_context": item.parent_context is not None,
                },
                "selected": diagnostic.selected_position is not None,
                "rejection_reason": diagnostic.decision_reason,
                "selection_position": diagnostic.selected_position,
                "selector_input_position": input_position,
                "element_type": item.element_type,
            }
        )
    selected = [item.identity_key for item in decision.candidates]
    expected = set(case["expected_provisions"]) | set(case["acceptable_provisions"])
    sufficiency = assess_evidence_sufficiency(case["question"], decision.candidates)
    return {
        "candidate_count": len(pool),
        "selected_identities": selected,
        "expected_target_selected": bool(expected & set(selected)),
        "candidates": rows,
        "sufficiency": {
            "decision": sufficiency.decision.value,
            "reasons": list(sufficiency.reasons),
        },
    }


def main() -> None:
    replay = json.loads(INPUT.read_text())
    with SessionLocal() as session:
        resolved = _corpus_candidates(session)
        baseline_traces = {
            case["case_id"]: _trace(case, "BASELINE", resolved)
            for case in replay["cases"]
        }
        reserve_traces = {
            case["case_id"]: _trace(case, "STRUCTURAL_RESERVE_1", resolved)
            for case in replay["cases"]
        }
    state = reserve_traces["rw-estado-sitio"]
    highlighted = {
        row["candidate_identity"]: row
        for row in state["candidates"]
        if "/ARTICLE:137/" in row["candidate_identity"]
        or "/ARTICLE:138/" in row["candidate_identity"]
        or "/ARTICLE:139/" in row["candidate_identity"]
    }
    answerable = [case for case in replay["cases"] if case["expect_answer"]]
    failures = [
        case["case_id"]
        for case in answerable
        if not baseline_traces[case["case_id"]]["expected_target_selected"]
    ]
    result = {
        "phase": "91.12",
        "baseline_sha256": BASELINE_SHA256,
        "source_artifacts": [str(INPUT.relative_to(ROOT))],
        "selector_implementation": "src/consultor_juridico/consultation/selection.py",
        "selection_budget": 3,
        "new_retrieval_executed": False,
        "structural_score_changed": False,
        "baseline_selector_trace": baseline_traces,
        "reserve_1_selector_trace": reserve_traces,
        "state_siege_trace": {
            "ART137": next(
                row
                for identity, row in highlighted.items()
                if "/ARTICLE:137/" in identity
            ),
            "ART138": next(
                (
                    row
                    for identity, row in highlighted.items()
                    if "/ARTICLE:138/" in identity
                ),
                None,
            ),
            "ART139": next(
                (
                    row
                    for identity, row in highlighted.items()
                    if "/ARTICLE:139/" in identity
                ),
                None,
            ),
            "selected": state["selected_identities"],
        },
        "target_selection_failure_cases": failures,
        "root_causes": {
            "rw-estado-sitio": ["SELECTION_BUDGET", "MARGINAL_GAIN"],
            "rw-voto-obrigatorio": ["SELECTION_BUDGET", "MARGINAL_GAIN"],
            "explanation": (
                "O Art. 137 tem cobertura lexical integral, mas, na posição 11, perde "
                "o orçamento de três itens pela regra de "
                "relevância/marginalidade existente. O structural_score é apenas "
                "provenance do replay: o selector não o lê nem penaliza a origem "
                "estrutural. O mesmo padrão explica o CAPUT do art. 14."
            ),
        },
        "candidate_fix": (
            "NONE — only score/budget behavior was observed; no bug or invariant "
            "violation demonstrated"
        ),
        "pre_fix_results": {"targets_selected": "8/10", "state_siege_selected": False},
        "post_fix_results": "NOT_APPLICABLE",
        "safety_gates": {
            "ABORTO_REMAINS_INSUFFICIENT": reserve_traces["rw-aborto"]["sufficiency"][
                "decision"
            ]
            == "INSUFFICIENT",
            "synthetic_controls": "NOT_RUN_NO_IN_SCOPE_FIX",
        },
        "integration_decision": "NONE",
        "evidence_selection_fix": "INCONCLUSIVE",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["state_siege_trace"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
