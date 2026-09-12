"""Replay read-only de Gold Evidence já materializada e congelada."""

import json
from hashlib import sha256
from pathlib import Path

import pytest
from typer.testing import CliRunner

from consultor_juridico.application.gold_evidence.prompt import (
    PROMPT_NAME,
    PROMPT_VERSION_V2,
    build_user_prompt,
    system_prompt_for,
)
from consultor_juridico.application.gold_evidence.types import GoldEvidenceItem
from consultor_juridico.cli import main as cli_main
from consultor_juridico.evaluation.frozen_gold_bundle import (
    FrozenGoldBundleRepository,
    IncompleteFrozenCitationNamespaceError,
)
from consultor_juridico.evaluation.gold_evidence import validate_gold_responses

VERSION_HASH = "a" * 64
SNAPSHOT_SHA256 = "b" * 64
FROZEN_DATASET = Path("evaluation/datasets/lei_9784_gold_evidence_dev_v1.json")
FROZEN_BUNDLE = Path("evaluation/runs/gold_evidence_input_prompt_v2.jsonl")
FROZEN_BUNDLE_SHA256 = (
    "dd91a0d68f5e7e78ec9739b8fcde333308362a246d934c5a38da6810af3bdd98"
)
HISTORICAL_RESPONSES = Path(
    "evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_responses.jsonl"
)
HISTORICAL_ORACLE = Path(
    "evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_automatic_evaluation.json"
)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _frozen_fixture(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    dataset_path = tmp_path / "dataset.json"
    dataset = {
        "dataset_id": "gold_test_v1",
        "legal_act_code": "ACT",
        "cases": [
            {
                "case_id": "GOLD-001",
                "category": "SINGLE_SUPPORT",
                "question": "Qual é a regra?",
                "gold_provisions": ["ARTICLE:1/CAPUT"],
                "required_provisions": ["ARTICLE:1/CAPUT"],
                "expected_decision": "ANSWER",
            }
        ],
    }
    _write_json(dataset_path, dataset)
    item = GoldEvidenceItem(
        stable_key="ARTICLE:1/CAPUT",
        provision_type="CAPUT",
        citation_text="Art. 1º Texto oficial.",
        source_locator={"paragraph_start": 1, "paragraph_end": 1},
        source_snapshot_sha256=SNAPSHOT_SHA256,
        official_url="https://example.test/lei",
        document_order=1,
    )
    bundle_path = tmp_path / "bundle.jsonl"
    record = {
        "case_id": "GOLD-001",
        "category": "SINGLE_SUPPORT",
        "expected_decision": "ANSWER",
        "required_provisions": ["ARTICLE:1/CAPUT"],
        "gold_provisions": ["ARTICLE:1/CAPUT"],
        "prompt_name": PROMPT_NAME,
        "prompt_version": PROMPT_VERSION_V2,
        "dataset_sha256": sha256(dataset_path.read_bytes()).hexdigest(),
        "version_hash": VERSION_HASH,
        "system_prompt": system_prompt_for(PROMPT_VERSION_V2),
        "user_prompt": build_user_prompt("Qual é a regra?", (item,)),
        "evidence": [
            {
                "stable_key": item.stable_key,
                "provision_type": item.provision_type,
                "citation_text": item.citation_text,
                "source_locator": item.source_locator,
                "source_snapshot_sha256": item.source_snapshot_sha256,
                "official_url": item.official_url,
                "document_order": item.document_order,
            }
        ],
    }
    bundle_path.write_text(
        json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    responses_path = tmp_path / "responses.jsonl"
    response = {
        "case_id": "GOLD-001",
        "raw_response": json.dumps(
            {
                "decision": "ANSWER",
                "answer": "Texto oficial.",
                "citations": ["ARTICLE:1/CAPUT"],
            }
        ),
        "latency_ms": 1.0,
    }
    responses_path.write_text(json.dumps(response) + "\n", encoding="utf-8")
    return (
        dataset_path,
        bundle_path,
        responses_path,
        sha256(bundle_path.read_bytes()).hexdigest(),
    )


def _repository(dataset: Path, bundle: Path, digest: str):
    return FrozenGoldBundleRepository(
        dataset_path=dataset,
        bundle_path=bundle,
        expected_bundle_sha256=digest,
    )


def _mutate_bundle(bundle_path: Path, mutation) -> None:
    records = [json.loads(line) for line in bundle_path.read_text().splitlines()]
    mutation(records)
    bundle_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )


def test_frozen_repository_materializes_valid_bundle(tmp_path):
    dataset, bundle, _, digest = _frozen_fixture(tmp_path)
    repository = _repository(dataset, bundle, digest)
    evidence = repository.materialize(VERSION_HASH, ("ARTICLE:1/CAPUT",))
    assert repository.citation_namespace_complete is False
    assert repository.context(VERSION_HASH).source_snapshot_sha256 == SNAPSHOT_SHA256
    assert repository.provision_keys(VERSION_HASH) == {"ARTICLE:1/CAPUT"}
    assert [item.stable_key for item in evidence] == ["ARTICLE:1/CAPUT"]


def test_frozen_repository_rejects_wrong_bundle_sha(tmp_path):
    dataset, bundle, _, _ = _frozen_fixture(tmp_path)
    with pytest.raises(ValueError, match="SHA-256 do Gold bundle diverge"):
        _repository(dataset, bundle, "0" * 64)


def test_frozen_repository_rejects_invalid_jsonl(tmp_path):
    dataset, bundle, _, _ = _frozen_fixture(tmp_path)
    bundle.write_text("{invalid\n", encoding="utf-8")
    digest = sha256(bundle.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="JSONL inválido"):
        _repository(dataset, bundle, digest)


def test_frozen_repository_rejects_duplicate_case_id(tmp_path):
    dataset, bundle, _, _ = _frozen_fixture(tmp_path)
    bundle.write_text(bundle.read_text() * 2, encoding="utf-8")
    digest = sha256(bundle.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="case_id duplicado"):
        _repository(dataset, bundle, digest)


def test_frozen_repository_rejects_missing_case(tmp_path):
    dataset, bundle, _, _ = _frozen_fixture(tmp_path)
    bundle.write_text("", encoding="utf-8")
    digest = sha256(bundle.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="Gold bundle vazio"):
        _repository(dataset, bundle, digest)


def test_frozen_repository_rejects_bundle_missing_dataset_case(tmp_path):
    dataset, bundle, _, _ = _frozen_fixture(tmp_path)
    payload = json.loads(dataset.read_text())
    payload["cases"].append(
        {
            "case_id": "GOLD-002",
            "category": "INSUFFICIENT_EVIDENCE",
            "question": "Há evidência?",
            "gold_provisions": [],
            "required_provisions": [],
            "expected_decision": "ABSTAIN",
        }
    )
    _write_json(dataset, payload)
    records = [json.loads(line) for line in bundle.read_text().splitlines()]
    records[0]["dataset_sha256"] = sha256(dataset.read_bytes()).hexdigest()
    bundle.write_text(json.dumps(records[0]) + "\n", encoding="utf-8")
    digest = sha256(bundle.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="não representa integralmente"):
        _repository(dataset, bundle, digest)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda records: records[0].update({"category": "AMBIGUOUS"}),
            "Dataset diverge",
        ),
        (
            lambda records: records[0].update({"required_provisions": []}),
            "Dataset diverge",
        ),
        (
            lambda records: records[0].update({"evidence": []}),
            "JSONL inválido",
        ),
    ],
)
def test_frozen_repository_rejects_dataset_or_evidence_divergence(
    tmp_path, mutation, message
):
    dataset, bundle, _, _ = _frozen_fixture(tmp_path)
    _mutate_bundle(bundle, mutation)
    digest = sha256(bundle.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match=message):
        _repository(dataset, bundle, digest)


