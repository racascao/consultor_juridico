"""Geração estruturada e local via Ollama."""

import json
from copy import deepcopy
from typing import Any

import httpx

from consultor_juridico.consultation.errors import LLMResponseError
from consultor_juridico.consultation.types import GeneratedClaim, GeneratedResponse
from consultor_juridico.models import EvidenceItem

SYSTEM_PROMPT = """Você é um consultor da Constituição Federal de 1988 e do ADCT.
Use EXCLUSIVAMENTE as evidências fornecidas. Não use conhecimento externo.
Cada afirmação factual deve citar ao menos um evidence_id existente.
Produza somente claims atômicas necessárias para responder à pergunta.
Não duplique, parafraseie repetidamente nem acrescente detalhes não expressos.
Ignore evidências que não respondam diretamente à pergunta; a presença de uma
evidência no contexto não autoriza criar uma claim sobre ela.
Em perguntas simples, use uma única claim curta e fiel ao texto da evidência.
Se as evidências não bastarem, responda com abstain=true e claims vazias.
Responda somente no JSON solicitado, em português, sem markdown."""

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
            ctx = metadata["parent_context"]
            parent_ctx = f"\nContexto estrutural: {ctx}"
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
