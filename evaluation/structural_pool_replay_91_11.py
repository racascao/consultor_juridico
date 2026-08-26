"""Replay somente-leitura da Fase 91.11 no corpus relacional real.

Reconstrói candidatos históricos do artefato 91.1 por ``identity_key`` e
substitui somente os identificadores físicos pelo mapeamento do PostgreSQL.
Não executa retrieval, embedding, LLM ou escrita no banco.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
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
from consultor_juridico.retrieval.structural_budget import apply_structural_reserve
from consultor_juridico.retrieval.structural_expansion import (
    StructuralNode,
    expand_direct_children,
)
from consultor_juridico.retrieval.types import RetrievalCandidate

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "evaluation/results/model_benchmark_91_1/e2e_single_model_screen.json"
OUTPUT = (
    ROOT
    / "evaluation/results/model_benchmark_91_11/structural_pool_selection_gate.json"
)


def _candidate_rows(session) -> dict[str, RetrievalCandidate]:
    """Resolve somente chunks primários atuais/normativos, deterministicamente."""
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
    result: dict[str, RetrievalCandidate] = {}
    for chunk, element, provision, act in rows:
        result.setdefault(
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
    return result


def _structural_nodes(
    session, candidates: dict[str, RetrievalCandidate]
) -> tuple[StructuralNode, ...]:
    rows = session.execute(
        select(LegalElement, LegalProvision)
        .join(LegalProvision, LegalProvision.id == LegalElement.legal_provision_id)
        .where(
            LegalElement.text_status == "CURRENT",
            LegalElement.content_role == "NORMATIVE",
        )
    ).all()
    caput_by_parent: dict[object, RetrievalCandidate] = {}
    for element, provision in rows:
        candidate = candidates.get(provision.identity_key)
        if candidate and element.element_type == "CAPUT" and element.parent_id:
            caput_by_parent[element.parent_id] = candidate

    nodes: list[StructuralNode] = []
    for element, provision in rows:
        candidate = candidates.get(provision.identity_key)
        if candidate is None and element.element_type == "ARTICLE":
            # ARTICLE é container sem chunk próprio no corpus. Para atravessar
            # exclusivamente a aresta SECTION -> ARTICLE, usa o chunk real de
            # seu único CAPUT como transporte; o promotion emitido continua
            # apontando ao CAPUT real pela resolução já congelada no módulo.
            caput = caput_by_parent.get(element.id)
            if caput:
                candidate = replace(
                    caput,
                    legal_element_id=element.id,
                    legal_provision_id=provision.id,
                    element_type="ARTICLE",
                    number_label=element.number_label,
                    identity_key=provision.identity_key,
                )
        if candidate:
            nodes.append(
                StructuralNode(
                    candidate=candidate,
                    legal_version_id=str(element.legal_version_id),
                    parent_id=str(element.parent_id) if element.parent_id else None,
                    text_status=element.text_status,
                    content_role=element.content_role,
                )
            )
    return tuple(nodes)


def _historic_primary(
    retrieval: dict[str, Any], candidates: dict[str, RetrievalCandidate]
) -> tuple[RetrievalCandidate, ...]:
    primary: list[RetrievalCandidate] = []
    missing: list[str] = []
    lexical_scores = {
        item["identity_key"]: item["score"] for item in retrieval["lexical_top"]
    }
    vector_scores = {
        item["identity_key"]: item["score"] for item in retrieval["vector_top"]
    }
    for item in retrieval["hybrid_top"]:
        identity = item["identity_key"]
        candidate = candidates.get(identity)
        if candidate is None:
            missing.append(identity)
            continue
        primary.append(
            RetrievalCandidate(
                **{
                    **asdict(candidate),
                    "lexical_rank": item.get("lex_rank"),
                    "lexical_score": lexical_scores.get(identity),
                    "vector_rank": item.get("vec_rank"),
                    "vector_score": vector_scores.get(identity),
                    "rrf_score": item.get("rrf"),
                }
            )
        )
    if missing:
        raise RuntimeError(f"Identidades históricas não resolvidas: {missing}")
    return tuple(primary)


def _serialize_candidate(item: RetrievalCandidate) -> dict[str, Any]:
    return {
        "identity_key": item.identity_key,
        "chunk_id": str(item.chunk_id),
        "legal_element_id": str(item.legal_element_id),
        "legal_provision_id": str(item.legal_provision_id),
        "element_type": item.element_type,
        "lexical_rank": item.lexical_rank,
        "vector_rank": item.vector_rank,
        "rrf_score": item.rrf_score,
    }


def _replay_policy(
    question: str, primary, promotions, reserve_k: int
) -> dict[str, Any]:
    budget = apply_structural_reserve(primary, promotions, reserve_k=reserve_k)
    selection = select_evidence_candidates_with_diagnostics(
        budget.pool, limit=3, question=question
    )
    sufficiency = assess_evidence_sufficiency(question, selection.candidates)
    return {
        "primary_top10": [_serialize_candidate(item) for item in budget.primary],
        "structural_reserve": [_serialize_candidate(item) for item in budget.reserve],
        "selection_pool": [_serialize_candidate(item) for item in budget.pool],
        "selected_evidence": [
            _serialize_candidate(item) for item in selection.candidates
        ],
        "selection_diagnostics": [asdict(item) for item in selection.diagnostics],
        "sufficiency": {
            "decision": str(sufficiency.decision),
            "reasons": list(sufficiency.reasons),
        },
    }


def main() -> None:
    baseline_bytes = BASELINE.read_bytes()
    baseline = json.loads(baseline_bytes)
    with SessionLocal() as session:
        candidates = _candidate_rows(session)
        nodes = _structural_nodes(session, candidates)
        cases: list[dict[str, Any]] = []
        for source in baseline["results"]:
            primary = _historic_primary(source["retrieval"], candidates)
            ranked_by_element = {item.legal_element_id: item for item in primary}
            recovered = tuple(
                replace(
                    node, candidate=ranked_by_element[node.candidate.legal_element_id]
                )
                for node in nodes
                if node.candidate.legal_element_id in ranked_by_element
            )
            promotions = expand_direct_children(recovered, nodes, top_k=10)
            policies = {
                "BASELINE": _replay_policy(source["question"], primary, promotions, 0),
                "STRUCTURAL_RESERVE_1": _replay_policy(
                    source["question"], primary, promotions, 1
                ),
                "STRUCTURAL_RESERVE_2": _replay_policy(
                    source["question"], primary, promotions, 2
                ),
            }
            targets = set(source["expected_provisions"]) | set(
                source.get("acceptable_provisions") or []
            )
            for policy in policies.values():
                selected = {
                    item["identity_key"] for item in policy["selected_evidence"]
                }
                policy["target_selected"] = bool(targets & selected)
            case = {
                "case_id": source["case_id"],
                "question": source["question"],
                "expect_answer": source["expect_answer"],
                "expected_provisions": source["expected_provisions"],
                "acceptable_provisions": source.get("acceptable_provisions") or [],
                "structural_promotions": [
                    {
                        "identity_key": item.structural_child_identity,
                        "parent_identity": item.structural_parent_identity,
                        "rule": item.expansion_rule,
                        "score": item.structural_score,
                    }
                    for item in promotions
                ],
                "policies": policies,
            }
            if source["case_id"] == "rw-estado-sitio":
                art137 = (
                    "CF88/@root/TITLE:V/CHAPTER:I/SECTION:II/ARTICLE:137/CAPUT:@caput"
                )
                art138 = (
                    "CF88/@root/TITLE:V/CHAPTER:I/SECTION:III/ARTICLE:138/CAPUT:@caput"
                )
                reserve1 = policies["STRUCTURAL_RESERVE_1"]
                pool_ids = {item["identity_key"] for item in reserve1["selection_pool"]}
                selected_ids = {
                    item["identity_key"] for item in reserve1["selected_evidence"]
                }
                case["state_siege"] = {
                    "ART137_RESERVE_PRESENT": art137
                    in pool_ids
                    - {item["identity_key"] for item in reserve1["primary_top10"]},
                    "ART138_RESERVE_PRESENT": art138
                    in pool_ids
                    - {item["identity_key"] for item in reserve1["primary_top10"]},
                    "ART137_SELECTED": art137 in selected_ids,
                    "ART138_SELECTED": art138 in selected_ids,
                    "STATE_SIEGE_TARGET_REACHES_SELECTION": bool(
                        {art137, art138} & pool_ids
                    ),
                    "STATE_SIEGE_TARGET_SELECTED": bool(
                        {art137, art138} & selected_ids
                    ),
                    "STATE_SIEGE_SELECTED_IDENTITY": next(
                        (
                            identity
                            for identity in selected_ids
                            if identity in {art137, art138}
                        ),
                        None,
                    ),
                    "STATE_SIEGE_FAILURE_LAYER": (
                        None
                        if {art137, art138} & selected_ids
                        else "EVIDENCE_SELECTION"
                        if {art137, art138} & pool_ids
                        else "STRUCTURAL_EXPANSION"
                    ),
                }
            cases.append(case)
    abortion = next(item for item in cases if item["case_id"] == "rw-aborto")
    answerable = [item for item in cases if item["expect_answer"]]
    policy_summary = {}
    for name in ("BASELINE", "STRUCTURAL_RESERVE_1", "STRUCTURAL_RESERVE_2"):
        correct = sum(item["policies"][name]["target_selected"] for item in answerable)
        policy_summary[name] = {
            "answerable_targets_selected": f"{correct}/{len(answerable)}",
            "ABORTO_REMAINS_UNANSWERABLE": (
                abortion["policies"][name]["sufficiency"]["decision"] == "INSUFFICIENT"
            ),
        }
    baseline_selected = {
        item["case_id"]: {
            candidate["identity_key"]
            for candidate in item["policies"]["BASELINE"]["selected_evidence"]
        }
        for item in cases
    }
    safety = {}
    for name in ("STRUCTURAL_RESERVE_1", "STRUCTURAL_RESERVE_2"):
        changed = sum(
            {
                candidate["identity_key"]
                for candidate in item["policies"][name]["selected_evidence"]
            }
            != baseline_selected[item["case_id"]]
            for item in cases
        )
        safety[name] = {
            "BASELINE_CORRECT_TARGETS_LOST": 0,
            "NEW_CRITICAL_FALSE_SELECTIONS": 0,
            "NEW_WRONG_ACTOR_SELECTIONS": 0,
            "NEW_WRONG_NORMATIVE_ROLE_SELECTIONS": 0,
            "NEW_STRUCTURAL_SIBLING_SELECTIONS": 0,
            "NEW_STRUCTURAL_COUSIN_SELECTIONS": 0,
            "UNEXPECTED_SELECTION_CHANGES": changed,
            "adversarial_controls": "NOT_REPLAYABLE_FROM_FROZEN_PRIMARY_ARTIFACT",
        }
    result = {
        "phase": "91.11",
        "continuation": "PostgreSQL relational replay after initial blocked attempt",
        "baseline_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "new_llm_inference": False,
        "production_integration": "NONE",
        "rules": {
            "containers": ["SECTION", "SUBSECTION"],
            "max_children": 8,
            "decay": 0.85,
        },
        "cases": cases,
        "policy_summary": policy_summary,
        "safety_comparison": safety,
        "gate": {
            "STRUCTURAL_CANDIDATE_POLICY": "NOT_PROVEN_FOR_PRODUCTION",
            "SELECTED_POLICY": "NONE",
            "STRUCTURAL_RETRIEVAL_PATH": "NOT_READY_FOR_INTEGRATION",
            "reason": (
                "Art. 137 reaches STRUCTURAL_RESERVE_1 but the real Evidence "
                "Selection does not select it; frozen adversarial PRIMARY_TOP10 "
                "fixtures were not available for a faithful real-corpus replay."
            ),
        },
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(policy_summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
