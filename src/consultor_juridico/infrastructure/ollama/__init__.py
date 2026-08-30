"""Adapter estruturado do único papel de consulta Ollama do MVP2."""

from consultor_juridico.infrastructure.ollama.adapters import (
    OllamaConsultationResponder,
)
from consultor_juridico.infrastructure.ollama.client import (
    OllamaStructuredClient,
    OllamaStructuredError,
)

__all__ = [
    "OllamaConsultationResponder",
    "OllamaStructuredClient",
    "OllamaStructuredError",
]
