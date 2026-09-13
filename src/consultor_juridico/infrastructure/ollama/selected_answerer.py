"""Adapter de produção para o answerer congelado do MVP2."""

from __future__ import annotations

from typing import Any

import httpx

from consultor_juridico.evaluation.ollama_gold_runner import GENERATION_CONFIG
from consultor_juridico.evaluation.selected_answerer import (
    SELECTED_MODEL,
    SELECTED_MODEL_DIGEST,
    SELECTED_OLLAMA_FORMAT,
    validate_selected_answerer_freeze,
)


class SelectedAnswererError(RuntimeError):
    pass


class OllamaSelectedAnswerer:
    def __init__(self, client: httpx.Client, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        if self._base_url not in {
            "http://ollama:11434",
            "http://localhost:11435",
        }:
            raise ValueError("OLLAMA_BASE_URL_NOT_ALLOWED_FOR_PROJECT")

    def _validate(self) -> None:
        freeze = validate_selected_answerer_freeze()
        if not freeze.valid:
            failed = sorted(key for key, value in freeze.checks.items() if not value)
            raise SelectedAnswererError(f"SELECTED_ANSWERER_FREEZE_MISMATCH: {failed}")
        try:
            response = self._client.get(f"{self._base_url}/api/tags")
            response.raise_for_status()
            models = response.json()["models"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise SelectedAnswererError("OLLAMA_MODEL_DISCOVERY_FAILED") from error
        model: dict[str, Any] | None = next(
            (
                item
                for item in models
                if SELECTED_MODEL in {item.get("name"), item.get("model")}
            ),
            None,
        )
        if model is None:
            raise SelectedAnswererError("SELECTED_MODEL_NOT_AVAILABLE")
        if model.get("digest") != SELECTED_MODEL_DIGEST:
            raise SelectedAnswererError("SELECTED_MODEL_DIGEST_MISMATCH")

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self._validate()
        options = {
            key: value for key, value in GENERATION_CONFIG.items() if key != "seed"
        }
        payload = {
            "model": SELECTED_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "think": False,
            "format": SELECTED_OLLAMA_FORMAT,
            "options": options,
        }
        try:
            response = self._client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
            message = response.json()["message"]
            if isinstance(message.get("thinking"), str) and message["thinking"].strip():
                raise SelectedAnswererError("THINKING_RETURNED_WHEN_DISABLED")
            content = message["content"]
            if not isinstance(content, str):
                raise TypeError("message.content não é texto")
            return content
        except SelectedAnswererError:
            raise
        except httpx.TimeoutException as error:
            raise SelectedAnswererError(
                "SELECTED_ANSWERER_REQUEST_FAILED: TIMEOUT"
            ) from error
        except httpx.ConnectError as error:
            raise SelectedAnswererError(
                "SELECTED_ANSWERER_REQUEST_FAILED: CONNECTIVITY"
            ) from error
        except httpx.HTTPStatusError as error:
            raise SelectedAnswererError(
                "SELECTED_ANSWERER_REQUEST_FAILED: "
                f"HTTP_STATUS_{error.response.status_code}"
            ) from error
        except (ValueError, KeyError, TypeError) as error:
            raise SelectedAnswererError(
                "SELECTED_ANSWERER_REQUEST_FAILED: INVALID_RESPONSE"
            ) from error
