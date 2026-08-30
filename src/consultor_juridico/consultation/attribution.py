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
    AttributionMode,
    AttributionStatus,
    ClaimAttributionDiagnostic,
    ClaimClause,
    ClauseAttribution,
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
    diagnostics: tuple[ClaimAttributionDiagnostic, ...] = ()


_PROTECTED_SCOPE_RE = re.compile(
    r"\b(?:salvo|exceto|excepto|ressalvad\w*|desde\s+que|quando)\b"
    r"|(?:^|[,;])\s*se\b",
    re.IGNORECASE,
)
_PREDICATE_RE = re.compile(
    r"\b(?:e|é|são|foi|foram|será|serão|pode|podem|poderá|poderão|"
    r"deve|devem|deverá|deverão|haverá|há|tem|têm|"
    r"[a-záàâãéêíóôõúç]{4,}(?:ar|er|ir|ado|ada|ados|adas|ido|ida|idos|idas))\b",
    re.IGNORECASE,
)
_SEMICOLON_RE = re.compile(r";\s*")
_ENUMERATION_RE = re.compile(r",\s*(?!conforme\b)(?:(?:e|ou)\s+)?", re.IGNORECASE)
_COORDINATION_RE = re.compile(r"\s+(?:bem\s+como|além\s+de|e)\s+", re.IGNORECASE)


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
    diagnostics: list[ClaimAttributionDiagnostic] = []
    changed = 0
    for claim in response.claims:
        clauses = split_claim_clauses(claim.text)
        mode = AttributionMode.CLAUSE if len(clauses) > 1 else AttributionMode.SIMPLE
        clause_results: list[ClauseAttribution] = []
        selected_by_clause: list[tuple[str, ...]] = []
        for clause in clauses:
            selected = _select_evidence(
                clause.text, evidence_tokens, document_frequency
            )
            if selected is None:
                clause_results.append(
                    ClauseAttribution(
                        clause,
                        (),
                        0.0,
                        "Cláusula sem atribuição material inequívoca.",
                    )
                )
                diagnostics.append(
                    ClaimAttributionDiagnostic(
                        claim.claim_code,
                        mode,
                        AttributionStatus.UNRESOLVED,
                        tuple(clause_results),
                        (),
                        f"Cláusula {clause.index} sem suporte inequívoco.",
                    )
                )
                break
            coverage = _coverage_score(
                clause.text,
                selected,
                evidence_tokens,
                document_frequency,
            )
            literal_coverage = _literal_coverage_score(
                clause.text,
                selected,
                evidence_items,
            )
            clause_score = min(coverage, literal_coverage)
            if mode is AttributionMode.CLAUSE and clause_score < 0.60:
                clause_results.append(
                    ClauseAttribution(
                        clause,
                        selected,
                        clause_score,
                        "Cobertura insuficiente para cláusula material independente.",
                    )
                )
                diagnostics.append(
                    ClaimAttributionDiagnostic(
                        claim.claim_code,
                        mode,
                        AttributionStatus.UNRESOLVED,
                        tuple(clause_results),
                        (),
                        f"Cláusula {clause.index} possui apenas suporte parcial.",
                    )
                )
                break
            selected_by_clause.append(selected)
            clause_results.append(
                ClauseAttribution(
                    clause,
                    selected,
                    clause_score if mode is AttributionMode.CLAUSE else coverage,
                    "EvidenceItems autorizados com contribuição material.",
                )
            )
        else:
            evidence_order = {code: index for index, code in enumerate(evidence_tokens)}
            union = tuple(
                sorted(
                    {code for selected in selected_by_clause for code in selected},
                    key=evidence_order.__getitem__,
                )
            )
            diagnostics.append(
                ClaimAttributionDiagnostic(
                    claim.claim_code,
                    mode,
                    AttributionStatus.ATTRIBUTED,
                    tuple(clause_results),
                    union,
                    "Todas as cláusulas materiais receberam atribuição autorizada.",
                )
            )
            if union != claim.evidence_codes:
                changed += 1
            attributed.append(GeneratedClaim(claim.claim_code, claim.text, union))
            continue

        if diagnostics[-1].status is AttributionStatus.UNRESOLVED:
            reasons.append(f"Claim {claim.claim_code} sem atribuição inequívoca.")
            return AttributionDecision(
                GeneratedResponse(response.answer, (), abstain=True),
                changed,
                True,
                tuple(reasons),
                tuple(diagnostics),
            )
    return AttributionDecision(
        GeneratedResponse(response.answer, tuple(attributed), abstain=False),
        changed,
        False,
        diagnostics=tuple(diagnostics),
    )


