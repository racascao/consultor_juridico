"""Contratos dos adapters MVP2 usando somente HTTP mockado."""

import json

import httpx

from consultor_juridico.application.citation import TraceableCitationValidator
from consultor_juridico.application.retrieval import EmbeddingMode
from consultor_juridico.application.workflow import WorkflowDiagnostics
from consultor_juridico.domain import (
    AbstainOutcome,
    AnswerDraft,
    AnswerOutcome,
    Citation,
    CitationItem,
    ClarificationOutcome,
    EvidenceCandidate,
    Question,
    SelectedEvidence,
)
from consultor_juridico.infrastructure.ollama import (
    OllamaConsultationResponder,
    OllamaStructuredClient,
)
from consultor_juridico.infrastructure.ollama.adapters import CONSULTATION_SYSTEM
from consultor_juridico.infrastructure.ollama.schemas import (
    consultation_payload_schema,
)
from consultor_juridico.infrastructure.retrieval import OllamaEmbeddingProvider


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://test")
            response = httpx.Response(
                self.status_code, json=self._payload, request=request
            )
            response.raise_for_status()


class FakeHttpClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


class SequencedHttpClient:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = 0

    def post(self, url, **kwargs):
        self.calls += 1
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)


def chat_client(content, diagnostics=None):
    http = FakeHttpClient({"message": {"content": json.dumps(content)}})
    return (
        OllamaStructuredClient(
            "http://ollama", "ministral-3:3b", 30, http, diagnostics
        ),
        http,
    )


def candidate(identity="E1"):
    return EvidenceCandidate(
        identity,
        "Art. 143. O serviço militar é obrigatório nos termos da lei.",
        "CF88/ARTICLE:143",
        "block:143",
        stable_reference="CF88/ARTICLE:143",
        citation_items=(
            CitationItem("CF88/ARTICLE:143", "Art. 143", "Texto", "block:143"),
        ),
        source_url="https://www.planalto.gov.br",
        source_snapshot_sha="a" * 64,
    )


def selected(identity="E1"):
    return SelectedEvidence.from_candidate(candidate(identity))


def test_consultation_answer_uses_request_scoped_discriminated_contract():
    client, http = chat_client(
        {"decision": "ANSWER", "answer": "Resposta sustentada.", "evidence_ids": ["E1"]}
    )

    result = OllamaConsultationResponder(client).respond(
        Question("Alistamento militar é obrigatório?"), (candidate(),)
    )

    assert isinstance(result, AnswerOutcome)
    assert result.evidence_ids == ("E1",)
    request = http.calls[0][1]["json"]
    assert request["options"] == {"temperature": 0, "num_predict": 512}
    assert request["think"] is False
    schema_text = json.dumps(request["format"])
    assert '"const": "E1"' in schema_text
    assert '"discriminator"' in schema_text
    assert (
        "maxLength"
        not in request["format"]["$defs"]["AnswerConsultationPayload"]["properties"][
            "answer"
        ]
    )
    json.dumps(request)


def test_real_consultation_schema_for_ten_candidates_is_serializable():
    allowed_ids = tuple(f"E{index}" for index in range(1, 11))
    schema = consultation_payload_schema(allowed_ids).model_json_schema()

    serialized = json.dumps(schema)

    assert '"oneOf"' in serialized
    assert '"discriminator"' in serialized
    assert '"E10"' in serialized
    assert (
        schema["$defs"]["AnswerConsultationPayload"]["properties"]["evidence_ids"][
            "minItems"
        ]
        == 1
    )
    assert (
        schema["$defs"]["ClarifyConsultationPayload"]["properties"]["interpretations"][
            "minItems"
        ]
        == 2
    )
    assert all(
        "decision" in definition["required"]
        for name, definition in schema["$defs"].items()
        if name.endswith("ConsultationPayload")
    )
    assert all(
        definition.get("additionalProperties") is False
        for definition in schema["$defs"].values()
    )


def test_consultation_contract_rejects_empty_answer_and_unknown_evidence():
    for payload in (
        {"decision": "ANSWER", "answer": "", "evidence_ids": ["E1"]},
        {"decision": "ANSWER", "answer": "Resposta", "evidence_ids": []},
        {"decision": "ANSWER", "answer": "Resposta", "evidence_ids": ["E99"]},
    ):
        client, _ = chat_client(payload)
        result = OllamaConsultationResponder(client).respond(
            Question("Pergunta?"), (candidate(),)
        )
        assert isinstance(result, AbstainOutcome)