def test_frozen_namespace_allows_known_and_malformed_but_blocks_plausible_unknown(
    tmp_path,
):
    dataset, bundle, _, digest = _frozen_fixture(tmp_path)
    repository = _repository(dataset, bundle, digest)
    repository.validate_citation_namespace(frozenset({"ARTICLE:1/CAPUT"}))
    repository.validate_citation_namespace(frozenset({"EVIDENCE_ID: ARTICLE:1/CAPUT"}))
    with pytest.raises(
        IncompleteFrozenCitationNamespaceError,
        match="INCOMPLETE_FROZEN_CITATION_NAMESPACE",
    ):
        repository.validate_citation_namespace(frozenset({"ARTICLE:999/CAPUT"}))


def test_offline_cli_never_requests_sqlalchemy_session(tmp_path, monkeypatch):
    dataset, bundle, responses, digest = _frozen_fixture(tmp_path)

    def fail_if_called():
        raise AssertionError("offline mode must not initialize PostgreSQL")

    monkeypatch.setattr(cli_main, "_session_factory", fail_if_called)
    output = tmp_path / "automatic.json"
    result = CliRunner().invoke(
        cli_main.app,
        [
            "eval",
            "gold",
            "validate-responses",
            "--dataset",
            str(dataset),
            "--version-hash",
            VERSION_HASH,
            "--responses",
            str(responses),
            "--output",
            str(output),
            "--prompt-version",
            PROMPT_VERSION_V2,
            "--gold-evidence-source",
            "frozen-bundle",
            "--gold-bundle",
            str(bundle),
            "--gold-bundle-sha256",
            digest,
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text())["cases"][0]["automatic_pass"] is True


def test_frozen_evaluator_blocks_incomplete_citation_namespace(tmp_path):
    dataset, bundle, responses, digest = _frozen_fixture(tmp_path)
    response = json.loads(responses.read_text())
    payload = json.loads(response["raw_response"])
    payload["citations"] = ["ARTICLE:999/CAPUT"]
    response["raw_response"] = json.dumps(payload)
    responses.write_text(json.dumps(response) + "\n", encoding="utf-8")
    with pytest.raises(IncompleteFrozenCitationNamespaceError):
        validate_gold_responses(
            _repository(dataset, bundle, digest),
            dataset_path=dataset,
            version_hash=VERSION_HASH,
            responses_path=responses,
            output_path=tmp_path / "automatic.json",
            prompt_version=PROMPT_VERSION_V2,
        )


def test_frozen_evaluator_preserves_known_citation_semantics(tmp_path):
    dataset, bundle, responses, digest = _frozen_fixture(tmp_path)
    result, _ = validate_gold_responses(
        _repository(dataset, bundle, digest),
        dataset_path=dataset,
        version_hash=VERSION_HASH,
        responses_path=responses,
        output_path=tmp_path / "automatic.json",
        prompt_version=PROMPT_VERSION_V2,
    )
    assert result["cases"][0]["automatic_pass"] is True


def test_historical_qwen_v2_offline_replay_matches_db_oracle_32_of_32(tmp_path):
    repository = _repository(
        FROZEN_DATASET,
        FROZEN_BUNDLE,
        FROZEN_BUNDLE_SHA256,
    )
    result, _ = validate_gold_responses(
        repository,
        dataset_path=FROZEN_DATASET,
        version_hash=repository.context(
            "298028477a55a61cdd1df94bda3aec784e6fe94d17c485ae6a2f6c77fe2b7a74"
        ).version_hash,
        responses_path=HISTORICAL_RESPONSES,
        output_path=tmp_path / "automatic.json",
        prompt_version=PROMPT_VERSION_V2,
    )
    oracle = json.loads(HISTORICAL_ORACLE.read_text(encoding="utf-8"))
    result_metadata = {
        k: v for k, v in result["metadata"].items() if k != "evaluated_at"
    }
    oracle_metadata = {
        k: v for k, v in oracle["metadata"].items() if k != "evaluated_at"
    }
    assert result_metadata == oracle_metadata
    assert result["cases"] == oracle["cases"]
    assert len(result["cases"]) == 32
