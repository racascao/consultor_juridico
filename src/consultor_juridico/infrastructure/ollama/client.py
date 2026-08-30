"""Cliente HTTP que conhece Ollama, mas não conhece decisões jurídicas."""

import json
from dataclasses import replace
from time import perf_counter
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from consultor_juridico.application.workflow.diagnostics import (
    ProviderCall,
    WorkflowDiagnostics,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class OllamaStructuredError(RuntimeError):
    def __init__(
        self,
        message: str,
        kind: str = "INVALID_STRUCTURED_OUTPUT",
        structured_output: dict[str, object] | None = None,
    ) -> None:
        self.kind = kind
        self.structured_output = structured_output
        super().__init__(message)


class OllamaStructuredClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float,
        client: httpx.Client | None = None,
        diagnostics: WorkflowDiagnostics | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._client = client
        self._diagnostics = diagnostics

    @property
    def model_name(self) -> str:
        return self._model

    def complete(
        self,
        system: str,
        user: str,
        schema: type[SchemaT],
        *,
        role: str = "chat",
        num_predict: int | None = None,
    ) -> SchemaT:
        payload = {
            "model": self._model,
            "stream": False,
            "think": False,
            "format": schema.model_json_schema(),
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if num_predict is not None:
            payload["options"]["num_predict"] = num_predict
        started = perf_counter()
        structured_output: dict[str, object] | None = None
        native_metrics: dict[str, float | int | None] = {}
        try:
            if self._client is None:
                response = httpx.post(
                    f"{self._base_url}/api/chat", json=payload, timeout=self._timeout
                )
            else:
                response = self._client.post(
                    f"{self._base_url}/api/chat", json=payload, timeout=self._timeout
                )
            response.raise_for_status()
            response_payload = response.json()
            native_metrics = _ollama_native_metrics(response_payload)
            content = response_payload["message"]["content"]
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                structured_output = parsed
            result = schema.model_validate(parsed)
            self._record_call(
                role,
                started,
                len(system) + len(user),
                "VALID",
                native_metrics=native_metrics,
            )
            return result
        except httpx.TimeoutException as exc:
            self._record_call(
                role,
                started,
                len(system) + len(user),
                "INVALID",
                "PROVIDER_TIMEOUT",
                provider_error_category="TIMEOUT",
                provider_message=_sanitize_provider_message(str(exc)),
            )
            raise OllamaStructuredError(
                f"Timeout do provedor Ollama: {exc}", "PROVIDER_TIMEOUT"
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else None
            message = _http_error_message(exc.response, exc)
            self._record_call(
                role,
                started,
                len(system) + len(user),
                "INVALID",
                "PROVIDER_ERROR",
                provider_error_category="HTTP_ERROR",
                provider_http_status=status,
                provider_message=message,
            )
            raise OllamaStructuredError(
                f"Falha HTTP no provedor Ollama: {status or 'N/A'}", "PROVIDER_ERROR"
            ) from exc
        except httpx.RequestError as exc:
            self._record_call(
                role,
                started,
                len(system) + len(user),
                "INVALID",
                "PROVIDER_ERROR",
                provider_error_category="CONNECTION_ERROR",
                provider_message=_sanitize_provider_message(str(exc)),
            )
            raise OllamaStructuredError(
                "Falha de conexão com o provedor Ollama.", "PROVIDER_ERROR"
            ) from exc
        except (
            KeyError,
            TypeError,
            ValueError,
            ValidationError,
        ) as exc:
            self._record_call(
                role,
                started,
                len(system) + len(user),
                "INVALID",
                "INVALID_STRUCTURED_OUTPUT",
                native_metrics,
            )
            raise OllamaStructuredError(
                f"Resposta estruturada inválida: {exc}",
                structured_output=structured_output,
            ) from exc

    def _record_call(
        self,
        role: str,
        started: float,
        request_chars: int,
        validation: str,
        error_kind: str | None = None,
        native_metrics: dict[str, float | int | None] | None = None,
        *,
        provider_error_category: str | None = None,
        provider_http_status: int | None = None,
        provider_message: str | None = None,
    ) -> None:
        if self._diagnostics is not None:
            self._diagnostics.add_provider_call(
                ProviderCall(
                    operation="chat",
                    role=role,
                    model=self._model,
                    duration_ms=(perf_counter() - started) * 1000,
                    request_chars=request_chars,
                    output_validation=validation,
                    error_kind=error_kind,
                    provider_error_category=provider_error_category,
                    provider_http_status=provider_http_status,
                    provider_message=provider_message,
                    **(native_metrics or {}),
                )
            )

    def mark_last_output_invalid(self, role: str) -> None:
        """Reclassifica falha contratual detectada pelo adapter, sem novo I/O."""
        if self._diagnostics is None:
            return
        for index in range(len(self._diagnostics.provider_calls) - 1, -1, -1):
            call = self._diagnostics.provider_calls[index]
            if call.role == role:
                self._diagnostics.provider_calls[index] = replace(
                    call,
                    output_validation="INVALID",
                    error_kind="INVALID_STRUCTURED_OUTPUT",
                )
                return

    def add_contract_detail(self, role: str, **values: object) -> None:
        if self._diagnostics is not None:
            self._diagnostics.add_detail(f"provider:{role}", **values)


def _ollama_native_metrics(payload: object) -> dict[str, float | int | None]:
    if not isinstance(payload, dict):
        return {}
    return {
        "total_duration_ms": _nanoseconds_to_ms(payload.get("total_duration")),
        "load_duration_ms": _nanoseconds_to_ms(payload.get("load_duration")),
        "prompt_eval_count": _optional_int(payload.get("prompt_eval_count")),
        "prompt_eval_duration_ms": _nanoseconds_to_ms(
            payload.get("prompt_eval_duration")
        ),
        "eval_count": _optional_int(payload.get("eval_count")),
        "eval_duration_ms": _nanoseconds_to_ms(payload.get("eval_duration")),
    }


def _nanoseconds_to_ms(value: object) -> float | None:
    return float(value) / 1_000_000 if isinstance(value, int | float) else None


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int) else None


def _http_error_message(
    response: httpx.Response | None, error: httpx.HTTPStatusError
) -> str:
    if response is not None:
        try:
            payload = response.json()
        except (ValueError, TypeError):
            payload = None
        if isinstance(payload, dict) and isinstance(payload.get("error"), str):
            return _sanitize_provider_message(payload["error"])
        if response.text:
            return _sanitize_provider_message(response.text)
    return _sanitize_provider_message(str(error))


def _sanitize_provider_message(message: str) -> str:
    sanitized = " ".join(message.split())
    return sanitized[:300] if sanitized else "Mensagem não fornecida pelo provider."
