"""Runner manual Ollama da avaliação Gold Evidence, sem inferência real."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from consultor_juridico.cli import main as cli_main
from consultor_juridico.evaluation.ollama_gold_runner import (
    GENERATION_CONFIG,
    MAX_GENERATION_TIME_SECONDS,
    OllamaGoldRunError,
    OllamaModelNotAvailableError,
    ThinkingMode,
    run_ollama_gold_bundle,
)

MODEL = "qwen3:4b-instruct-2507-q4_K_M"
BASE_URL = "http://ollama.test"


def _write_bundle(path: Path) -> list[dict]:
    records = [
        {
            "case_id": "GOLD-002",
            "category": "INSUFFICIENT_EVIDENCE",
            "expected_decision": "ABSTAIN",
            "required_provisions": [],
            "gold_provisions": [],
            "prompt_name": "gold-evidence-answering",
            "prompt_version": "1",
            "dataset_sha256": "a" * 64,
            "version_hash": "b" * 64,
            "system_prompt": "Instrução genérica",
            "user_prompt": "QUESTION: segunda\nEVIDENCE: nenhuma",
            "evidence": [],
        },
        {
            "case_id": "GOLD-001",
            "category": "SINGLE_SUPPORT",
            "expected_decision": "ANSWER",
            "required_provisions": ["A"],
            "gold_provisions": ["A"],
            "prompt_name": "gold-evidence-answering",
            "prompt_version": "1",
            "dataset_sha256": "a" * 64,
            "version_hash": "b" * 64,
            "system_prompt": "Instrução genérica",
            "user_prompt": "QUESTION: primeira\nEVIDENCE: A",
            "evidence": [],
        },
    ]
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    return records


def _model_payload() -> dict:
    return {
        "models": [
            {
                "name": MODEL,
                "model": MODEL,
                "digest": "digest-123",
                "details": {"quantization_level": "Q4_K_M"},
            }
        ]
    }


def test_runner_sends_only_prompts_and_preserves_raw_output_and_order(tmp_path):
    bundle_path = tmp_path / "bundle.jsonl"
    _write_bundle(bundle_path)
    requests: list[dict] = []
    raw_outputs = ["```json\n{inválido}\n```", "não é JSON"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json=_model_payload())
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.11.0"})
        payload = json.loads(request.content)
        requests.append(payload)
        index = len(requests) - 1
        return httpx.Response(
            200,
            json={
                "message": {"content": raw_outputs[index]},
                "total_duration": (index + 1) * 1_500_000,
                "prompt_eval_count": 100 + index,
                "eval_count": 20 + index,
            },
        )

    output_path = tmp_path / "responses.jsonl"
    metadata_path = tmp_path / "metadata.json"
    times = iter(
        (
            datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
            datetime(2026, 9, 1, 12, 1, tzinfo=UTC),
        )
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = run_ollama_gold_bundle(
            input_path=bundle_path,
            model=MODEL,
            base_url=BASE_URL + "/",
            output_path=output_path,
            metadata_path=metadata_path,
            client=client,
            now=lambda: next(times),
        )

    assert len(requests) == 2
    for request in requests:
        assert set(request) == {"model", "messages", "stream", "options"}
        assert request["model"] == MODEL
        assert request["stream"] is False
        assert request["options"] == GENERATION_CONFIG
        assert [message["role"] for message in request["messages"]] == [
            "system",
            "user",
        ]
        serialized = json.dumps(request, ensure_ascii=False)
        assert "INSUFFICIENT_EVIDENCE" not in serialized
        assert "expected_decision" not in serialized
        assert "required_provisions" not in serialized
        assert "format" not in request

    responses = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [item["case_id"] for item in responses] == ["GOLD-002", "GOLD-001"]
    assert [item["raw_response"] for item in responses] == raw_outputs
    assert [item["latency_ms"] for item in responses] == [1.5, 3.0]
    assert result["status"] == "COMPLETED"
    assert result["provider"] == "ollama"
    assert result["provider_version"] == "0.11.0"
    assert result["model_digest"] == "digest-123"
    assert result["quantization"] == "Q4_K_M"
    assert result["input_bundle_sha256"] == sha256(bundle_path.read_bytes()).hexdigest()
    assert result["completed_case_count"] == 2
    assert result["semantic_retries"] == 0
    assert result["generation_config"]["seed"] == 42
    assert result["thinking_mode"] == "auto"
    assert "ollama_format" not in result
    assert result["max_generation_time_seconds"] == MAX_GENERATION_TIME_SECONDS
    assert result["case_metrics"][0]["prompt_eval_count"] == 100
    assert json.loads(metadata_path.read_text(encoding="utf-8")) == result


@pytest.mark.parametrize("seed", [43, 44])
def test_runner_overrides_only_seed_and_records_it(tmp_path, seed):
    bundle_path = tmp_path / "bundle.jsonl"
    _write_bundle(bundle_path)
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json=_model_payload())
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.11.0"})
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"message": {"content": "{}"}, "total_duration": 1_000_000},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = run_ollama_gold_bundle(
            input_path=bundle_path,
            model=MODEL,
            base_url=BASE_URL,
            output_path=tmp_path / "responses.jsonl",
            metadata_path=tmp_path / "metadata.json",
            client=client,
            seed=seed,
        )

    assert len(requests) == 2
    assert all(
        request["options"] == GENERATION_CONFIG | {"seed": seed} for request in requests
    )
    assert result["generation_config"] == GENERATION_CONFIG | {
        "seed": seed,
        "stream": False,
    }


def test_runner_can_disable_native_thinking_without_changing_prompt(tmp_path):
    bundle_path = tmp_path / "bundle.jsonl"
    _write_bundle(bundle_path)
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json=_model_payload())
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.33.2"})
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"message": {"content": "{}"}, "total_duration": 1_000_000},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = run_ollama_gold_bundle(
            input_path=bundle_path,
            model=MODEL,
            base_url=BASE_URL,
            output_path=tmp_path / "responses.jsonl",
            metadata_path=tmp_path / "metadata.json",
            client=client,
            thinking_mode=ThinkingMode.DISABLED,
        )

    assert len(requests) == 2
    assert all(request["think"] is False for request in requests)
    assert all(
        "think" not in message
        for request in requests
        for message in request["messages"]
    )
    assert result["thinking_mode"] == "disabled"


def test_runner_adds_only_explicit_ollama_format_to_request(tmp_path):
    bundle_path = tmp_path / "bundle.jsonl"
    _write_bundle(bundle_path)
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json=_model_payload())
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.33.2"})
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"message": {"content": "{}"}, "total_duration": 1_000_000},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = run_ollama_gold_bundle(
            input_path=bundle_path,
            model=MODEL,
            base_url=BASE_URL,
            output_path=tmp_path / "responses.jsonl",
            metadata_path=tmp_path / "metadata.json",
            client=client,
            thinking_mode=ThinkingMode.DISABLED,
            ollama_format="json",
        )

    assert len(requests) == 2
    for request in requests:
        assert request["format"] == "json"
        assert request["options"] == GENERATION_CONFIG
        assert request["stream"] is False
        assert request["think"] is False
        assert set(request) == {
            "model",
            "messages",
            "stream",
            "options",
            "think",
            "format",
        }
    assert result["ollama_format"] == "json"


def test_cli_forwards_generic_ollama_format(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_run_ollama_gold_bundle(**kwargs):
        captured.update(kwargs)
        return {
            "run_id": "run-1",
            "status": "COMPLETED",
            "completed_case_count": 0,
        }

    monkeypatch.setattr(cli_main, "run_ollama_gold_bundle", fake_run_ollama_gold_bundle)
    result = CliRunner().invoke(
        cli_main.app,
        [
            "eval",
            "gold",
            "run-ollama",
            "--input",
            str(tmp_path / "input.jsonl"),
            "--model",
            MODEL,
            "--output",
            str(tmp_path / "output.jsonl"),
            "--metadata",
            str(tmp_path / "metadata.json"),
            "--base-url",
            BASE_URL,
            "--ollama-format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert captured["ollama_format"] == "json"
    assert captured["seed"] == 42
    assert captured["thinking_mode"] is ThinkingMode.AUTO


def test_runner_stops_if_disabled_thinking_is_still_returned(tmp_path):
    bundle_path = tmp_path / "bundle.jsonl"
    _write_bundle(bundle_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json=_model_payload())
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.33.2"})
        return httpx.Response(
            200,
            json={
                "message": {"content": "{}", "thinking": "conteúdo separado"},
                "total_duration": 1_000_000,
            },
        )

    output_path = tmp_path / "responses.jsonl"
    metadata_path = tmp_path / "metadata.json"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            OllamaGoldRunError, match="THINKING_CONTENT_RETURNED_WHEN_DISABLED"
        ):
            run_ollama_gold_bundle(
                input_path=bundle_path,
                model=MODEL,
                base_url=BASE_URL,
                output_path=output_path,
                metadata_path=metadata_path,
                client=client,
                thinking_mode=ThinkingMode.DISABLED,
            )

    assert output_path.read_text(encoding="utf-8") == ""
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["status"] == "FAILED"
    assert metadata["completed_case_count"] == 0


def test_runner_fails_before_case_one_when_model_is_not_local(tmp_path):
    bundle_path = tmp_path / "bundle.jsonl"
    _write_bundle(bundle_path)
    post_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_calls
        if request.method == "POST":
            post_calls += 1
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        return httpx.Response(200, json={"version": "0.11.0"})

    output_path = tmp_path / "responses.jsonl"
    metadata_path = tmp_path / "metadata.json"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            OllamaModelNotAvailableError, match="MODEL_NOT_AVAILABLE_LOCALLY"
        ):
            run_ollama_gold_bundle(
                input_path=bundle_path,
                model=MODEL,
                base_url=BASE_URL,
                output_path=output_path,
                metadata_path=metadata_path,
                client=client,
            )
    assert post_calls == 0
    assert not output_path.exists()
    assert not metadata_path.exists()


def test_runner_does_not_retry_transport_failure_and_records_partial_run(tmp_path):
    bundle_path = tmp_path / "bundle.jsonl"
    _write_bundle(bundle_path)
    post_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_calls
        if request.url.path == "/api/tags":
            return httpx.Response(200, json=_model_payload())
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.11.0"})
        post_calls += 1
        raise httpx.ConnectError("offline", request=request)

    output_path = tmp_path / "responses.jsonl"
    metadata_path = tmp_path / "metadata.json"
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OllamaGoldRunError, match="nenhum retry"):
            run_ollama_gold_bundle(
                input_path=bundle_path,
                model=MODEL,
                base_url=BASE_URL,
                output_path=output_path,
                metadata_path=metadata_path,
                client=client,
            )
    assert post_calls == 1
    assert output_path.read_text(encoding="utf-8") == ""
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["status"] == "FAILED"
    assert metadata["completed_case_count"] == 0
    assert metadata["semantic_retries"] == 0


@pytest.mark.parametrize("existing", ["output", "metadata"])
def test_runner_refuses_to_overwrite_artifacts(tmp_path, existing):
    bundle_path = tmp_path / "bundle.jsonl"
    _write_bundle(bundle_path)
    output_path = tmp_path / "responses.jsonl"
    metadata_path = tmp_path / "metadata.json"
    target = output_path if existing == "output" else metadata_path
    target.write_text("preservar", encoding="utf-8")
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(500))
    ) as client:
        with pytest.raises(FileExistsError, match="não pode ser sobrescrito"):
            run_ollama_gold_bundle(
                input_path=bundle_path,
                model=MODEL,
                base_url=BASE_URL,
                output_path=output_path,
                metadata_path=metadata_path,
                client=client,
            )
    assert target.read_text(encoding="utf-8") == "preservar"


def test_cross_model_manifest_freezes_inputs_and_generation_contract():
    repository_root = Path(__file__).resolve().parents[1]
    manifest_path = (
        repository_root / "evaluation/runs/gold_evidence_cross_model_manifest_v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["status"] == "FROZEN_BEFORE_FIRST_CANDIDATE_RUN"
    assert manifest["candidate_order"] == [
        "qwen3.5:9b",
        "phi4-mini:3.8b-q4_K_M",
        "gemma3:4b",
        "gemma4:12b",
    ]
    assert manifest["generation"] == {
        "full_run_seed": 42,
        "stability_seeds": [42, 43, 44],
        "risk_02_probe_seeds": [42, 43, 44],
        "options": {
            key: value for key, value in GENERATION_CONFIG.items() if key != "seed"
        },
        "stream": False,
        "max_generation_time_seconds": MAX_GENERATION_TIME_SECONDS,
        "semantic_retries": 0,
        "one_generation_per_case": True,
        "regime": "DIRECT_ANSWER",
    }
    for input_contract in manifest["inputs"].values():
        input_path = repository_root / input_contract["path"]
        assert sha256(input_path.read_bytes()).hexdigest() == input_contract["sha256"]
    dataset_path = repository_root / manifest["dataset"]["path"]
    assert (
        sha256(dataset_path.read_bytes()).hexdigest() == manifest["dataset"]["sha256"]
    )


def test_gemma4_format_json_runbook_uses_seven_isolated_output_paths():
    repository_root = Path(__file__).resolve().parents[1]
    runbook = (
        repository_root / "docs/evaluation/gemma4-format-json-reconsideration-v1.md"
    ).read_text(encoding="utf-8")
    expected_outputs = {
        "gemma4_12b_prompt_v2_format_json_reconsideration_v1_full_responses.jsonl",
        "gemma4_12b_prompt_v2_format_json_reconsideration_v1_stability_seed42_responses.jsonl",
        "gemma4_12b_prompt_v2_format_json_reconsideration_v1_stability_seed43_responses.jsonl",
        "gemma4_12b_prompt_v2_format_json_reconsideration_v1_stability_seed44_responses.jsonl",
        "gemma4_12b_prompt_v2_format_json_reconsideration_v1_gold012_seed42_responses.jsonl",
        "gemma4_12b_prompt_v2_format_json_reconsideration_v1_gold012_seed43_responses.jsonl",
        "gemma4_12b_prompt_v2_format_json_reconsideration_v1_gold012_seed44_responses.jsonl",
    }

    assert runbook.count("--ollama-format json") == 7
    assert all(path in runbook for path in expected_outputs)
    assert (
        "--output evaluation/runs/gemma4_12b_prompt_v2_full_responses.jsonl"
        not in runbook
    )
