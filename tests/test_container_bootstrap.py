"""Contratos estáticos dos entrypoints do ambiente containerizado."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_entrypoint_scripts_are_valid_and_executable():
    scripts = (
        ROOT / "docker" / "app-entrypoint.sh",
        ROOT / "docker" / "ollama-entrypoint.sh",
    )

    for script in scripts:
        assert os.access(script, os.X_OK)
        subprocess.run(["sh", "-n", str(script)], check=True)


def test_app_entrypoint_delegates_business_logic_to_python_bootstrap():
    script = (ROOT / "docker" / "app-entrypoint.sh").read_text()

    assert "consultor-juridico bootstrap" in script
    assert 'set -- consultor-juridico "$@"' in script
    assert 'exec "$@"' in script
    assert ".initialized" not in script
    assert "bootstrap-done" not in script


def test_ollama_entrypoint_provisions_configured_models():
    script = (ROOT / "docker" / "ollama-entrypoint.sh").read_text()
    compose = (ROOT / "docker-compose.yml").read_text()

    assert 'ollama pull "$EMBEDDING_MODEL"' in script
    assert 'ollama pull "$SEMANTIC_JUDGE_MODEL"' in script
    assert "ollama_data:/root/.ollama" in compose
    assert "ollama show" in compose
    assert "$$EMBEDDING_MODEL" in compose
    assert "$$SEMANTIC_JUDGE_MODEL" in compose


def test_runtime_exposes_direct_cli_command():
    dockerfile = (ROOT / "Dockerfile").read_text()
    project = (ROOT / "pyproject.toml").read_text()

    assert 'PATH="/app/.venv/bin:$PATH"' in dockerfile
    assert 'ENTRYPOINT ["app-entrypoint.sh"]' in dockerfile
    assert 'consultor-juridico = "consultor_juridico.cli.main:app"' in project
