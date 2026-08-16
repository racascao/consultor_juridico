"""Consulta jurídica fundamentada, local e auditável."""

from consultor_juridico.consultation.llm import OllamaLegalGenerator
from consultor_juridico.consultation.service import run_consultation
from consultor_juridico.consultation.types import (
    CitationReference,
    ConsultationOutcome,
    ConsultationResult,
    GeneratedClaim,
    GeneratedResponse,
    ValidationReport,
)
from consultor_juridico.consultation.validator import validate_citations

__all__ = [
    "ConsultationOutcome",
    "ConsultationResult",
    "CitationReference",
    "GeneratedClaim",
    "GeneratedResponse",
    "OllamaLegalGenerator",
    "ValidationReport",
    "run_consultation",
    "validate_citations",
]
