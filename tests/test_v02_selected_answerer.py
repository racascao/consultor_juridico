"""Validação determinística do freeze do answerer selecionado."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from typer.testing import CliRunner

from consultor_juridico.cli import main as cli_main
from consultor_juridico.evaluation.selected_answerer import (
    DEFAULT_FREEZE_PATH,
    FREEZE_ID,
    SELECTED_MODEL,
    SELECTED_MODEL_DIGEST,
    load_selected_answerer_freeze,
    validate_selected_answerer_freeze,
)


@pytest.fixture
def frozen_payload() -> dict:
    return load_selected_answerer_freeze()


def _modified_freeze(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "freeze.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_canonical_freeze_is_valid_without_external_services():
    report = validate_selected_answerer_freeze()

    assert report.valid
    assert report.freeze_id == FREEZE_ID
    assert report.model == SELECTED_MODEL
    assert report.model_digest == SELECTED_MODEL_DIGEST
    assert report.prompt_identity == "gold-evidence-answering/2"
    assert report.ollama_format == "json"
    assert all(report.checks.values())


@pytest.mark.parametrize(
    ("mutation", "failed_check"),
    [
        (lambda value: value.update({"model": "outro:1b"}), "model_match"),
        (
            lambda value: value.update({"model_digest": "0" * 64}),
            "model_digest_match",
        ),
        (
            lambda value: value["prompt"].update({"version": "3"}),
            "prompt_identity_match",
        ),
        (
            lambda value: value["prompt"].update({"sha256": "0" * 64}),
            "prompt_sha256_match",
        ),
        (
            lambda value: value["generation_config"].update({"temperature": 0}),
            "generation_config_match",
        ),
        (
            lambda value: value.update({"ollama_format": None}),
            "ollama_format_match",
        ),
    ],
)
def test_validator_detects_identity_drift(
    tmp_path, frozen_payload, mutation, failed_check
):
    payload = deepcopy(frozen_payload)
    mutation(payload)

    report = validate_selected_answerer_freeze(_modified_freeze(tmp_path, payload))

    assert not report.valid
    assert report.checks[failed_check] is False


def test_validator_detects_selection_artifact_drift(tmp_path, frozen_payload):
    payload = deepcopy(frozen_payload)
    payload["artifacts"]["dataset"]["sha256"] = "0" * 64

    report = validate_selected_answerer_freeze(_modified_freeze(tmp_path, payload))

    assert not report.valid
    assert report.checks["artifact_hashes_match"] is False


def test_validator_has_no_network_or_inference_dependency(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("rede ou inferência não deve ser usada")

    monkeypatch.setattr("httpx.get", forbidden)
    monkeypatch.setattr("httpx.post", forbidden)

    assert validate_selected_answerer_freeze().valid


def test_selected_answerer_status_cli_is_read_only_and_valid():
    result = CliRunner().invoke(
        cli_main.app,
        ["eval", "gold", "selected-answerer-status"],
    )

    assert result.exit_code == 0
    assert f"FREEZE_ID: {FREEZE_ID}" in result.output
    assert f"MODEL: {SELECTED_MODEL}" in result.output
    assert "MODEL_DIGEST_MATCH: YES" in result.output
    assert "PROMPT_MATCH: YES" in result.output
    assert "GENERATION_CONFIG_MATCH: YES" in result.output
    assert "OLLAMA_FORMAT: json" in result.output
    assert "SELECTION_EVIDENCE_MATCH: YES" in result.output
    assert "HOLDOUT_READ: NO" in result.output
    assert "STATUS: VALID" in result.output


def test_freeze_file_is_versioned_at_canonical_path():
    assert DEFAULT_FREEZE_PATH == Path(
        "evaluation/model_selection/gold_evidence_selected_answerer_freeze_v1.json"
    )
    assert DEFAULT_FREEZE_PATH.is_file()


def test_freeze_preserves_baseline_artifact_identities(frozen_payload):
    artifacts = frozen_payload["artifacts"]

    assert artifacts["baseline_full_raw"]["sha256"] == (
        "701f9fd3036028f41ba6f70c838ac63cdaed1a31c93b7888e05153fc99ea6879"
    )
    assert artifacts["baseline_full_final_review"]["sha256"] == (
        "3a5636758bbaf01dcc470fae6958d6004175a3246da7ae160a52d991b2126e7a"
    )
    assert artifacts["baseline_gold012_material_review"]["sha256"] == (
        "0e2df88f572310793e36015352b208ea329e8ba418c355627538bde1053ee4a9"
    )
    assert artifacts["baseline_risk_scorecard"]["sha256"] == (
        "48cbaa086403d52ecde10dcf0cbedbb99ddaad6e2b796ef2d1b04109f84485bd"
    )
