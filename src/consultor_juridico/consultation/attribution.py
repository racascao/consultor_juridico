"""Atribuição determinística de claims a snapshots de evidência.

Este módulo é deliberadamente puro e não é chamado pelo serviço nesta fase.
Ele só pode escolher códigos presentes no EvidenceSet recebido; em caso de
ambiguidade, retorna uma resposta abstida (fail-closed).
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from consultor_juridico.consultation.types import (
    GeneratedClaim,
    GeneratedResponse,
)

WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
STOPWORDS = {
    "a",
    "ao",
    "as",
    "com",
    "conforme",
    "constituição",
    "constitucional",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "estabelece",
    "estabelecido",
    "artigo",
    "inciso",
    "parágrafo",
    "pela",
    "pelo",
    "que",
    "são",
    "segundo",
    "nos",
    "na",
    "no",
    "um",
    "uma",
}


@dataclass(frozen=True, slots=True)
class AttributionDecision:
    response: GeneratedResponse
    changed_claims: int
    abstained: bool
    reasons: tuple[str, ...] = ()


def deterministically_attribute(
    response: GeneratedResponse,
    evidence_items: tuple[Any, ...],
) -> AttributionDecision:
    """Reatribui claims usando somente texto/contexto dos EvidenceItems.

    A pontuação usa cobertura lexical ponderada pela raridade no próprio
    EvidenceSet. Isso reduz o peso de palavras temáticas comuns (por exemplo,
    ``prisão``) e favorece termos distintivos (por exemplo, ``perpétuo``).
    Nenhum ID é criado; uma claim sem cobertura inequívoca faz toda a resposta
    falhar fechadamente.
    """

    if response.abstain:
        abstained_response = GeneratedResponse(response.answer, (), abstain=True)
        return AttributionDecision(abstained_response, 0, False)
    if not response.claims or not evidence_items:
        return AttributionDecision(
            GeneratedResponse(response.answer, (), abstain=True),
            0,
            True,
            ("Não há claims ou evidências para atribuição.",),
        )

    evidence_tokens = {
        item.evidence_code: _tokens(_evidence_text(item)) for item in evidence_items
    }
    document_frequency = {
        token: sum(token in tokens for tokens in evidence_tokens.values())
        for tokens in evidence_tokens.values()
        for token in tokens
    }
    reasons: list[str] = []
    attributed: list[GeneratedClaim] = []
    changed = 0
    for claim in response.claims:
        selected = _select_evidence(claim.text, evidence_tokens, document_frequency)
        if selected is None:
            reasons.append(f"Claim {claim.claim_code} sem atribuição inequívoca.")
            return AttributionDecision(
                GeneratedResponse(response.answer, (), abstain=True),
                changed,
                True,
                tuple(reasons),
            )
        if selected != claim.evidence_codes:
            changed += 1
        attributed.append(GeneratedClaim(claim.claim_code, claim.text, tuple(selected)))
    return AttributionDecision(
        GeneratedResponse(response.answer, tuple(attributed), abstain=False),
        changed,
        False,
    )


def _evidence_text(item: Any) -> str:
    metadata = getattr(item, "validation_metadata", None) or {}
    parent = metadata.get("parent_context")
    identity = metadata.get("identity_key")
    return " ".join(
        part
        for part in (getattr(item, "text_snapshot", ""), parent, identity)
        if isinstance(part, str)
    )


def _token(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold())
    without_marks = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    # Prefix matching handles inflection conservatively (pena/penas,
    # obrigatório/obrigatórios) without maintaining a legal synonym list.
    return without_marks[:7]


def _tokens(value: str) -> set[str]:
    return {
        _token(word)
        for word in WORD_RE.findall(value)
        if word.casefold() not in STOPWORDS
    }


def _weight(token: str, document_frequency: dict[str, int], total: int) -> float:
    return math.log((total + 1) / (document_frequency.get(token, 0) + 1)) + 1


def _select_evidence(
    claim_text: str,
    evidence_tokens: dict[str, set[str]],
    document_frequency: dict[str, int],
) -> tuple[str, ...] | None:
    claim_tokens = _tokens(claim_text)
    if not claim_tokens:
        return None
    total_weight = sum(
        _weight(token, document_frequency, len(evidence_tokens))
        for token in claim_tokens
    )
    scored: list[tuple[str, float, set[str]]] = []
    for code, tokens in evidence_tokens.items():
        overlap = claim_tokens & tokens
        score = (
            sum(
                _weight(token, document_frequency, len(evidence_tokens))
                for token in overlap
            )
            / total_weight
        )
        if score > 0:
            scored.append((code, score, overlap))
    if not scored:
        return None
    scored.sort(key=lambda value: (-value[1], value[0]))
    best_code, best_score, best_overlap = scored[0]
    if best_score < 0.40:
        return None
    second_score = scored[1][1] if len(scored) > 1 else 0.0
    # A rare, materially distinctive token can make a single evidence item
    # decisive even when a generic token appears in several siblings.
    if best_score < 0.55 and best_score - second_score < 0.08:
        return None

    selected = [best_code]
    covered = set(best_overlap)
    for code, score, overlap in scored[1:]:
        new_tokens = overlap - covered
        if score >= 0.35 and new_tokens:
            selected.append(code)
            covered.update(new_tokens)
        if (
            len(selected) == 4
            or sum(
                _weight(token, document_frequency, len(evidence_tokens))
                for token in covered
            )
            / total_weight
            >= 0.90
        ):
            break
    evidence_order = {code: index for index, code in enumerate(evidence_tokens)}
    return tuple(sorted(selected, key=evidence_order.__getitem__))
