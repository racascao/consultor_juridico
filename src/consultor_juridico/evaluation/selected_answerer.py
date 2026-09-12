"""Freeze determinístico do answerer selecionado na avaliação Gold Evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from consultor_juridico.application.gold_evidence.prompt import (
    PROMPT_NAME,
    PROMPT_VERSION_V2,
    system_prompt_for,
)
from consultor_juridico.evaluation.ollama_gold_runner import (
    GENERATION_CONFIG,
    MAX_GENERATION_TIME_SECONDS,
)

FREEZE_ID = "gold-evidence-selected-answerer/1"
SELECTED_MODEL = "gemma4:12b"
SELECTED_MODEL_DIGEST = (
    "4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c"
)
SELECTED_OLLAMA_FORMAT = "json"
SELECTED_THINKING_MODE = "disabled"
DEFAULT_FREEZE_PATH = Path(
    "evaluation/model_selection/gold_evidence_selected_answerer_freeze_v1.json"
)

_EXPECTED_GENERATION_CONFIG = {
    key: value for key, value in GENERATION_CONFIG.items() if key != "seed"
} | {
    "stream": False,
    "timeout_seconds": int(MAX_GENERATION_TIME_SECONDS),
}

_EXPECTED_OUTPUT_CONTRACT = {
    "type": "JSON_OBJECT",
    "required_fields": ["decision", "answer", "citations"],
    "allowed_decisions": ["ANSWER", "ABSTAIN", "CLARIFY"],
    "citations": "ARRAY_OF_AUTHORIZED_STABLE_KEYS",
    "additional_fields_allowed": False,
    "markdown_fences_allowed": False,
    "surrounding_text_allowed": False,
    "post_generation_repair": False,
    "fence_stripping": False,
    "automatic_field_renaming": False,
    "format_error_retry": False,
    "failure_policy": "FAIL_CLOSED",
}


@dataclass(frozen=True)
class SelectedAnswererFreezeReport:
    """Resultado auditável da validação local do freeze."""

    freeze_id: str
    model: str
    model_digest: str
    prompt_identity: str
    ollama_format: str
    checks: dict[str, bool]

    @property
    def valid(self) -> bool:
        return all(self.checks.values())


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _prompt_sha256() -> str:
    prompt = system_prompt_for(PROMPT_VERSION_V2)
    return sha256(prompt.encode("utf-8")).hexdigest()


def load_selected_answerer_freeze(
    path: Path = DEFAULT_FREEZE_PATH,
) -> dict[str, Any]:
    """Carrega o freeze explícito sem rede, banco ou inferência."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("SELECTED_ANSWERER_FREEZE_NOT_AN_OBJECT")
    return payload


def validate_selected_answerer_freeze(
    path: Path = DEFAULT_FREEZE_PATH,
    *,
    project_root: Path | None = None,
) -> SelectedAnswererFreezeReport:
    """Detecta drift do freeze contra código e artefatos locais congelados."""
    root = project_root or _project_root()
    resolved_path = path if path.is_absolute() else root / path
    payload = load_selected_answerer_freeze(resolved_path)
    prompt = payload.get("prompt", {})
    generation = payload.get("generation_config", {})
    runtime = payload.get("runtime", {})
    artifacts = payload.get("artifacts", {})

    artifact_hashes_match = bool(artifacts)
    if artifact_hashes_match:
        for artifact in artifacts.values():
            artifact_path = root / artifact.get("path", "")
            expected_hash = artifact.get("sha256")
            if (
                not artifact_path.is_file()
                or not isinstance(expected_hash, str)
                or _sha256(artifact_path) != expected_hash
            ):
                artifact_hashes_match = False
                break

    checks = {
        "freeze_id_match": payload.get("freeze_id") == FREEZE_ID,
        "selection_status_match": payload.get("selection_status") == "FROZEN",
        "model_match": payload.get("model") == SELECTED_MODEL,
        "model_digest_match": payload.get("model_digest") == SELECTED_MODEL_DIGEST,
        "prompt_identity_match": prompt.get("name") == PROMPT_NAME
        and prompt.get("version") == PROMPT_VERSION_V2
        and prompt.get("identity") == f"{PROMPT_NAME}/{PROMPT_VERSION_V2}",
        "prompt_sha256_match": prompt.get("sha256") == _prompt_sha256(),
        "generation_config_match": generation == _EXPECTED_GENERATION_CONFIG,
        "thinking_mode_match": payload.get("thinking_mode") == SELECTED_THINKING_MODE,
        "ollama_format_match": payload.get("ollama_format") == SELECTED_OLLAMA_FORMAT,
        "output_contract_match": payload.get("output_contract")
        == _EXPECTED_OUTPUT_CONTRACT,
        "runtime_match": runtime.get("provider") == "ollama"
        and runtime.get("deployment") == "DOCKER_COMPOSE_ONLY"
        and runtime.get("internal_service_url") == "http://ollama:11434"
        and runtime.get("host_cli_url") == "http://localhost:11435"
        and runtime.get("host_native_ollama_allowed") is False,
        "artifact_hashes_match": artifact_hashes_match,
        "holdout_closed": payload.get("holdout", {}).get("read") is False,
        "rag_not_started": payload.get("rag_integration") == "NOT_STARTED",
    }
    return SelectedAnswererFreezeReport(
        freeze_id=str(payload.get("freeze_id", "")),
        model=str(payload.get("model", "")),
        model_digest=str(payload.get("model_digest", "")),
        prompt_identity=str(prompt.get("identity", "")),
        ollama_format=str(payload.get("ollama_format", "")),
        checks=checks,
    )
