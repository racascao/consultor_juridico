"""Testes unitários de geração e validação da consulta jurídica."""

import json
import uuid
from types import SimpleNamespace

import httpx
import pytest

from consultor_juridico.consultation.errors import LLMResponseError
from consultor_juridico.consultation.llm import (
    OllamaLegalGenerator,
    build_evidence_prompt,
    parse_generated_response,
    response_schema,
)
from consultor_juridico.consultation.types import GeneratedClaim, GeneratedResponse
from consultor_juridico.consultation.validator import validate_citations


def _evidence(code="EV001"):
    return SimpleNamespace(
        evidence_code=code,
        citation_label="CF/88, INCISO IV",
        source_url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
        text_snapshot="é livre a manifestação do pensamento",
    )


def test_prompt_contains_only_question_and_frozen_evidence():
    prompt = build_evidence_prompt("O que é livre?", (_evidence(),))
    assert "O que é livre?" in prompt
    assert "[EV001]" in prompt
    assert "é livre a manifestação do pensamento" in prompt
    assert "Fonte oficial:" in prompt


def test_structured_response_is_parsed_strictly():
    parsed = parse_generated_response(
        {
            "answer": "A manifestação é livre. [EV001]",
            "abstain": False,
            "claims": [
                {
                    "id": "C1",
                    "text": "A manifestação do pensamento é livre.",
                    "evidence_ids": ["EV001"],
                }
            ],
        }
    )
    assert parsed.claims[0].evidence_codes == ("EV001",)


@pytest.mark.parametrize(
    "payload",
    [None, [], {}, {"answer": 1, "abstain": False, "claims": []}],
)
def test_structured_response_rejects_invalid_contract(payload):
    with pytest.raises(LLMResponseError):
        parse_generated_response(payload)


def test_ollama_generator_uses_json_schema_and_temperature_zero(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "message": {
                    "content": json.dumps(
                        {"answer": "Não basta.", "abstain": True, "claims": []}
                    )
                }
            }

    def fake_post(_url, **kwargs):
        captured.update(kwargs["json"])
        return Response()

    monkeypatch.setattr(httpx, "post", fake_post)
    generator = OllamaLegalGenerator("http://ollama:11434", "llama3.2", 30, 500)
    result = generator.generate("Pergunta", (_evidence(),))
    assert result.abstain is True
    assert captured["format"]["type"] == "object"
    assert captured["options"]["temperature"] == 0


def test_generation_schema_restricts_citations_to_authorized_codes():
    schema = response_schema((_evidence("EV001"), _evidence("EV002")))
    allowed = schema["properties"]["claims"]["items"]["properties"]["evidence_ids"][
        "items"
    ]["enum"]
    assert allowed == ["EV001", "EV002"]
    assert schema["properties"]["answer"]["maxLength"] == 1000
    assert schema["properties"]["claims"]["maxItems"] == 4
    assert schema["additionalProperties"] is False


def test_validator_accepts_clean_abstention_without_database_access():
    evidence_set = SimpleNamespace(id=uuid.uuid4(), items=[])
    response = GeneratedResponse("Não há evidência suficiente.", (), abstain=True)
    report = validate_citations(SimpleNamespace(), evidence_set, response)
    assert report.is_valid


def test_validator_rejects_claim_without_citation():
    evidence_set = SimpleNamespace(id=uuid.uuid4(), items=[])
    response = GeneratedResponse(
        "Resposta",
        (GeneratedClaim("C1", "Afirmação", ()),),
    )
    report = validate_citations(SimpleNamespace(), evidence_set, response)
    assert not report.is_valid
    assert "sem citação" in report.errors[0]


def test_validator_rejects_evidence_from_another_set():
    set_id = uuid.uuid4()
    item = SimpleNamespace(
        evidence_code="EV001",
        evidence_set_id=uuid.uuid4(),
        is_validated=True,
    )
    evidence_set = SimpleNamespace(id=set_id, items=[item])
    response = GeneratedResponse("", (GeneratedClaim("C1", "Afirmação", ("EV001",)),))
    report = validate_citations(SimpleNamespace(), evidence_set, response)
    assert not report.is_valid
    assert "não pertence" in report.errors[0]


def test_validator_rejects_unvalidated_evidence():
    set_id = uuid.uuid4()
    item = SimpleNamespace(
        evidence_code="EV001", evidence_set_id=set_id, is_validated=False
    )
    evidence_set = SimpleNamespace(id=set_id, items=[item])
    response = GeneratedResponse("", (GeneratedClaim("C1", "Afirmação", ("EV001",)),))
    report = validate_citations(SimpleNamespace(), evidence_set, response)
    assert not report.is_valid


@pytest.mark.parametrize(
    ("row", "expected_error"),
    [
        (None, "Cadeia documental inválida"),
        (
            SimpleNamespace(chunk_text="alterado", url_source="https://fonte"),
            "Snapshot divergente",
        ),
        (
            SimpleNamespace(chunk_text="snapshot", url_source="https://outra"),
            "URL oficial divergente",
        ),
    ],
)
def test_validator_rejects_broken_physical_chain(row, expected_error):
    set_id = uuid.uuid4()
    item = SimpleNamespace(
        evidence_code="EV001",
        evidence_set_id=set_id,
        is_validated=True,
        chunk_id=uuid.uuid4(),
        legal_element_id=uuid.uuid4(),
        text_snapshot="snapshot",
        source_url="https://fonte",
    )

    class Result:
        def one_or_none(self):
            return row

    session = SimpleNamespace(execute=lambda _statement: Result())
    evidence_set = SimpleNamespace(id=set_id, items=[item])
    response = GeneratedResponse("", (GeneratedClaim("C1", "Afirmação", ("EV001",)),))
    report = validate_citations(session, evidence_set, response)
    assert not report.is_valid
    assert any(expected_error in error for error in report.errors)
