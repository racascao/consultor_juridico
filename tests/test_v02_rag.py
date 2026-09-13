"""Regressões do fluxo RAG integrado do MVP2, sem inferência real."""

import json
from hashlib import sha256
from pathlib import Path
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
from consultor_juridico.domain.rag import (
    CitationStatus,
    QueryMode,
    RagDecision,
    RagQueryRequest,
)
from consultor_juridico.domain.retrieval import (
    RetrievalCandidate,
    RetrievalContext,
)
from consultor_juridico.evaluation.gold_evidence import load_gold_dataset
from consultor_juridico.evaluation.integrated_rag import (
    IntegratedDevProfile,
    run_integrated_dev,
)
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
    ).execute(RagQueryRequest("Pergunta?", VERSION, QueryMode.LEGAL_RULE))
    assert result.output.decision is RagDecision.ANSWER
    assert result.citation_validation.status is CitationStatus.VALID
    assert result.evidence[0].stable_key == KEY_A
    assert answerer.calls[0][0] == SYSTEM_PROMPT_V2
    assert "QUESTION:\nPergunta?" in answerer.calls[0][1]
    assert f"EVIDENCE_ID: {KEY_A}" in answerer.calls[0][1]
    assert result.identity is not None
    assert result.identity.model == SELECTED_MODEL
    assert result.query_mode is QueryMode.LEGAL_RULE
    assert result.retrieval_executed is True
    assert result.answerer_executed is True


@pytest.mark.parametrize("decision", ["ABSTAIN", "CLARIFY"])
def test_integrated_non_answer_decisions(decision):
    answerer = FakeAnswerer({"decision": decision, "answer": "Texto.", "citations": []})
    result = RunRagQuery(
        FakeRetriever((_candidate(KEY_A),)), FakeRepository(), answerer
    ).execute(RagQueryRequest("Pergunta?", VERSION, QueryMode.LEGAL_RULE))
    assert result.output.decision.value == decision


class ExplodingDependency:
    def __getattr__(self, name):
        raise AssertionError(f"CASE_APPLICATION acessou dependência externa: {name}")


@pytest.mark.parametrize(
    "question",
    ["Posso fazer X?", "Quais são as condições para X?", "texto arbitrário"],
)
def test_case_application_clarifies_without_retrieval_or_answerer(question):
    result = RunRagQuery(
        ExplodingDependency(), ExplodingDependency(), ExplodingDependency()
    ).execute(RagQueryRequest(question, VERSION, QueryMode.CASE_APPLICATION))

    assert result.output.decision is RagDecision.CLARIFY
    assert result.output.citations == ()
    assert result.retrieved == ()
    assert result.evidence == ()
    assert result.identity is None
    assert result.retrieval_executed is False
    assert result.answerer_executed is False
    assert result.routing_reason == "CASE_APPLICATION_NOT_SUPPORTED_IN_MVP2"


def test_rag_query_request_rejects_untyped_or_missing_mode():
    with pytest.raises(ValueError, match="QueryMode explícito"):
        RagQueryRequest("Pergunta?", VERSION, "legal-rule")  # type: ignore[arg-type]


def test_all_ambiguous_dev_cases_clarify_without_external_calls():
    dataset = load_gold_dataset(
        Path("evaluation/datasets/lei_9784_gold_evidence_dev_v1.json")
    )
    ambiguous = tuple(case for case in dataset.cases if case.category == "AMBIGUOUS")

    results = [
        RunRagQuery(
            ExplodingDependency(), ExplodingDependency(), ExplodingDependency()
        ).execute(RagQueryRequest(case.question, VERSION, QueryMode.CASE_APPLICATION))
        for case in ambiguous
    ]

    assert [case.case_id for case in ambiguous] == [
        "GOLD-027",
        "GOLD-028",
        "GOLD-029",
        "GOLD-030",
        "GOLD-031",
        "GOLD-032",
    ]
    assert all(result.output.decision is RagDecision.CLARIFY for result in results)
    assert all(result.retrieval_executed is False for result in results)
    assert all(result.answerer_executed is False for result in results)


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


