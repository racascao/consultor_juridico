"""Adapter da única inferência de consulta fundamentada do MVP2."""

import json

from pydantic import BaseModel

from consultor_juridico.domain import (
    AbstainOutcome,
    AnswerOutcome,
    ClarificationOutcome,
    ClarificationRequest,
    ConsultationModelOutcome,
    Interpretation,
    Question,
)
from consultor_juridico.infrastructure.ollama.client import (
    OllamaStructuredClient,
    OllamaStructuredError,
)
from consultor_juridico.infrastructure.ollama.schemas import (
    consultation_payload_schema,
)

CONSULTATION_OUTPUT_TOKEN_LIMIT = 512

CONSULTATION_SYSTEM = """Use somente as evidências fornecidas para afirmações jurídicas.
Retorne ANSWER com resposta direta, concisa e IDs fornecidos quando as evidências
permitirem resposta segura; qualifique a resposta quando o texto exigir, sem inventar
lei, artigo, fato ou exceção. Retorne CLARIFY somente se a própria pergunta tiver duas
ou mais interpretações jurídicas materialmente distintas que exijam esclarecimento.
Ruído entre candidatos não torna a pergunta ambígua. Retorne ABSTAIN quando as
evidências não sustentarem resposta segura. Não use conhecimento externo nem exponha
chain-of-thought."""


class OllamaConsultationResponder:
    def __init__(self, client: OllamaStructuredClient) -> None:
        self._client = client

    def respond(self, question: Question, candidates) -> ConsultationModelOutcome:
        allowed_ids = tuple(item.candidate_id for item in candidates)
        try:
            envelope = self._client.complete(
                CONSULTATION_SYSTEM,
                _consultation_input(question, candidates),
                consultation_payload_schema(allowed_ids),
                role="consultation_model",
                num_predict=CONSULTATION_OUTPUT_TOKEN_LIMIT,
            )
            return _consultation_outcome(envelope.root)
        except OllamaStructuredError as exc:
            if exc.kind == "INVALID_STRUCTURED_OUTPUT":
                self._client.mark_last_output_invalid("consultation_model")
            return AbstainOutcome()
        except ValueError:
            self._client.mark_last_output_invalid("consultation_model")
            return AbstainOutcome()


def _consultation_input(question, candidates) -> str:
    return json.dumps(
        {
            "question": question.text,
            "candidates": [
                {
                    "id": item.candidate_id,
                    "reference": item.stable_reference,
                    "text": item.text,
                }
                for item in candidates
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _consultation_outcome(payload: BaseModel) -> ConsultationModelOutcome:
    if payload.decision == "ANSWER":
        return AnswerOutcome(payload.answer, tuple(payload.evidence_ids))
    if payload.decision == "CLARIFY":
        interpretations = tuple(
            Interpretation(item.label, tuple(item.candidate_ids))
            for item in payload.interpretations
        )
        return ClarificationOutcome(
            ClarificationRequest(
                payload.question, tuple(item.label for item in interpretations)
            ),
            interpretations,
        )
    return AbstainOutcome()
