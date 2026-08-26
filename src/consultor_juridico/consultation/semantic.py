"""Validação semântica fail-closed, separada da cadeia estrutural."""

import json
import re
from typing import Any, Protocol

import httpx

from consultor_juridico.consultation.types import (
    ClaimSupport,
    GeneratedResponse,
    SemanticSupportReport,
    SemanticSupportStatus,
)
from consultor_juridico.models import EvidenceItem

SEMANTIC_SYSTEM_PROMPT = """Você é um validador de suporte semântico.
Julgue SOMENTE se cada claim é materialmente sustentada pelas evidências citadas.
NÃO responda à pergunta e NÃO use conhecimento externo.
SUPPORTED exige que a claim seja integralmente afirmada ou fielmente parafraseada
pela evidência. Não exija detalhes que a própria claim não declarou.
Julgue cada claim isoladamente; repetição entre claims não altera o suporte.
PARTIALLY_SUPPORTED significa: existe ao menos uma afirmação material sustentada,
mas a claim acrescenta outra afirmação material não sustentada.
UNSUPPORTED significa: nenhuma afirmação material é sustentada, a evidência é
irrelevante, ou a claim contradiz a evidência.

Exemplos abstratos:
- Evidência: "O ingresso é permitido a maiores de 18 anos."
  Claim: "Maiores de 18 anos podem ingressar." => SUPPORTED.
- Evidência: "O serviço inclui A."
  Claim: "O serviço inclui A e B." => PARTIALLY_SUPPORTED.
- Evidência: "O serviço inclui A."
  Claim: "O serviço não inclui A." => UNSUPPORTED.
Para cada claim informe separadamente:
- has_supported_material: existe ao menos uma afirmação material sustentada;
- all_material_supported: todas as afirmações materiais estão sustentadas;
- contradicted: a evidência contradiz o núcleo da claim.
Não escolha o status final; ele será derivado dessas três decisões.
Responda exclusivamente no JSON solicitado."""

SEMANTIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string"},
                    "has_supported_material": {"type": "boolean"},
                    "all_material_supported": {"type": "boolean"},
                    "contradicted": {"type": "boolean"},
                    "evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "reason": {"type": "string"},
                },
                "required": [
                    "claim_id",
                    "has_supported_material",
                    "all_material_supported",
                    "contradicted",
                    "evidence_ids",
                    "reason",
                ],
            },
        }
    },
    "required": ["claims"],
}

WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
SEMANTIC_STOPWORDS = {
    "que",
    "para",
    "pela",
    "pelo",
    "todos",
    "toda",
    "todas",
    "como",
    "uma",
    "com",
    "sem",
    "constituição",
    "constitucional",
}


class SemanticSupportValidator(Protocol):
    def validate(
        self, response: GeneratedResponse, items: tuple[EvidenceItem, ...]
    ) -> SemanticSupportReport: ...


class OllamaSemanticSupportValidator:
    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def validate(
        self, response: GeneratedResponse, items: tuple[EvidenceItem, ...]
    ) -> SemanticSupportReport:
        prompt = build_semantic_support_prompt(response, items)
        try:
            result = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "think": False,
                    "format": SEMANTIC_SCHEMA,
                    "messages": [
                        {"role": "system", "content": SEMANTIC_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "options": {"temperature": 0, "num_predict": 500},
                },
                timeout=self.timeout,
            )
            result.raise_for_status()
            payload = json.loads(result.json()["message"]["content"])
            return parse_semantic_support(payload, response, items)
        except (httpx.HTTPError, KeyError, RuntimeError, TypeError, ValueError) as exc:
            return SemanticSupportReport((), f"Falha semântica fail-closed: {exc}")