def test_integrated_dev_v2_applies_external_mode_mapping_without_llm_for_case(
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
                        "case_id": "RULE",
                        "category": "SINGLE_SUPPORT",
                        "question": "Qual é a regra?",
                        "gold_provisions": [KEY_A],
                        "required_provisions": [KEY_A],
                        "expected_decision": "ANSWER",
                    },
                    {
                        "case_id": "CASE",
                        "category": "AMBIGUOUS",
                        "question": "A regra se aplica ao meu caso?",
                        "gold_provisions": [KEY_A],
                        "required_provisions": [],
                        "expected_decision": "CLARIFY",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    mapping = tmp_path / "mapping.json"
    mapping.write_text(
        json.dumps(
            {
                "mapping_id": "test/two-mode",
                "dataset_sha256": sha256(dataset.read_bytes()).hexdigest(),
                "category_to_mode": {
                    "SINGLE_SUPPORT": "LEGAL_RULE",
                    "COMPOSITE_SUPPORT": "LEGAL_RULE",
                    "INSUFFICIENT_EVIDENCE": "LEGAL_RULE",
                    "AMBIGUOUS": "CASE_APPLICATION",
                },
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
        output_dir=tmp_path / "v2",
        profile=IntegratedDevProfile.TWO_MODE_V2,
        query_mode_mapping_path=mapping,
    )

    assert len(answerer.calls) == 1
    assert result["metrics"]["legal_rule_cases"] == 1
    assert result["metrics"]["case_application_cases"] == 1
    assert result["metrics"]["case_application_clarify_rate"] == 1
    assert result["metrics"]["case_application_retrieval_calls"] == 0
    assert result["metrics"]["case_application_llm_calls"] == 0
    raw = json.loads((tmp_path / "v2/integrated_dev_raw_v2.json").read_text())
    case = next(item for item in raw["cases"] if item["case_id"] == "CASE")
    assert case["raw_model_response"] is None
    assert case["retrieved_stable_keys"] == []
    assert case["citations"] == []
    assert case["routing_reason"] == "CASE_APPLICATION_NOT_SUPPORTED_IN_MVP2"


def test_empty_retrieval_abstains_without_calling_answerer():
    answerer = FakeAnswerer({})
    result = RunRagQuery(FakeRetriever(()), FakeRepository(), answerer).execute(
        RagQueryRequest("Pergunta?", VERSION, QueryMode.LEGAL_RULE)
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
        ).execute(RagQueryRequest("Pergunta?", VERSION, QueryMode.LEGAL_RULE))
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
    assert "--mode" in ask.output
    assert "required" in ask.output.lower()
    assert "--trace" in ask.output
    assert status.exit_code == 0


def test_rag_cli_rejects_missing_mode_before_external_services():
    result = CliRunner().invoke(app, ["ask", "Pergunta?", "--version-hash", VERSION])
    assert result.exit_code != 0
    assert "--mode" in result.output


def test_case_application_cli_returns_before_database_or_ollama(monkeypatch):
    monkeypatch.setattr(
        "consultor_juridico.cli.main._session_factory",
        lambda: (_ for _ in ()).throw(AssertionError("database accessed")),
    )
    result = CliRunner().invoke(
        app,
        [
            "ask",
            "A autoridade pode fazer isso no meu caso?",
            "--mode",
            "case-application",
            "--version-hash",
            VERSION,
            "--trace",
        ],
    )

    assert result.exit_code == 0
    assert "Decisão: CLARIFY" in result.output
    assert "query_mode=CASE_APPLICATION" in result.output
    assert "retrieval=NOT_EXECUTED" in result.output
    assert "answerer=NOT_EXECUTED" in result.output
    assert "CASE_APPLICATION_NOT_SUPPORTED_IN_MVP2" in result.output