def test_invalid_structured_output_is_distinct_from_provider_failure():
    diagnostics = WorkflowDiagnostics()
    client, _ = chat_client({"decision": "MAYBE"}, diagnostics)

    result = OllamaConsultationResponder(client).respond(
        Question("Pergunta?"), (candidate(),)
    )

    assert isinstance(result, AbstainOutcome)
    call = diagnostics.last_provider_call("consultation_model")
    assert call is not None
    assert call.error_kind == "INVALID_STRUCTURED_OUTPUT"
    assert call.provider_error_category is None


def test_consultation_clarify_requires_two_request_scoped_interpretations():
    candidates = (candidate("E1"), candidate("E2"))
    client, _ = chat_client(
        {
            "decision": "CLARIFY",
            "question": "Qual sentido você pretende?",
            "interpretations": [
                {"label": "Sentido A", "candidate_ids": ["E1"]},
                {"label": "Sentido B", "candidate_ids": ["E2"]},
            ],
        }
    )
    result = OllamaConsultationResponder(client).respond(Question("Q?"), candidates)
    assert isinstance(result, ClarificationOutcome)
    assert len(result.interpretations) == 2

    invalid_client, _ = chat_client(
        {
            "decision": "CLARIFY",
            "question": "Qual sentido?",
            "interpretations": [{"label": "Único", "candidate_ids": ["E99"]}],
        }
    )
    invalid = OllamaConsultationResponder(invalid_client).respond(
        Question("Q?"), candidates
    )
    assert isinstance(invalid, AbstainOutcome)


def test_consultation_abstain_has_no_meaningless_fields():
    schema = consultation_payload_schema(("E1",)).model_json_schema()
    abstain_schema = schema["$defs"]["AbstainConsultationPayload"]
    assert set(abstain_schema["properties"]) == {"decision"}

    client, _ = chat_client({"decision": "ABSTAIN"})
    assert isinstance(
        OllamaConsultationResponder(client).respond(Question("Q?"), (candidate(),)),
        AbstainOutcome,
    )


def test_consultation_prompt_is_short_evidence_bound_and_not_case_specific():
    normalized = " ".join(CONSULTATION_SYSTEM.split())
    assert "somente as evidências fornecidas" in normalized
    assert "CLARIFY somente" in normalized
    assert "chain-of-thought" in normalized
    assert "Art. 143" not in CONSULTATION_SYSTEM
    assert "alistamento" not in CONSULTATION_SYSTEM.lower()


def test_provider_timeout_fails_closed_without_retry():
    diagnostics = WorkflowDiagnostics()
    request = httpx.Request("POST", "http://ollama/api/chat")
    http = SequencedHttpClient((httpx.ReadTimeout("timeout", request=request),))
    client = OllamaStructuredClient(
        "http://ollama", "ministral-3:3b", 30, http, diagnostics
    )

    result = OllamaConsultationResponder(client).respond(Question("Q?"), (candidate(),))

    assert isinstance(result, AbstainOutcome)
    assert http.calls == 1
    call = diagnostics.last_provider_call("consultation_model")
    assert call is not None
    assert call.error_kind == "PROVIDER_TIMEOUT"
    assert call.provider_error_category == "TIMEOUT"


def test_http_400_preserves_safe_provider_diagnostics():
    diagnostics = WorkflowDiagnostics()
    http = FakeHttpClient({"error": "Failed to initialize samplers: bad grammar"})
    client = OllamaStructuredClient(
        "http://ollama", "ministral-3:3b", 30, http, diagnostics
    )
    http.payload = {"error": "Failed to initialize samplers: bad grammar"}
    original_post = http.post

    def failing_post(url, **kwargs):
        response = original_post(url, **kwargs)
        response.status_code = 400
        return response

    http.post = failing_post

    result = OllamaConsultationResponder(client).respond(Question("Q?"), (candidate(),))

    assert isinstance(result, AbstainOutcome)
    call = diagnostics.last_provider_call("consultation_model")
    assert call is not None
    assert call.error_kind == "PROVIDER_ERROR"
    assert call.provider_error_category == "HTTP_ERROR"
    assert call.provider_http_status == 400
    assert call.provider_message == "Failed to initialize samplers: bad grammar"


