"""Runner Ollama isolado para execução manual do bundle Gold Evidence."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

import httpx

from consultor_juridico.evaluation.gold_stability import load_gold_bundle_records

GENERATION_CONFIG: dict[str, float | int] = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "seed": 42,
    "repeat_penalty": 1.0,
    "num_predict": 1024,
    "num_ctx": 8192,
}
MAX_GENERATION_TIME_SECONDS = 180.0


class ThinkingMode(StrEnum):
    """Controle nativo e genérico do modo de raciocínio do provider."""

    AUTO = "auto"
    DISABLED = "disabled"


class OllamaModelNotAvailableError(RuntimeError):
    """O modelo explícito não está instalado no provider local."""


class OllamaGoldRunError(RuntimeError):
    """A execução foi interrompida sem retry semântico."""


def _provider_version(client: httpx.Client, base_url: str) -> str | None:
    try:
        response = client.get(f"{base_url}/api/version")
        response.raise_for_status()
        value = response.json().get("version")
    except (httpx.HTTPError, ValueError, AttributeError):
        return None
    return str(value) if value is not None else None


def _find_local_model(
    client: httpx.Client, base_url: str, model: str
) -> dict[str, Any]:
    try:
        response = client.get(f"{base_url}/api/tags")
        response.raise_for_status()
        models = response.json().get("models", [])
    except (httpx.HTTPError, ValueError, AttributeError) as error:
        raise OllamaGoldRunError(
            "Falha ao consultar modelos locais do Ollama"
        ) from error
    for item in models:
        if model in {item.get("name"), item.get("model")}:
            return item
    raise OllamaModelNotAvailableError(f"MODEL_NOT_AVAILABLE_LOCALLY: {model}")


def _write_metadata(path: Path, payload: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as output:
        json.dump(payload, output, ensure_ascii=False, indent=2)
        output.write("\n")


def run_ollama_gold_bundle(
    *,
    input_path: Path,
    model: str,
    base_url: str,
    output_path: Path,
    metadata_path: Path,
    client: httpx.Client,
    seed: int = 42,
    thinking_mode: ThinkingMode = ThinkingMode.AUTO,
    ollama_format: str | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    """Executa uma geração por caso e preserva a saída bruta sem reparo."""
    if not model.strip():
        raise ValueError("model explícito é obrigatório")
    if output_path.exists():
        raise FileExistsError(f"O artefato não pode ser sobrescrito: {output_path}")
    if metadata_path.exists():
        raise FileExistsError(f"O artefato não pode ser sobrescrito: {metadata_path}")
    if ollama_format is not None and not ollama_format.strip():
        raise ValueError("ollama_format não pode ser vazio")

    normalized_base_url = base_url.rstrip("/")
    if not normalized_base_url:
        raise ValueError("base_url explícita é obrigatória")
    input_bytes = input_path.read_bytes()
    records = load_gold_bundle_records(input_path)
    model_info = _find_local_model(client, normalized_base_url, model)
    provider_version = _provider_version(client, normalized_base_url)
    started_at = now()
    run_id = str(uuid4())
    case_metrics: list[dict[str, Any]] = []
    status = "COMPLETED"
    failure: dict[str, str] | None = None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("x", encoding="utf-8") as output:
            for record in records:
                request_payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": record["system_prompt"]},
                        {"role": "user", "content": record["user_prompt"]},
                    ],
                    "stream": False,
                    "options": GENERATION_CONFIG | {"seed": seed},
                }
                if thinking_mode is ThinkingMode.DISABLED:
                    request_payload["think"] = False
                if ollama_format is not None:
                    request_payload["format"] = ollama_format
                wall_started = monotonic()
                try:
                    response = client.post(
                        f"{normalized_base_url}/api/chat", json=request_payload
                    )
                    response.raise_for_status()
                    provider_payload = response.json()
                    message = provider_payload["message"]
                    if (
                        thinking_mode is ThinkingMode.DISABLED
                        and isinstance(message.get("thinking"), str)
                        and message["thinking"].strip()
                    ):
                        raise OllamaGoldRunError(
                            "THINKING_CONTENT_RETURNED_WHEN_DISABLED; execução "
                            "interrompida"
                        )
                    raw_response = message["content"]
                    if not isinstance(raw_response, str):
                        raise TypeError("message.content não é texto")
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                    raise OllamaGoldRunError(
                        f"Falha no caso {record['case_id']}; nenhum retry executado"
                    ) from error
                wall_latency_ms = (monotonic() - wall_started) * 1000
                total_duration_ns = provider_payload.get("total_duration")
                latency_ms = (
                    float(total_duration_ns) / 1_000_000
                    if isinstance(total_duration_ns, int | float)
                    else wall_latency_ms
                )
                output.write(
                    json.dumps(
                        {
                            "case_id": record["case_id"],
                            "raw_response": raw_response,
                            "latency_ms": latency_ms,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                output.flush()
                case_metrics.append(
                    {
                        "case_id": record["case_id"],
                        "latency_ms": latency_ms,
                        "total_duration_ns": total_duration_ns,
                        "prompt_eval_count": provider_payload.get("prompt_eval_count"),
                        "eval_count": provider_payload.get("eval_count"),
                    }
                )
    except OllamaGoldRunError as error:
        status = "FAILED"
        failure = {"type": type(error).__name__, "message": str(error)}
        caught_error: OllamaGoldRunError | None = error
    else:
        caught_error = None

    finished_at = now()
    details = model_info.get("details") or {}
    metadata = {
        "run_id": run_id,
        "status": status,
        "provider": "ollama",
        "provider_version": provider_version,
        "model": model,
        "model_digest": model_info.get("digest"),
        "quantization": details.get("quantization_level"),
        "dataset_sha256": records[0]["dataset_sha256"],
        "input_bundle_sha256": sha256(input_bytes).hexdigest(),
        "prompt_name": records[0]["prompt_name"],
        "prompt_version": records[0]["prompt_version"],
        "act_version_hash": records[0]["version_hash"],
        "generation_config": GENERATION_CONFIG | {"seed": seed, "stream": False},
        "thinking_mode": thinking_mode.value,
        "max_generation_time_seconds": MAX_GENERATION_TIME_SECONDS,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "case_count": len(records),
        "completed_case_count": len(case_metrics),
        "semantic_retries": 0,
        "case_metrics": case_metrics,
        "failure": failure,
    }
    if ollama_format is not None:
        metadata["ollama_format"] = ollama_format
    _write_metadata(metadata_path, metadata)
    if caught_error is not None:
        raise caught_error
    return metadata
