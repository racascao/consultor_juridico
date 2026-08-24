"""Classificação conservadora de completude para respostas slot-scoped."""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum


class QueryScope(StrEnum):
    EXPLICITLY_EXHAUSTIVE = "EXPLICITLY_EXHAUSTIVE"
    EXPLICITLY_NON_EXHAUSTIVE = "EXPLICITLY_NON_EXHAUSTIVE"
    TOPICAL_LIMITED = "TOPICAL_LIMITED"
    UNRESOLVED = "UNRESOLVED"


_EXHAUSTIVE_RE = re.compile(
    r"\b(?:todos|todas|liste|enumere)\b"
    r"|\b(?:requisitos|hipoteses|condicoes|excecoes)\s+complet(?:os|as)\b",
    re.IGNORECASE,
)
_NON_EXHAUSTIVE_RE = re.compile(
    r"\b(?:de|dê)\s+um\s+exemplo\b"
    r"|\bcite\s+uma\s+hipotese\b"
    r"|\bmencione\s+uma\s+possibilidade\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
_FUNCTIONAL = {
    "como",
    "constituição",
    "constitucional",
    "disso",
    "isso",
    "o que",
    "que",
    "sobre",
}


def classify_query_scope(question: str) -> QueryScope:
    normalized = _normalize(question)
    if not normalized:
        return QueryScope.UNRESOLVED
    if _EXHAUSTIVE_RE.search(normalized):
        return QueryScope.EXPLICITLY_EXHAUSTIVE
    if _NON_EXHAUSTIVE_RE.search(normalized):
        return QueryScope.EXPLICITLY_NON_EXHAUSTIVE
    material = {
        word for word in _WORD_RE.findall(normalized) if word not in _FUNCTIONAL
    }
    return QueryScope.TOPICAL_LIMITED if material else QueryScope.UNRESOLVED


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))
