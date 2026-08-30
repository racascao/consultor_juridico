"""Gate determinístico de suficiência anterior à geração."""

import re
import unicodedata

from consultor_juridico.consultation.types import (
    SufficiencyDecision,
    SufficiencyReport,
)
from consultor_juridico.retrieval import RetrievalCandidate

# Política de escopo do MVP1, não uma classificação jurídica do conteúdo.
OUT_OF_SCOPE_PATTERNS = (
    re.compile(r"\b(python|javascript|programação|código-fonte)\b", re.I),
    re.compile(r"\b(receita|bolo|culinária|ingredientes)\b", re.I),
    re.compile(r"\b(futebol|copa do mundo|campeonato|placar)\b", re.I),
    re.compile(r"\b(jurisprudência|decisão|julgado)\b.*\bSTF\b", re.I),
    re.compile(r"\bCLT\b|consolidação das leis do trabalho", re.I),
    re.compile(r"\bqual decreto\b|\bdecreto regulamenta\b", re.I),
    re.compile(r"\bignore (as )?evidências\b|\buse seu conhecimento\b", re.I),
    re.compile(r"\bmesmo que .* não diga\b.*\bconfirme\b", re.I),
    re.compile(r"\b(todos|quais) (os )?meus direitos\b.*\bneste caso\b", re.I),
)


def assess_evidence_sufficiency(
    question: str,
    candidates: tuple[RetrievalCandidate, ...],
    *,
    min_vector_score: float = 0.60,
    min_lexical_score: float = 0.15,
) -> SufficiencyReport:
    """Combina escopo explícito e força observável do retrieval."""
    lexical = max((item.lexical_score or 0.0 for item in candidates), default=0.0)
    vector = max((item.vector_score or 0.0 for item in candidates), default=0.0)
    agreement = sum(
        item.lexical_rank is not None and item.vector_rank is not None
        for item in candidates
    )
    reasons: list[str] = []
    if any(pattern.search(question) for pattern in OUT_OF_SCOPE_PATTERNS):
        reasons.append("Consulta fora do escopo explícito CF/88 + ADCT do MVP1.")
    if not candidates:
        reasons.append("Nenhuma evidência candidata válida.")
    query_tokens = _tokens(question)
    evidence_tokens = {
        token
        for candidate in candidates
        for token in _tokens(
            " ".join(
                part
                for part in (candidate.chunk_text, candidate.parent_context)
                if isinstance(part, str)
            )
        )
    }
    has_textual_anchor = bool(query_tokens & evidence_tokens)
    if (
        vector < min_vector_score
        and lexical < min_lexical_score
        and not has_textual_anchor
    ):
        reasons.append("Sinais lexical e vetorial abaixo dos limiares conservadores.")
    decision = (
        SufficiencyDecision.INSUFFICIENT if reasons else SufficiencyDecision.SUFFICIENT
    )
    if not reasons:
        reasons.append("Consulta no escopo e ao menos um sinal forte de retrieval.")
    return SufficiencyReport(decision, tuple(reasons), lexical, vector, agreement)


def _tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFD", value.casefold())
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    result = set()
    for word in re.findall(r"[^\W\d_]{4,}", normalized):
        if len(word) > 4 and word.endswith("s"):
            word = word[:-1]
        result.add(word[:6])
    return result