def split_claim_clauses(text: str) -> tuple[ClaimClause, ...]:
    """Segmenta somente predicações coordenadas reconhecíveis.

    Condições e exceções permanecem ligadas à regra. Se qualquer divisão
    candidata produzir trecho sem predicação completa, a claim inteira é
    preservada como unidade simples.
    """

    if not text.strip():
        return (ClaimClause(1, text, 0, len(text)),)
    if _PROTECTED_SCOPE_RE.search(text):
        return (ClaimClause(1, text.strip(), 0, len(text)),)
    for pattern in (_SEMICOLON_RE, _ENUMERATION_RE, _COORDINATION_RE):
        parts = _split_spans(text, pattern)
        if len(parts) > 1 and all(_has_predicate(value) for value, _, _ in parts):
            return tuple(
                ClaimClause(index, value, start, end)
                for index, (value, start, end) in enumerate(parts, start=1)
            )
    return (ClaimClause(1, text.strip(), 0, len(text)),)


def _split_spans(
    text: str, pattern: re.Pattern[str]
) -> tuple[tuple[str, int, int], ...]:
    parts: list[tuple[str, int, int]] = []
    start = 0
    for match in pattern.finditer(text):
        raw = text[start : match.start()]
        stripped = raw.strip(" ,;\t\n")
        if stripped:
            offset = raw.find(stripped)
            parts.append((stripped, start + offset, start + offset + len(stripped)))
        start = match.end()
    raw = text[start:]
    stripped = raw.strip(" ,;\t\n")
    if stripped:
        offset = raw.find(stripped)
        parts.append((stripped, start + offset, start + offset + len(stripped)))
    return tuple(parts)


def _has_predicate(text: str) -> bool:
    return len(_tokens(text)) >= 2 and _PREDICATE_RE.search(text) is not None


def _evidence_text(item: Any) -> str:
    if getattr(item, "materialization_type", None) is not None:
        return str(getattr(item, "text_snapshot", ""))
    metadata = getattr(item, "validation_metadata", None) or {}
    return " ".join(
        part
        for part in (getattr(item, "text_snapshot", ""), metadata.get("parent_context"))
        if isinstance(part, str)
    )


def _token(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold())
    without_marks = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    if len(without_marks) > 4 and without_marks.endswith("s"):
        without_marks = without_marks[:-1]
    # Prefixo conservador cobre flexões nominais/verbais sem vocabulário
    # jurídico específico (repúdio/repudiado, obrigatório/obrigatórios).
    return without_marks[:6]


def _tokens(value: str) -> set[str]:
    return {
        _token(word)
        for word in WORD_RE.findall(value)
        if word.casefold() not in STOPWORDS
    }


def _literal_tokens(value: str) -> set[str]:
    result = set()
    for word in WORD_RE.findall(value):
        if word.casefold() in STOPWORDS:
            continue
        normalized = unicodedata.normalize("NFD", word.casefold())
        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        if len(normalized) > 4 and normalized.endswith("s"):
            normalized = normalized[:-1]
        result.add(normalized)
    return result


def _weight(token: str, document_frequency: dict[str, int], total: int) -> float:
    return math.log((total + 1) / (document_frequency.get(token, 0) + 1)) + 1


def _coverage_score(
    text: str,
    selected: tuple[str, ...],
    evidence_tokens: dict[str, set[str]],
    document_frequency: dict[str, int],
) -> float:
    tokens = _tokens(text)
    if not tokens:
        return 0.0
    covered = tokens & set().union(*(evidence_tokens[code] for code in selected))
    total = sum(
        _weight(token, document_frequency, len(evidence_tokens)) for token in tokens
    )
    matched = sum(
        _weight(token, document_frequency, len(evidence_tokens)) for token in covered
    )
    return round(matched / total, 6) if total else 0.0


def _literal_coverage_score(
    text: str,
    selected: tuple[str, ...],
    evidence_items: tuple[Any, ...],
) -> float:
    claim_tokens = _literal_tokens(text)
    if not claim_tokens:
        return 0.0
    selected_codes = set(selected)
    evidence_tokens = set().union(
        *(
            _literal_tokens(_evidence_text(item))
            for item in evidence_items
            if item.evidence_code in selected_codes
        )
    )
    return round(len(claim_tokens & evidence_tokens) / len(claim_tokens), 6)


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
