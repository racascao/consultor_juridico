"""Exporta EvidenceSets A/B para o diagnóstico da Fase 9.14.

O módulo é diagnóstico: não grava no banco e não é importado pelo pipeline.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from consultor_juridico.config import settings
from consultor_juridico.consultation.selection import select_evidence_candidates
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.evaluation.dataset import load_dataset
from consultor_juridico.retrieval.embeddings import OllamaEmbeddingProvider
from consultor_juridico.retrieval.search import hybrid_search


def _old_select(candidates, *, limit, question):
    """Implementação transitória equivalente ao selection.py anterior à 9.12."""
    unique = []
    seen = set()
    for candidate in candidates:
        if candidate.legal_provision_id in seen:
            continue
        seen.add(candidate.legal_provision_id)
        unique.append(candidate)
    if not question:
        return tuple(unique[:limit])
    # O algoritmo anterior preservava a ordem híbrida e filtrava por overlap.
    from consultor_juridico.consultation.selection import _selection_text, _tokens

    query = _tokens(question)
    overlaps = [len(query & _tokens(_selection_text(item))) for item in unique]
    strongest = max(overlaps, default=0)
    minimum = 1 if len(query) <= 3 else max(1, (strongest + 1) // 2)
    selected = [
        item
        for item, overlap in zip(unique, overlaps, strict=True)
        if overlap >= minimum
    ]
    if unique and unique[0] not in selected:
        selected.insert(0, unique[0])
    return tuple(selected[: max(limit, 10) if len(query) <= 3 else limit])


def _candidate_json(candidate, position):
    return {
        "position": position,
        "chunk_id": str(candidate.chunk_id),
        "legal_provision_id": str(candidate.legal_provision_id),
        "legal_element_id": str(candidate.legal_element_id),
        "identity_key": candidate.identity_key,
        "element_type": candidate.element_type,
        "number_label": candidate.number_label,
        "text_snapshot": candidate.chunk_text,
        "parent_context": candidate.parent_context,
        "lexical_rank": candidate.lexical_rank,
        "lexical_score": candidate.lexical_score,
        "vector_rank": candidate.vector_rank,
        "vector_score": candidate.vector_score,
        "hybrid_score": candidate.rrf_score,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", default="evaluation/datasets/real_world_short_v1.json"
    )
    parser.add_argument("--output", default="evaluation/results/evidenceset_9_14")
    args = parser.parse_args()
    _, cases = load_dataset(Path(args.dataset))
    wanted = {
        "rw-liberdade-religiosa",
        "rw-racismo",
        "rw-extradicao",
        "rw-direito-vida",
        "rw-estado-sitio",
    }
    provider = OllamaEmbeddingProvider(
        settings.ollama_base_url, settings.embedding_model, settings.embedding_timeout
    )
    output = []
    with SessionLocal() as session:
        for case in cases:
            if case.id not in wanted:
                continue
            candidates = hybrid_search(
                session,
                case.question,
                provider,
                model_name=settings.embedding_model,
                limit=settings.consultation_top_k,
            )
            strategies = {
                "A": _old_select(
                    candidates,
                    limit=settings.consultation_evidence_limit,
                    question=case.question,
                ),
                "B": select_evidence_candidates(
                    candidates,
                    limit=settings.consultation_evidence_limit,
                    question=case.question,
                ),
            }
            output.append(
                {
                    "case_id": case.id,
                    "query": case.question,
                    "created_at": datetime.now(UTC).isoformat(),
                    "configuration": {
                        "generator": settings.ollama_model,
                        "semantic_judge": settings.semantic_judge_model,
                        "embedding": settings.embedding_model,
                        "selection_limit": settings.consultation_evidence_limit,
                    },
                    "strategies": {
                        name: {
                            "candidates": [
                                _candidate_json(c, i)
                                for i, c in enumerate(candidates, 1)
                            ],
                            "selected": [
                                _candidate_json(c, i) for i, c in enumerate(selected, 1)
                            ],
                        }
                        for name, selected in strategies.items()
                    },
                }
            )
    base = Path(args.output)
    base.parent.mkdir(parents=True, exist_ok=True)
    base.with_name(base.name + "_AB.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
