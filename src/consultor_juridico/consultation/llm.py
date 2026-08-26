"""Geração estruturada e local via Ollama."""

import json
import re
from copy import deepcopy
from typing import Any, Protocol

import httpx

from consultor_juridico.consultation.errors import LLMResponseError
from consultor_juridico.consultation.support_slots import SupportSlot
from consultor_juridico.consultation.types import (
    GeneratedClaim,
    GeneratedResponse,
    ScopedGeneration,
)
from consultor_juridico.models import EvidenceItem

GENERATOR_CONTRACT = {
    "minimum_complete_answer": (
        "Produza a MENOR resposta completa suficiente para responder à pergunta."
    ),
    "core_claims_only": (
        "Cada claim deve responder diretamente à pergunta; para uma única regra "
        "jurídica, prefira exatamente uma claim curta."
    ),
    "no_auxiliary_claims": (
        "Não crie claim adicional para explicar, contextualizar, reforçar ou "
        "acrescentar competência, histórico, comentário geral ou outra norma "
        "não indispensável."
    ),
    "evidence_codes_for_citations": (
        "Use somente evidence_ids autorizados para citar as evidências."
    ),
    "do_not_invent_locators": (
        "A prosa da claim deve conter a proposição jurídica, sem inventar ou "
        "acrescentar artigo, parágrafo, inciso, alínea ou item; a localização "
        "é responsabilidade da citação."
    ),
    "abstain_when_unsupported": (
        "Se as evidências não bastarem para uma resposta direta e completa, "
        "responda com abstain=true e claims vazias."
    ),
}

SYSTEM_PROMPT = (
    """Você é um consultor da Constituição Federal de 1988 e do ADCT.
Use EXCLUSIVAMENTE as evidências fornecidas. Não use conhecimento externo.
Cada afirmação factual deve citar ao menos um evidence_id existente.
Ignore evidências que não respondam diretamente à pergunta; a presença de uma
evidência no contexto não autoriza criar uma claim sobre ela.
Preserve exceções, condições e limitações materiais indispensáveis.
"""
    + "\n".join(GENERATOR_CONTRACT.values())
    + """
Responda somente no JSON solicitado, em português, sem markdown."""
)

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string", "maxLength": 1000},
        "abstain": {"type": "boolean"},
        "claims": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string", "maxLength": 500},
                    "evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["id", "text", "evidence_ids"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["answer", "abstain", "claims"],
    "additionalProperties": False,
}

SCOPED_SYSTEM_PROMPT = """Você interpreta um único conjunto fechado de fragmentos
constitucionais verificáveis. Use SOMENTE esses fragmentos e a pergunta.
Produza no máximo uma claim curta, atômica e integralmente sustentada.
Não acrescente fatos, autoridades ou referências externas.
Preserve qualquer exceção, condição ou limitação material presente.
Não escolha nem mencione slot, evidence ID ou citation ID.
Se o slot não sustentar diretamente uma claim útil, use abstain=true.
Responda somente no JSON solicitado, em português, sem markdown."""

SCOPED_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claim": {"type": "string", "maxLength": 500},
        "abstain": {"type": "boolean"},
    },
    "required": ["claim", "abstain"],
    "additionalProperties": False,
}
SCOPED_BINDING_RE = re.compile(r"\bEV\d{3,}\b|\bSS-[0-9a-f-]+\b", re.IGNORECASE)


class LegalGenerator(Protocol):
    """Contrato mínimo comum a geradores livres e controlados."""

    def generate(
        self,
        question: str,
        evidence_items: tuple[EvidenceItem, ...],
        *,
        correction: tuple[str, ...] = (),
    ) -> GeneratedResponse: ...


class EvidenceBoundControlledGenerator:
    """Gera uma única claim factual a partir da Core Evidence congelada.

    EBCG-v1 não interpreta, resume nem combina texto: EV001 é a autoridade
    exclusiva do conteúdo apresentado. O construtor é puro e não possui I/O.
    """

    generation_mode = "EBCG_V1"

    def generate(
        self,
        question: str,
        evidence_items: tuple[EvidenceItem, ...],
        *,
        correction: tuple[str, ...] = (),
    ) -> GeneratedResponse:
        del question, correction
        core = next(
            (
                item
                for item in evidence_items
                if item.evidence_code == "EV001"
                and bool(getattr(item, "is_validated", False))
                and isinstance(getattr(item, "text_snapshot", None), str)
                and item.text_snapshot.strip()
            ),
            None,
        )
        if core is None:
            return GeneratedResponse("", (), abstain=True)
        claim = GeneratedClaim("C1", core.text_snapshot, ("EV001",))
        return GeneratedResponse(core.text_snapshot, (claim,), abstain=False)


