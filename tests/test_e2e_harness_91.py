from pathlib import Path

import pytest

from evaluation.e2e_single_model_91 import prepare_output_path


def test_e2e_harness_creates_explicit_output_parent(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "result.json"

    assert prepare_output_path(output) == output
    assert output.parent.is_dir()


def test_e2e_harness_rejects_existing_output_before_inference(tmp_path: Path) -> None:
    output = tmp_path / "existing.json"
    output.write_text("frozen", encoding="utf-8")

    with pytest.raises(FileExistsError, match="OUTPUT_ALREADY_EXISTS"):
        prepare_output_path(output)
