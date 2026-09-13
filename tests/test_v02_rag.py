"""Regressões do fluxo RAG integrado do MVP2, sem inferência real."""

import json
from uuid import UUID

import httpx
import pytest
from typer.testing import CliRunner

from consultor_juridico.application.gold_evidence.prompt import SYSTEM_PROMPT_V2
from consultor_juridico.application.gold_evidence.types import (
    GoldEvidenceContext,
    GoldEvidenceItem,
)
from consultor_juridico.application.rag.services import (
    CitationValidationError,
    EvidenceAssembler,
    InvalidAnswerContractError,
    RunRagQuery,
    parse_answer_contract,
)
from consultor_juridico.cli.main import app
from consultor_juridico.domain.rag import CitationStatus, RagDecision
from consultor_juridico.domain.retrieval import (
    RetrievalCandidate,
    RetrievalContext,
    RetrievalRequest,
)
from consultor_juridico.evaluation.integrated_rag import run_integrated_dev
from consultor_juridico.evaluation.selected_answerer import (
    SELECTED_MODEL,
    SELECTED_MODEL_DIGEST,
)
from consultor_juridico.infrastructure.ollama.selected_answerer import (
    OllamaSelectedAnswerer,
    SelectedAnswererError,
)

VERSION = "a" * 64
KEY_A = "LAW:9784/ARTICLE:1/CAPUT"
KEY_B = "LAW:9784/ARTICLE:2/CAPUT"


def _item(key: str, order: int) -> GoldEvidenceItem:
    return GoldEvidenceItem(
        key,
        "CAPUT",
        f"Texto {key}",
        {"block_index": order},
        "b" * 64,
        "https://example.test/lei",
        order,
    )


class FakeRepository:
    def __init__(self) -> None:
        self.items = {KEY_A: _item(KEY_A, 1), KEY_B: _item(KEY_B, 2)}

    def context(self, version_hash):
        assert version_hash == VERSION
        return GoldEvidenceContext("BR-FED-LEI-9784-1999", VERSION, "b" * 64, "url")

    def materialize(self, version_hash, stable_keys):
        return tuple(
            self.items[key] for key in reversed(stable_keys) if key in self.items
        )

    def provision_keys(self, version_hash):
        return frozenset(self.items)

    def direct_children(self, version_hash, parent_keys, *, max_children_per_parent):
        return {}

    def validate_citation_namespace(self, citations):
        return None


class FakeRetriever:
    implementation_name = "FAKE"
    retrieval_config = {}

    def __init__(self, candidates):
        self.candidates = candidates

    def search(self, request):
        return self.candidates

    def context(self, version_hash):
        return RetrievalContext(
            "BR-FED-LEI-9784-1999",
            UUID(int=9),
            VERSION,
            "b" * 64,
            "parser",
            "1",
            "projection",
            "1",
        )

    def provision_keys(self, version_hash):
        return frozenset({KEY_A, KEY_B})