def build_semantic_support_prompt(
    response: GeneratedResponse, items: tuple[EvidenceItem, ...]
) -> str:
    evidence = {item.evidence_code: item for item in items}
    blocks = []
    for claim in response.claims:
        cited = []
        for code in claim.evidence_codes:
            item = evidence.get(code)
            if item is not None:
                cited.append(f"[{code}] {_semantic_prompt_evidence_text(item)}")
        blocks.append(
            f"CLAIM {claim.claim_code}: {claim.text}\nEVIDÊNCIAS CITADAS:\n"
            + "\n".join(cited)
        )
    return "\n\n".join(blocks)


def parse_semantic_support(
    payload: object,
    response: GeneratedResponse,
    items: tuple[EvidenceItem, ...],
) -> SemanticSupportReport:
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        return SemanticSupportReport((), "Contrato semântico inválido.")
    expected = {
        claim.claim_code: set(claim.evidence_codes) for claim in response.claims
    }
    claim_text = {claim.claim_code: claim.text for claim in response.claims}
    evidence_text = {
        item.evidence_code: _authorized_evidence_text(item) for item in items
    }
    available = {item.evidence_code for item in items}
    parsed: list[ClaimSupport] = []
    try:
        for value in payload["claims"]:
            code = value["claim_id"]
            evidence_codes = tuple(value["evidence_ids"])
            if (
                code not in expected
                or not set(evidence_codes) <= expected[code] <= available
            ):
                raise ValueError("Claim/evidência incompatível com a geração.")
            has_supported = value["has_supported_material"]
            all_supported = value["all_material_supported"]
            contradicted = value["contradicted"]
            if not all(
                isinstance(item, bool)
                for item in (has_supported, all_supported, contradicted)
            ) or (all_supported and not has_supported):
                raise ValueError("Decisões semânticas booleanas inválidas.")
            if contradicted or not has_supported:
                status = SemanticSupportStatus.UNSUPPORTED
            elif all_supported:
                status = SemanticSupportStatus.SUPPORTED
            else:
                status = SemanticSupportStatus.PARTIALLY_SUPPORTED
            if status is SemanticSupportStatus.SUPPORTED and not _has_lexical_anchor(
                claim_text[code],
                tuple(evidence_text[item] for item in evidence_codes),
            ):
                status = SemanticSupportStatus.UNSUPPORTED
            parsed.append(
                ClaimSupport(
                    code,
                    status,
                    evidence_codes,
                    str(value["reason"]),
                )
            )
    except (KeyError, TypeError, ValueError) as exc:
        return SemanticSupportReport((), f"Contrato semântico inválido: {exc}")
    if {item.claim_code for item in parsed} != set(expected):
        return SemanticSupportReport((), "Validação semântica omitiu claims.")
    return SemanticSupportReport(tuple(parsed))


def _has_lexical_anchor(claim: str, evidence: tuple[str, ...]) -> bool:
    claim_tokens = {
        token
        for token in WORD_RE.findall(claim.casefold())
        if token not in SEMANTIC_STOPWORDS
    }
    evidence_tokens = {
        token
        for text in evidence
        for token in WORD_RE.findall(text.casefold())
        if token not in SEMANTIC_STOPWORDS
    }
    return bool(claim_tokens.intersection(evidence_tokens))


def _authorized_evidence_text(item: EvidenceItem) -> str:
    if getattr(item, "materialization_type", None) is not None:
        return str(item.text_snapshot)
    metadata = getattr(item, "validation_metadata", None) or {}
    return " ".join(
        part
        for part in (item.text_snapshot, metadata.get("parent_context"))
        if isinstance(part, str) and part.strip()
    )


def _semantic_prompt_evidence_text(item: EvidenceItem) -> str:
    """Preserva contexto pai legado sem duplicar evidência materializada."""
    if getattr(item, "materialization_type", None) is not None:
        return str(item.text_snapshot)
    metadata = getattr(item, "validation_metadata", None) or {}
    parent_context = metadata.get("parent_context")
    context = (
        f"\nContexto estrutural: {parent_context}"
        if isinstance(parent_context, str) and parent_context.strip()
        else ""
    )
    return f"{item.text_snapshot}{context}"
