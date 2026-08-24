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
        len(query_tokens.intersection(_tokens(_selection_text(item))))
        for item in unique
    ]
    strongest = max(overlaps)
    if len(query_tokens) <= 3:
        minimum = 1
    else:
        minimum = max(1, (strongest + 1) // 2)
    # O overlap mede cobertura textual; a posição original já representa o
    # ranking híbrido. A ordenação composta evita que candidatos apenas
    # temáticos ocupem todo o orçamento de evidências em consultas curtas.
    selected = [
        (item, overlap, position)
        for position, (item, overlap) in enumerate(zip(unique, overlaps, strict=True))
        if overlap >= minimum
    ]
    selected.sort(
        key=lambda value: (
            -value[1],
            -int(value[0].parent_context is not None),
            value[2],
            str(value[0].chunk_id),
        )
    )
    if not selected:
        # Sem âncora lexical, preserva apenas o melhor resultado híbrido para
        # que a suficiência possa decidir de modo fail-closed.
        return (unique[0],)
    return tuple(item for item, _, _ in selected[:limit])


def _normalize_token(token: str) -> str:
    import unicodedata

    nfkd = unicodedata.normalize("NFD", token.casefold())
    ascii_token = "".join(c for c in nfkd if not unicodedata.combining(c))
    if len(ascii_token) > 5:
        return ascii_token[:6]
    return ascii_token


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