class FakeAnswerer:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate(self, *, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return json.dumps(self.payload)


def _candidate(*keys):
    return RetrievalCandidate(1, UUID(int=1), "unit-1", 0.8, keys, "texto")


@pytest.mark.parametrize("decision", list(RagDecision))
def test_output_contract_supports_all_decisions(decision):
    citations = [KEY_A] if decision is RagDecision.ANSWER else []
    output = parse_answer_contract(
        json.dumps(
            {"decision": decision.value, "answer": "texto", "citations": citations}
        )
    )
    assert output.decision is decision


@pytest.mark.parametrize(
    "raw",
    [
        "não-json",
        '{"decision":"ANSWER","answer":"x","citations_ids":[]}',
        '{"decision":"ANSWER","answer":"","citations":["x"]}',
        '{"decision":"ANSWER","answer":"x","citations":[]}',
        '{"decision":"ABSTAIN","answer":"x","citations":["x"]}',
        '{"decision":"ANSWER","answer":"x","citations":["x","x"]}',
    ],
)
def test_output_contract_fails_closed(raw):
    with pytest.raises(InvalidAnswerContractError):
        parse_answer_contract(raw)


def test_evidence_assembly_preserves_retrieval_order_and_deduplicates():
    result = EvidenceAssembler(FakeRepository()).assemble(
        VERSION, (_candidate(KEY_B, KEY_A, KEY_B),)
    )
    assert tuple(item.stable_key for item in result) == (KEY_B, KEY_A)


def test_evidence_assembly_expands_direct_children_deterministically():
    parent = "ARTICLE:X/CAPUT"
    child_1 = "ARTICLE:X/CAPUT/INCISO:I"
    child_2 = "ARTICLE:X/CAPUT/INCISO:II"
    repository = FakeRepository()
    repository.items[parent] = _item(parent, 10)
    repository.items[child_1] = _item(child_1, 11)
    repository.items[child_2] = _item(child_2, 12)

    def direct_children(version_hash, parent_keys, *, max_children_per_parent):
        assert parent_keys == (parent,)
        assert max_children_per_parent == 8
        return {parent: (repository.items[child_1], repository.items[child_2])}

    repository.direct_children = direct_children
    result = EvidenceAssembler(repository).assemble(VERSION, (_candidate(parent),))
    assert tuple(item.stable_key for item in result) == (parent, child_1, child_2)


def test_evidence_assembly_deduplicates_retrieved_child_after_expansion():
    parent = "ARTICLE:X/CAPUT"
    child = "ARTICLE:X/CAPUT/INCISO:I"
    repository = FakeRepository()
    repository.items[parent] = _item(parent, 10)
    repository.items[child] = _item(child, 11)
    repository.direct_children = lambda *args, **kwargs: {
        parent: (repository.items[child],)
    }
    result = EvidenceAssembler(repository).assemble(
        VERSION, (_candidate(parent), _candidate(child))
    )
    assert tuple(item.stable_key for item in result) == (parent, child)


def test_evidence_assembly_applies_global_context_limit():
    parent = "ARTICLE:X/CAPUT"
    repository = FakeRepository()
    repository.items[parent] = _item(parent, 1)
    children = tuple(_item(f"{parent}/INCISO:{index}", index + 1) for index in range(8))
    repository.direct_children = lambda *args, **kwargs: {parent: children}
    result = EvidenceAssembler(
        repository, max_children_per_parent=8, max_evidence_items=4
    ).assemble(VERSION, (_candidate(parent),))
    assert tuple(item.stable_key for item in result) == (
        parent,
        f"{parent}/INCISO:0",
        f"{parent}/INCISO:1",
        f"{parent}/INCISO:2",
    )


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (httpx.ReadTimeout("late"), "TIMEOUT"),
        (httpx.ConnectError("down"), "CONNECTIVITY"),
    ],
)
def test_selected_answerer_classifies_transport_failure(monkeypatch, error, category):
    valid = type("Report", (), {"valid": True, "checks": {}})()
    monkeypatch.setattr(
        "consultor_juridico.infrastructure.ollama.selected_answerer.validate_selected_answerer_freeze",
        lambda: valid,
    )

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": SELECTED_MODEL, "digest": SELECTED_MODEL_DIGEST}
                    ]
                },
            )
        raise error

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SelectedAnswererError, match=category):
            OllamaSelectedAnswerer(client, "http://ollama:11434").generate(
                system_prompt="s", user_prompt="u"
            )


def test_integrated_answer_preserves_prompt_trace_and_valid_citation():
    answerer = FakeAnswerer(
        {"decision": "ANSWER", "answer": "Resposta.", "citations": [KEY_A]}
    )
    result = RunRagQuery(
        FakeRetriever((_candidate(KEY_A),)), FakeRepository(), answerer
    ).execute(RetrievalRequest("Pergunta?", VERSION))
    assert result.output.decision is RagDecision.ANSWER
    assert result.citation_validation.status is CitationStatus.VALID
    assert result.evidence[0].stable_key == KEY_A
    assert answerer.calls[0][0] == SYSTEM_PROMPT_V2
    assert "QUESTION:\nPergunta?" in answerer.calls[0][1]
    assert f"EVIDENCE_ID: {KEY_A}" in answerer.calls[0][1]
    assert result.identity.model == SELECTED_MODEL


@pytest.mark.parametrize("decision", ["ABSTAIN", "CLARIFY"])
def test_integrated_non_answer_decisions(decision):
    answerer = FakeAnswerer({"decision": decision, "answer": "Texto.", "citations": []})
    result = RunRagQuery(
        FakeRetriever((_candidate(KEY_A),)), FakeRepository(), answerer
    ).execute(RetrievalRequest("Pergunta?", VERSION))
    assert result.output.decision.value == decision


