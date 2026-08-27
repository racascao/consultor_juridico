from pathlib import Path

import pytest

from consultor_juridico.config import settings
from consultor_juridico.consultation import EvidenceBoundControlledGenerator
from evaluation.e2e_single_model_91 import (
    DATASETS,
    GENERATION_MODE,
    build_parser,
    main,
    prepare_output_path,
    resolve_dataset,
    verify_dataset_hash,
)

V1_SHA256 = "c6b496d20dd9b7b5952f7abecca92e64c0179ce134794f5e3b39e579025f441f"
V2_SHA256 = "a6ef0c9e0f3a95a44637c80d061c854a9848aaea5aad1443e7f9f0ee9b710a89"


def test_ebcg_harness_metadata_describes_the_real_pipeline() -> None:
    assert GENERATION_MODE == "EBCG_V2"
    assert set(DATASETS) == {"v1", "v2"}


def test_v1_resolves_to_the_historical_dataset_and_hash() -> None:
    dataset = resolve_dataset("v1")

    assert dataset.path.name == "real_world_short_v1.json"
    assert dataset.sha256 == V1_SHA256
    assert dataset.phase == "96"


def test_v2_resolves_to_the_release_dataset_and_hash() -> None:
    dataset = resolve_dataset("v2")

    assert dataset.path.name == "real_world_short_v2.json"
    assert dataset.sha256 == V2_SHA256
    assert dataset.phase == "MVP1_FINAL"
    assert dataset.evaluation_context == "MVP1_FINAL_NATIVE_V2"


def test_frozen_dataset_hashes_match_files() -> None:
    assert verify_dataset_hash(resolve_dataset("v1")) == V1_SHA256
    assert verify_dataset_hash(resolve_dataset("v2")) == V2_SHA256


def test_unknown_dataset_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="dataset-version desconhecida"):
        resolve_dataset("unknown")


def test_argparse_rejects_unknown_dataset_version() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["--dataset-version", "unknown", "--output", "result.json"]
        )


def test_argparse_requires_dataset_version() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--output", "result.json"])


def test_e2e_harness_creates_explicit_output_parent(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "result.json"

    assert prepare_output_path(output) == output
    assert output.parent.is_dir()


def test_e2e_harness_rejects_existing_output_before_inference(tmp_path: Path) -> None:
    output = tmp_path / "existing.json"
    output.write_text("frozen", encoding="utf-8")

    with pytest.raises(FileExistsError, match="OUTPUT_ALREADY_EXISTS"):
        prepare_output_path(output)


def test_hash_mismatch_aborts_before_provider_or_inference(
    monkeypatch, tmp_path: Path
) -> None:
    calls = []
    monkeypatch.setattr(
        "evaluation.e2e_single_model_91.verify_dataset_hash",
        lambda _dataset: (_ for _ in ()).throw(RuntimeError("hash divergente")),
    )
    monkeypatch.setattr(
        "evaluation.e2e_single_model_91.OllamaEmbeddingProvider",
        lambda *_args: calls.append("provider"),
    )
    monkeypatch.setattr(
        "evaluation.e2e_single_model_91.evaluate_real_world",
        lambda *_args: calls.append("evaluate"),
    )

    with pytest.raises(RuntimeError, match="hash divergente"):
        main(tmp_path / "result.json", dataset_version="v2")

    assert calls == []


def test_e2e_harness_uses_ebcg_and_writes_versioned_metadata(
    monkeypatch, tmp_path: Path
) -> None:
    captured = {}
    monkeypatch.setattr(
        "evaluation.e2e_single_model_91.OllamaEmbeddingProvider",
        lambda *_args: object(),
    )
    monkeypatch.setattr(
        "evaluation.e2e_single_model_91.OllamaSemanticSupportValidator",
        lambda *_args: object(),
    )

    def fake_evaluate(_cases, _provider, generator, _semantic, _model, _embedding):
        captured["generator"] = generator
        return {"cases": 0}

    monkeypatch.setattr(
        "evaluation.e2e_single_model_91.evaluate_real_world", fake_evaluate
    )
    output = tmp_path / "result.json"

    main(output, dataset_version="v2")

    payload = __import__("json").loads(output.read_text(encoding="utf-8"))
    assert isinstance(captured["generator"], EvidenceBoundControlledGenerator)
    assert payload["dataset_version"] == "v2"
    assert payload["dataset"] == "real_world_short_v2.json"
    assert payload["dataset_sha256"] == V2_SHA256
    assert payload["phase"] == "MVP1_FINAL"
    assert payload["evaluation_context"] == "MVP1_FINAL_NATIVE_V2"
    assert payload["configuration"]["generator_model"] is None
    assert payload["configuration"]["semantic_model"] == (
        settings.semantic_judge_model or settings.ollama_model
    )
    assert payload["configuration"]["embedding_model"] == settings.embedding_model
