"""Seleção determinística e auditável de evidências candidatas."""

import re

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


def select_evidence_candidates(
    candidates: tuple[RetrievalCandidate, ...],
    *,
    limit: int = 5,
    question: str | None = None,
) -> tuple[RetrievalCandidate, ...]:
    """Mantém o melhor occurrence de cada identidade normativa."""
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
        return ()
    if not question:
        return tuple(unique[:limit])
    query_tokens = _tokens(question)
    overlaps = [
        len(query_tokens.intersection(_tokens(item.chunk_text))) for item in unique
    ]
    strongest = max(overlaps)
    minimum = max(1, (strongest + 1) // 2)
    selected = [
        item
        for item, overlap in zip(unique, overlaps, strict=True)
        if overlap >= minimum
    ]
    # O primeiro resultado híbrido sempre é preservado; o overlap é apenas
    # um filtro de ruído, não uma prova de relevância semântica.
    if unique[0] not in selected:
        selected.insert(0, unique[0])
    return tuple(selected[:limit])


def _tokens(text: str) -> set[str]:
    return {
        token for token in WORD_RE.findall(text.casefold()) if token not in STOPWORDS
    }