def test_http_500_is_provider_failure():
    diagnostics = WorkflowDiagnostics()
    http = FakeHttpClient({"error": "internal server error"})
    original_post = http.post

    def failing_post(url, **kwargs):
        response = original_post(url, **kwargs)
        response.status_code = 500
        return response

    http.post = failing_post
    client = OllamaStructuredClient(
        "http://ollama", "ministral-3:3b", 30, http, diagnostics
    )

    OllamaConsultationResponder(client).respond(Question("Q?"), (candidate(),))

    call = diagnostics.last_provider_call("consultation_model")
    assert call is not None
    assert call.error_kind == "PROVIDER_ERROR"
    assert call.provider_http_status == 500


def test_connection_error_is_distinguished_from_http_error():
    diagnostics = WorkflowDiagnostics()
    request = httpx.Request("POST", "http://ollama/api/chat")
    http = SequencedHttpClient(
        (httpx.ConnectError("connection refused", request=request),)
    )
    client = OllamaStructuredClient(
        "http://ollama", "ministral-3:3b", 30, http, diagnostics
    )

    OllamaConsultationResponder(client).respond(Question("Q?"), (candidate(),))

    call = diagnostics.last_provider_call("consultation_model")
    assert call is not None
    assert call.error_kind == "PROVIDER_ERROR"
    assert call.provider_error_category == "CONNECTION_ERROR"
    assert call.provider_http_status is None


def test_consultation_records_native_ollama_metrics():
    diagnostics = WorkflowDiagnostics()
    http = FakeHttpClient(
        {
            "message": {"content": json.dumps({"decision": "ABSTAIN"})},
            "total_duration": 2_000_000_000,
            "load_duration": 100_000_000,
            "prompt_eval_count": 120,
            "prompt_eval_duration": 1_200_000_000,
            "eval_count": 10,
            "eval_duration": 500_000_000,
        }
    )
    client = OllamaStructuredClient(
        "http://ollama", "ministral-3:3b", 30, http, diagnostics
    )

    OllamaConsultationResponder(client).respond(Question("Q?"), (candidate(),))

    call = diagnostics.last_provider_call("consultation_model")
    assert call is not None
    assert call.model == "ministral-3:3b"
    assert call.total_duration_ms == 2000
    assert call.prompt_tokens_per_second == 100
    assert call.generation_tokens_per_second == 20


def test_embedding_provider_centralizes_modes_and_validates_dimensions():
    diagnostics = WorkflowDiagnostics()
    http = FakeHttpClient({"embeddings": [[0.0] * 768]})
    provider = OllamaEmbeddingProvider(
        "http://ollama", "nomic-embed-text", 30, 768, http, diagnostics=diagnostics
    )
    result = provider.embed(("texto",), EmbeddingMode.QUERY)
    assert len(result[0]) == 768
    assert http.calls[0][1]["json"]["input"] == ["search_query: texto"]


def test_embedding_provider_retries_only_transient_timeout():
    request = httpx.Request("POST", "http://ollama/api/embed")
    client = SequencedHttpClient(
        (
            httpx.ReadTimeout("cold start", request=request),
            {"embeddings": [[0.0] * 768]},
        )
    )
    provider = OllamaEmbeddingProvider(
        "http://ollama",
        "nomic-embed-text",
        180,
        768,
        client,
        max_attempts=2,
        sleeper=lambda _: None,
    )
    assert len(provider.embed(("texto",), EmbeddingMode.DOCUMENT)[0]) == 768
    assert client.calls == 2


def test_citation_validator_accepts_traceable_evidence():
    evidence = (selected(),)
    draft = AnswerDraft("Resposta", (Citation("E1", "CF88/ARTICLE:143", "block:143"),))
    assert TraceableCitationValidator().validate(draft, evidence).valid


def test_composition_routes_configured_models_to_their_only_roles(monkeypatch):
    from consultor_juridico.cli import composition

    monkeypatch.setattr(
        composition.settings, "ollama_consultation_model", "consultation-3b"
    )
    monkeypatch.setattr(
        composition.settings, "ollama_embedding_model", "embedding-model"
    )

    workflow_context = composition.workflow_context()

    assert (
        workflow_context.consultation_responder._client.model_name == "consultation-3b"
    )
    assert composition.embedding_provider().model_name == "embedding-model"
