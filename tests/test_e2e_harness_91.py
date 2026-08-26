from pathlib import Path

import pytest

from consultor_juridico.consultation import EvidenceBoundControlledGenerator
from evaluation.e2e_single_model_91 import (
    GENERATION_MODE,
    PHASE,
    main,
    prepare_output_path,
)


def test_ebcg_harness_metadata_describes_the_real_pipeline() -> None:
    assert PHASE == "96"
    assert GENERATION_MODE == "EBCG_V2"


def test_e2e_harness_creates_explicit_output_parent(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "result.json"

    assert prepare_output_path(output) == output
    assert output.parent.is_dir()


def test_e2e_harness_rejects_existing_output_before_inference(tmp_path: Path) -> None:
    output = tmp_path / "existing.json"
    output.write_text("frozen", encoding="utf-8")

    with pytest.raises(FileExistsError, match="OUTPUT_ALREADY_EXISTS"):
        prepare_output_path(output)


def test_e2e_harness_uses_ebcg_without_constructing_an_ollama_generator(
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

    main(tmp_path / "result.json")

    assert isinstance(captured["generator"], EvidenceBoundControlledGenerator)
