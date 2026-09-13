"""Contrato estrutural do pacote HOLDOUT, sem runtime, corpus ou LLM."""

import json
from hashlib import sha256
from pathlib import Path

import pytest
from typer.testing import CliRunner

from consultor_juridico.cli.main import app
from consultor_juridico.evaluation.holdout_custody import validate_holdout_package


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _package(tmp_path: Path, *, extra_mapping_id: bool = False):
    dataset = tmp_path / "blind_holdout_mvp2_v1.json"
    _write_json(
        dataset,
        {
            "schema_id": "blind-holdout-dataset/1",
            "dataset_id": "private-test",
            "legal_act_code": "ACT-TEST",
            "cases": [
                {
                    "case_id": "HOLDOUT-001",
                    "question": "Conteúdo privado que não deve aparecer no log",
                    "expected_decision": "ANSWER",
                    "category": "SINGLE_SUPPORT",
                    "gold_provisions": ["KEY-1"],
                    "required_provisions": ["KEY-1"],
                }
            ],
        },
    )
    dataset_hash = sha256(dataset.read_bytes()).hexdigest()
    mapping = tmp_path / "blind_holdout_query_mode_mapping_v1.json"
    case_modes = {"HOLDOUT-001": "LEGAL_RULE"}
    if extra_mapping_id:
        case_modes["HOLDOUT-999"] = "CASE_APPLICATION"
    _write_json(
        mapping,
        {
            "schema_id": "blind-holdout-query-mode-mapping/1",
            "mapping_id": "blind-holdout-query-mode-mapping/1",
            "dataset_sha256": dataset_hash,
            "case_modes": case_modes,
        },
    )
    manifest = tmp_path / "blind_holdout_manifest_v1.json"
    _write_json(
        manifest,
        {
            "schema_id": "blind-holdout-manifest/1",
            "manifest_id": "blind-holdout-manifest/1",
            "created_at": "2026-09-13T00:00:00Z",
            "custodian": "USER",
            "dataset_path": ("evaluation/holdout/private/blind_holdout_mvp2_v1.json"),
            "dataset_sha256": dataset_hash,
            "query_mode_mapping_path": (
                "evaluation/holdout/private/blind_holdout_query_mode_mapping_v1.json"
            ),
            "query_mode_mapping_sha256": sha256(mapping.read_bytes()).hexdigest(),
            "case_count": 1,
            "dataset_schema_id": "blind-holdout-dataset/1",
            "query_mode_mapping_schema_id": ("blind-holdout-query-mode-mapping/1"),
            "runtime_freeze_id": "integrated-runtime-mvp2/1",
            "runtime_freeze_sha256": (
                "5f0df6b41f0d35fcba0a514777a2370385620007ff3e6122473ca6793067514d"
            ),
            "baseline_git_commit": "ea888a5f70d570e0ab4d505e4b3f5d695eb78cd5",
            "sealed_at": "2026-09-13T00:01:00Z",
            "holdout_read_by_runtime": False,
        },
    )
    return dataset, mapping, manifest


def test_structural_validator_accepts_sealed_package(tmp_path):
    dataset, mapping, manifest = _package(tmp_path)
    result = validate_holdout_package(
        dataset_path=dataset, mapping_path=mapping, manifest_path=manifest
    )
    assert result.case_count == 1
    assert result.mapping_id == "blind-holdout-query-mode-mapping/1"


def test_structural_validator_requires_one_to_one_mapping(tmp_path):
    dataset, mapping, manifest = _package(tmp_path, extra_mapping_id=True)
    with pytest.raises(ValueError, match="relação 1:1"):
        validate_holdout_package(
            dataset_path=dataset, mapping_path=mapping, manifest_path=manifest
        )


def test_structural_validator_rejects_runtime_read_or_wrong_hash(tmp_path):
    dataset, mapping, manifest = _package(tmp_path)
    payload = json.loads(manifest.read_text())
    payload["holdout_read_by_runtime"] = True
    payload["dataset_sha256"] = "0" * 64
    _write_json(manifest, payload)
    with pytest.raises(ValueError):
        validate_holdout_package(
            dataset_path=dataset, mapping_path=mapping, manifest_path=manifest
        )


def test_cli_validator_does_not_log_case_content(tmp_path):
    dataset, mapping, manifest = _package(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "eval",
            "holdout-validate",
            "--dataset",
            str(dataset),
            "--query-mode-mapping",
            str(mapping),
            "--manifest",
            str(manifest),
        ],
    )
    assert result.exit_code == 0
    assert "HOLDOUT_PACKAGE_VALID=YES" in result.output
    assert "Conteúdo privado" not in result.output

    payload = json.loads(dataset.read_text())
    payload["cases"][0]["expected_decision"] = "Conteúdo privado inválido"
    _write_json(dataset, payload)
    failed = CliRunner().invoke(
        app,
        [
            "eval",
            "holdout-validate",
            "--dataset",
            str(dataset),
            "--query-mode-mapping",
            str(mapping),
            "--manifest",
            str(manifest),
        ],
    )
    assert failed.exit_code == 1
    assert failed.output.strip() == "HOLDOUT_PACKAGE_VALID=NO"
    assert "Conteúdo privado" not in failed.output


def test_public_holdout_schemas_and_templates_are_valid_json():
    paths = tuple(Path("evaluation/holdout/schema").glob("*.json")) + tuple(
        Path("evaluation/holdout/templates").glob("*.json")
    )
    assert len(paths) == 6
    for path in paths:
        assert json.loads(path.read_text(encoding="utf-8"))
