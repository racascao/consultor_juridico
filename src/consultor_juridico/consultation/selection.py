"""Seleção determinística e auditável de evidências candidatas."""

import re
from dataclasses import dataclass

from consultor_juridico.retrieval import RetrievalCandidate

WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
STOPWORDS = {
    "que",
    "quais",
    "qual",
    "como",
    "são",
    "pela",
    "pelo",
    "para",
    "sobre",
    "constituição",
    "constitucional",
}


@dataclass(frozen=True, slots=True)
class SelectionCandidateDiagnostic:
    identity_key: str
    base_relevance: float
    query_coverage: float
    marginal_coverage: float
    redundancy: float
    final_score: float
    selected_position: int | None
    decision_reason: str


@dataclass(frozen=True, slots=True)
class EvidenceSelectionDecision:
    candidates: tuple[RetrievalCandidate, ...]
    diagnostics: tuple[SelectionCandidateDiagnostic, ...]


def select_evidence_candidates(
    candidates: tuple[RetrievalCandidate, ...],
    *,
    limit: int = 5,
    question: str | None = None,
) -> tuple[RetrievalCandidate, ...]:
    """Mantém occurrences relevantes com cobertura substantiva não redundante."""
    return select_evidence_candidates_with_diagnostics(
        candidates, limit=limit, question=question
    ).candidates


def select_evidence_candidates_with_diagnostics(
    candidates: tuple[RetrievalCandidate, ...],
    *,
    limit: int = 5,
    question: str | None = None,
) -> EvidenceSelectionDecision:
    """Seleciona evidências e explica relevância, margem e redundância.

    A posição original continua sendo a autoridade de retrieval. A contribuição
    marginal só desempata candidatos que já possuem âncora substantiva na query;
    tokens novos, isoladamente, nunca tornam um candidato elegível.
    """
    if limit < 1:
        raise ValueError("O limite de evidências deve ser positivo.")
    unique: list[RetrievalCandidate] = []
    seen: set[object] = set()
    for candidate in candidates:
        key = candidate.legal_provision_id
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    if not unique:
        return EvidenceSelectionDecision((), ())
    if not question:
        chosen = tuple(unique[:limit])
        diagnostics = tuple(
            SelectionCandidateDiagnostic(
                item.identity_key,
                _rank_relevance(index),
                0.0,
                0.0,
                0.0,
                _rank_relevance(index),
                index + 1 if index < limit else None,
                "SELECTED_BY_RETRIEVAL_ORDER" if index < limit else "REJECTED_BY_LIMIT",
            )
            for index, item in enumerate(unique)
        )
        return EvidenceSelectionDecision(chosen, diagnostics)
    query_tokens = _tokens(question)
    if not query_tokens:
        return select_evidence_candidates_with_diagnostics(
            tuple(unique), limit=limit, question=None
        )
    token_sets = [_tokens(_selection_text(item)) for item in unique]
    overlap_sets = [query_tokens.intersection(tokens) for tokens in token_sets]
    overlaps = [len(overlap) for overlap in overlap_sets]
    strongest = max(overlaps)
    if len(query_tokens) <= 3:
        minimum = 1
    else:
        minimum = max(1, (strongest + 1) // 2)
    eligible = [index for index, overlap in enumerate(overlaps) if overlap >= minimum]
    if not eligible:
        # Sem âncora lexical, preserva apenas o melhor resultado híbrido para
        # que a suficiência possa decidir de modo fail-closed.
        diagnostics = tuple(
            SelectionCandidateDiagnostic(
                item.identity_key,
                _rank_relevance(index),
                0.0,
                0.0,
                0.0,
                _rank_relevance(index),
                1 if index == 0 else None,
                "SELECTED_AS_RETRIEVAL_FALLBACK"
                if index == 0
                else "REJECTED_WITHOUT_QUERY_ANCHOR",
            )
            for index, item in enumerate(unique)
        )
        return EvidenceSelectionDecision((unique[0],), diagnostics)

    query_size = len(query_tokens)
    base_scores = [
        0.65 * (len(overlap_sets[index]) / query_size)
        + 0.20 * _rank_relevance(index)
        + 0.15 * int(unique[index].parent_context is not None)
        for index in range(len(unique))
    ]
    selected_indices: list[int] = []
    marginal_by_index = [0.0] * len(unique)
    redundancy_by_index = [0.0] * len(unique)
    final_by_index = list(base_scores)

    first = max(
        eligible,
        key=lambda index: (
            base_scores[index],
            -index,
            str(unique[index].chunk_id),
        ),
    )
    selected_indices.append(first)
    covered = set(overlap_sets[first])

    while len(selected_indices) < limit:
        options: list[int] = []
        for index in eligible:
            if index in selected_indices:
                continue
            marginal = len(overlap_sets[index] - covered) / query_size
            redundancy = max(
                _jaccard(token_sets[index], token_sets[chosen])
                for chosen in selected_indices
            )
            final_score = (
                0.45 * base_scores[index] + 0.40 * marginal + 0.15 * (1.0 - redundancy)
            )
            marginal_by_index[index] = marginal
            redundancy_by_index[index] = redundancy
            final_by_index[index] = final_score
            # Sem cobertura nova, somente evidência ainda forte e não redundante
            # pode ocupar o orçamento. Isso evita promoção por novidade espúria.
            if marginal == 0.0 and (base_scores[index] < 0.30 or redundancy >= 0.85):
                continue
            options.append(index)
        if not options:
            break
        chosen = max(
            options,
            key=lambda index: (
                final_by_index[index],
                -index,
                str(unique[index].chunk_id),
            ),
        )
        selected_indices.append(chosen)
        covered.update(overlap_sets[chosen])

    selected_positions = {
        index: position for position, index in enumerate(selected_indices, start=1)
    }
    diagnostics = tuple(
        SelectionCandidateDiagnostic(
            item.identity_key,
            round(base_scores[index], 6),
            round(len(overlap_sets[index]) / query_size, 6),
            round(marginal_by_index[index], 6),
            round(redundancy_by_index[index], 6),
            round(final_by_index[index], 6),
            selected_positions.get(index),
            "SELECTED"
            if index in selected_positions
            else (
                "REJECTED_WITHOUT_QUERY_ANCHOR"
                if index not in eligible
                else "REJECTED_AS_REDUNDANT_OR_BY_LIMIT"
            ),
        )
        for index, item in enumerate(unique)
    )
    return EvidenceSelectionDecision(
        tuple(unique[index] for index in selected_indices), diagnostics
    )


def _rank_relevance(index: int) -> float:
    return 1.0 / (index + 1)


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _normalize_token(token: str) -> str:
    import unicodedata

    nfkd = unicodedata.normalize("NFD", token.casefold())
    ascii_token = "".join(c for c in nfkd if not unicodedata.combining(c))
    if len(ascii_token) > 4 and ascii_token.endswith("s"):
        ascii_token = ascii_token[:-1]
    return ascii_token[:6]


def _tokens(text: str) -> set[str]:
    return {
        _normalize_token(token)
        for token in WORD_RE.findall(text.casefold())
        if token not in STOPWORDS
    }


def _selection_text(candidate: RetrievalCandidate) -> str:
    """Usa contexto estrutural derivado somente para decidir relevância."""
    return " ".join(
        part
        for part in (candidate.chunk_text, candidate.parent_context)
        if isinstance(part, str)
    )