def test_integrated_dev_uses_retrieved_evidence_and_creates_frozen_artifacts(
    tmp_path,
):
    dataset = tmp_path / "dataset.json"
    dataset.write_text(
        json.dumps(
            {
                "dataset_id": "dev",
                "legal_act_code": "BR-FED-LEI-9784-1999",
                "cases": [
                    {
                        "case_id": "CASE-1",
                        "category": "SINGLE_SUPPORT",
                        "question": "Pergunta?",
                        "gold_provisions": [KEY_A],
                        "required_provisions": [KEY_A],
                        "expected_decision": "ANSWER",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    answerer = FakeAnswerer(
        {"decision": "ANSWER", "answer": "Resposta.", "citations": [KEY_A]}
    )
    result = run_integrated_dev(
        FakeRetriever((_candidate(KEY_A),)),
        FakeRepository(),
        answerer,
        dataset_path=dataset,
        version_hash=VERSION,
        output_dir=tmp_path / "results",
    )

    assert result["metrics"]["automatic_pass"] == 1
    assert result["metrics"]["retrieval_required_citation_recall"] == 1.0
    assert set(result["paths"]) == {"raw", "automatic", "diagnostic", "review"}
    raw = json.loads((tmp_path / "results/integrated_dev_raw_v1.json").read_text())
    assert raw["cases"][0]["retrieved_stable_keys"] == [KEY_A]
    assert raw["cases"][0]["raw_model_response"]


def test_empty_retrieval_abstains_without_calling_answerer():
    answerer = FakeAnswerer({})
    result = RunRagQuery(FakeRetriever(()), FakeRepository(), answerer).execute(
        RetrievalRequest("Pergunta?", VERSION)
    )
    assert result.output.decision is RagDecision.ABSTAIN
    assert answerer.calls == []


@pytest.mark.parametrize(
    ("citation", "status"),
    [
        ("UNKNOWN", CitationStatus.INVALID_CITATION),
        (KEY_B, CitationStatus.OUT_OF_EVIDENCE),
    ],
)
def test_integrated_citation_failure_is_explicit(citation, status):
    answerer = FakeAnswerer(
        {"decision": "ANSWER", "answer": "Resposta.", "citations": [citation]}
    )
    with pytest.raises(CitationValidationError) as captured:
        RunRagQuery(
            FakeRetriever((_candidate(KEY_A),)), FakeRepository(), answerer
        ).execute(RetrievalRequest("Pergunta?", VERSION))
    assert captured.value.validation.status is status


def test_selected_answerer_sends_exact_frozen_configuration(monkeypatch):
    freeze_report = type("Report", (), {"valid": True, "checks": {}})()
    monkeypatch.setattr(
        "consultor_juridico.infrastructure.ollama.selected_answerer.validate_selected_answerer_freeze",
        lambda: freeze_report,
    )

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": SELECTED_MODEL, "digest": SELECTED_MODEL_DIGEST}
                    ]
                },
            )
        payload = json.loads(request.content)
        assert payload["model"] == SELECTED_MODEL
        assert payload["format"] == "json"
        assert payload["think"] is False
        assert payload["stream"] is False
        assert payload["options"] == {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 20,
            "repeat_penalty": 1.0,
            "num_predict": 1024,
            "num_ctx": 8192,
        }
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": '{"decision":"ABSTAIN","answer":"x","citations":[]}'
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        raw = OllamaSelectedAnswerer(client, "http://ollama:11434").generate(
            system_prompt="system", user_prompt="user"
        )
    assert "ABSTAIN" in raw


def test_selected_answerer_fails_on_freeze_or_digest_mismatch(monkeypatch):
    invalid = type("Report", (), {"valid": False, "checks": {"model": False}})()
    monkeypatch.setattr(
        "consultor_juridico.infrastructure.ollama.selected_answerer.validate_selected_answerer_freeze",
        lambda: invalid,
    )
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    ) as client:
        with pytest.raises(SelectedAnswererError, match="FREEZE_MISMATCH"):
            OllamaSelectedAnswerer(client, "http://ollama:11434").generate(
                system_prompt="s", user_prompt="u"
            )

    valid = type("Report", (), {"valid": True, "checks": {}})()
    monkeypatch.setattr(
        "consultor_juridico.infrastructure.ollama.selected_answerer.validate_selected_answerer_freeze",
        lambda: valid,
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"models": [{"name": SELECTED_MODEL, "digest": "wrong"}]}
        )
    )
    with httpx.Client(transport=transport) as client:
        with pytest.raises(SelectedAnswererError, match="DIGEST_MISMATCH"):
            OllamaSelectedAnswerer(client, "http://ollama:11434").generate(
                system_prompt="s", user_prompt="u"
            )


def test_selected_answerer_rejects_native_host_ollama_url():
    with httpx.Client() as client:
        with pytest.raises(ValueError, match="BASE_URL_NOT_ALLOWED"):
            OllamaSelectedAnswerer(client, "http://localhost:11434")


def test_rag_cli_commands_are_exposed_without_external_services():
    ask = CliRunner().invoke(app, ["ask", "--help"])
    status = CliRunner().invoke(app, ["rag", "status", "--help"])
    assert ask.exit_code == 0
    assert "--version-hash" in ask.output
    assert "--trace" in ask.output
    assert status.exit_code == 0