class OllamaLegalGenerator:
    """Cliente mínimo do endpoint estruturado `/api/chat` do Ollama."""

    def __init__(self, base_url: str, model: str, timeout: float, max_tokens: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    def generate(
        self,
        question: str,
        evidence_items: tuple[EvidenceItem, ...],
        *,
        correction: tuple[str, ...] = (),
    ) -> GeneratedResponse:
        prompt = build_evidence_prompt(question, evidence_items, correction=correction)
        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "think": False,
                    "format": response_schema(evidence_items),
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "options": {"temperature": 0, "num_predict": self.max_tokens},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            payload = json.loads(content)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise LLMResponseError(f"Resposta inválida do Ollama: {exc}") from exc

        return parse_generated_response(payload)

    def generate_scoped(
        self,
        question: str,
        slot: SupportSlot,
        *,
        correction: tuple[str, ...] = (),
    ) -> ScopedGeneration:
        prompt = build_scoped_prompt(question, slot, correction=correction)
        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "format": SCOPED_RESPONSE_SCHEMA,
                    "messages": [
                        {"role": "system", "content": SCOPED_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "options": {"temperature": 0, "num_predict": self.max_tokens},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            payload = json.loads(content)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise LLMResponseError(
                f"Resposta scoped inválida do Ollama: {exc}"
            ) from exc
        return parse_scoped_generation(payload)


def response_schema(evidence_items: tuple[EvidenceItem, ...]) -> dict[str, Any]:
    """Restringe citações aos códigos realmente autorizados no snapshot."""
    schema = deepcopy(RESPONSE_SCHEMA)
    evidence_ids = schema["properties"]["claims"]["items"]["properties"][
        "evidence_ids"
    ]["items"]
    evidence_ids["enum"] = [item.evidence_code for item in evidence_items]
    return schema


def build_evidence_prompt(
    question: str,
    evidence_items: tuple[EvidenceItem, ...],
    *,
    correction: tuple[str, ...] = (),
) -> str:
    blocks = []
    for item in evidence_items:
        metadata = getattr(item, "validation_metadata", None) or {}
        parent_ctx = ""
        if metadata.get("parent_context"):
            parent_ctx = f"\nContexto estrutural: {metadata['parent_context']}"
        blocks.append(
            f"[{item.evidence_code}]\n"
            f"Referência: {item.citation_label}\n"
            f"Fonte oficial: {item.source_url}\n"
            f"Texto: {item.text_snapshot}{parent_ctx}"
        )
    correction_text = ""
    if correction:
        correction_text = (
            "\nA resposta anterior foi recusada pelos seguintes motivos:\n- "
            + "\n- ".join(correction)
            + "\nCorrija todos eles."
        )
    return (
        f"PERGUNTA:\n{question}\n\nEVIDÊNCIAS AUTORIZADAS:\n"
        + "\n\n".join(blocks)
        + correction_text
        + "\n\nProduza answer, abstain e claims. Use IDs C1, C2... e EV001, EV002..."
    )


def build_scoped_prompt(
    question: str,
    slot: SupportSlot,
    *,
    correction: tuple[str, ...] = (),
) -> str:
    blocks = []
    for fragment in slot.fragments:
        label = (
            "TRECHO ALVO"
            if fragment.role.value == "TARGET_SNAPSHOT"
            else "CONTEXTO ESTRUTURAL PAI"
        )
        blocks.append(f"{label}:\n{fragment.text}")
    correction_text = ""
    if correction:
        safe_corrections = tuple(
            SCOPED_BINDING_RE.sub("[IDENTIFICADOR REDIGIDO]", item)
            for item in correction
        )
        correction_text = (
            "\nA saída anterior foi recusada:\n- "
            + "\n- ".join(safe_corrections)
            + "\nCorrija sem ampliar o conteúdo dos fragmentos."
        )
    return (
        f"PERGUNTA:\n{question}\n\nFRAGMENTOS AUTORIZADOS:\n"
        + "\n\n".join(blocks)
        + correction_text
        + "\n\nProduza somente claim e abstain."
    )


def parse_generated_response(payload: object) -> GeneratedResponse:
    if not isinstance(payload, dict):
        raise LLMResponseError("O JSON raiz deve ser um objeto.")
    answer = payload.get("answer")
    abstain = payload.get("abstain")
    raw_claims = payload.get("claims")
    if not isinstance(answer, str) or not isinstance(abstain, bool):
        raise LLMResponseError("answer/abstain possuem tipos inválidos.")
    if not isinstance(raw_claims, list):
        raise LLMResponseError("claims deve ser uma lista.")
    claims = []
    for value in raw_claims:
        if not isinstance(value, dict):
            raise LLMResponseError("Cada claim deve ser um objeto.")
        code, text, evidence_ids = (
            value.get("id"),
            value.get("text"),
            value.get("evidence_ids"),
        )
        if not isinstance(code, str) or not isinstance(text, str):
            raise LLMResponseError("Claim sem id/text válidos.")
        if not isinstance(evidence_ids, list) or not all(
            isinstance(item, str) for item in evidence_ids
        ):
            raise LLMResponseError("evidence_ids inválidos.")
        claims.append(GeneratedClaim(code, text, tuple(evidence_ids)))
    return GeneratedResponse(answer=answer, claims=tuple(claims), abstain=abstain)


def parse_scoped_generation(payload: object) -> ScopedGeneration:
    if not isinstance(payload, dict) or set(payload) != {"claim", "abstain"}:
        raise LLMResponseError("Contrato scoped deve conter apenas claim e abstain.")
    claim = payload.get("claim")
    abstain = payload.get("abstain")
    if not isinstance(claim, str) or not isinstance(abstain, bool):
        raise LLMResponseError("claim/abstain scoped possuem tipos inválidos.")
    if abstain and claim.strip():
        raise LLMResponseError("Resposta scoped abstida não pode conter claim.")
    if not abstain and not claim.strip():
        raise LLMResponseError("Resposta scoped não abstida exige claim.")
    if SCOPED_BINDING_RE.search(claim):
        raise LLMResponseError("Claim scoped não pode mencionar binding interno.")
    return ScopedGeneration(claim=claim.strip(), abstain=abstain)
