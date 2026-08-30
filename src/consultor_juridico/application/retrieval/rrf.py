"""Reciprocal Rank Fusion sem pesos ou boosts."""

from dataclasses import replace

from consultor_juridico.application.retrieval.types import RankedSearchUnit

RRF_K = 60


def reciprocal_rank_fusion(
    lexical: tuple[RankedSearchUnit, ...],
    vector: tuple[RankedSearchUnit, ...],
    limit: int,
) -> tuple[RankedSearchUnit, ...]:
    combined: dict[str, RankedSearchUnit] = {}
    scores: dict[str, float] = {}
    lexical_seen: set[str] = set()
    for rank, item in enumerate(lexical, start=1):
        if item.search_unit_id in lexical_seen:
            continue
        lexical_seen.add(item.search_unit_id)
        combined[item.search_unit_id] = replace(item, lexical_rank=rank)
        scores[item.search_unit_id] = scores.get(item.search_unit_id, 0.0) + 1 / (
            RRF_K + rank
        )
    vector_seen: set[str] = set()
    for rank, item in enumerate(vector, start=1):
        if item.search_unit_id in vector_seen:
            continue
        vector_seen.add(item.search_unit_id)
        current = combined.get(item.search_unit_id, item)
        combined[item.search_unit_id] = replace(current, vector_rank=rank)
        scores[item.search_unit_id] = scores.get(item.search_unit_id, 0.0) + 1 / (
            RRF_K + rank
        )
    ordered = sorted(
        combined.values(),
        key=lambda item: (-scores[item.search_unit_id], item.search_unit_id),
    )
    return tuple(
        replace(item, fused_score=scores[item.search_unit_id])
        for item in ordered[:limit]
    )


def diversify_article_families(
    candidates: tuple[RankedSearchUnit, ...], limit: int
) -> tuple[RankedSearchUnit, ...]:
    """Prioriza famílias distintas sem descartar a ordem híbrida restante."""
    if limit < 1:
        return ()

    selected: list[RankedSearchUnit] = []
    deferred: list[RankedSearchUnit] = []
    seen_families: set[str] = set()
    for candidate in candidates:
        family = candidate.article_reference or candidate.stable_reference
        if family in seen_families:
            deferred.append(candidate)
            continue
        seen_families.add(family)
        selected.append(candidate)
        if len(selected) == limit:
            return tuple(selected)

    selected.extend(deferred[: limit - len(selected)])
    return tuple(selected)
