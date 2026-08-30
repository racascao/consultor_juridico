"""Erros explícitos do pipeline de consulta."""


class ConsultationError(RuntimeError):
    """Falha controlada na consulta jurídica."""


class LLMResponseError(ConsultationError):
    """Resposta do provedor local incompatível com o contrato estruturado."""
