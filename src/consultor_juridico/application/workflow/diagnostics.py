"""Observabilidade local, tipada e sem impacto nas decisões do workflow."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from time import perf_counter


class AbstentionCause(StrEnum):
    NO_RELEVANT_EVIDENCE = "NO_RELEVANT_EVIDENCE"
    CONSULTATION_OUTPUT_INVALID = "CONSULTATION_OUTPUT_INVALID"
    WORKFLOW_LIMIT_REACHED = "WORKFLOW_LIMIT_REACHED"
    CITATION_VALIDATION_FAILED = "CITATION_VALIDATION_FAILED"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"


@dataclass(frozen=True, slots=True)
class NodeTiming:
    node: str
    attempt: int
    duration_ms: float
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderCall:
    operation: str
    role: str
    duration_ms: float
    request_chars: int
    output_validation: str
    error_kind: str | None = None
    provider_error_category: str | None = None
    provider_http_status: int | None = None
    provider_message: str | None = None
    model: str | None = None
    total_duration_ms: float | None = None
    load_duration_ms: float | None = None
    prompt_eval_count: int | None = None
    prompt_eval_duration_ms: float | None = None
    eval_count: int | None = None
    eval_duration_ms: float | None = None

    @property
    def prompt_tokens_per_second(self) -> float | None:
        return _rate(self.prompt_eval_count, self.prompt_eval_duration_ms)

    @property
    def generation_tokens_per_second(self) -> float | None:
        return _rate(self.eval_count, self.eval_duration_ms)


@dataclass(slots=True)
class WorkflowDiagnostics:
    """Coleta somente metadados auditáveis; nunca prompts ou raciocínio oculto."""

    node_timings: list[NodeTiming] = field(default_factory=list)
    provider_calls: list[ProviderCall] = field(default_factory=list)
    route: list[str] = field(default_factory=lambda: ["START"])
    details: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    abstention_cause: AbstentionCause | None = None

    @contextmanager
    def node(self, name: str, attempt: int) -> Iterator[None]:
        started = perf_counter()
        error: str | None = None
        try:
            yield
        except Exception as exc:
            error = type(exc).__name__
            raise
        finally:
            self.node_timings.append(
                NodeTiming(name, attempt, (perf_counter() - started) * 1000, error)
            )

    def add_route(self, step: str) -> None:
        self.route.append(step)

    def add_detail(self, node: str, **values: object) -> None:
        self.details.setdefault(node, []).append(values)

    def add_provider_call(self, call: ProviderCall) -> None:
        self.provider_calls.append(call)

    def last_provider_call(self, role: str) -> ProviderCall | None:
        return next(
            (item for item in reversed(self.provider_calls) if item.role == role), None
        )

    @property
    def workflow_total_ms(self) -> float:
        """Soma dos nós, excluindo espera humana durante interrupt."""
        return sum(item.duration_ms for item in self.node_timings)

    @property
    def node_execution_counts(self) -> dict[str, int]:
        return dict(Counter(item.node for item in self.node_timings))

    @property
    def embedding_calls(self) -> int:
        return sum(item.operation == "embedding" for item in self.provider_calls)

    @property
    def chat_calls(self) -> int:
        return sum(item.operation == "chat" for item in self.provider_calls)


def _rate(count: int | None, duration_ms: float | None) -> float | None:
    if count is None or duration_ms is None or duration_ms <= 0:
        return None
    return count / (duration_ms / 1000)
