"""Objetos e decisões do domínio de consulta da arquitetura v0.2."""

from consultor_juridico.domain.consultation import (
    AnswerDraft,
    Citation,
    ClarificationRequest,
    ClarificationTurn,
    ConsultationOutcome,
    ConsultationResult,
    Interpretation,
    Question,
)
from consultor_juridico.domain.decisions import (
    AnswerDecision,
    AnswerDecisionKind,
    CitationValidation,
    RelevanceDecision,
    RelevanceDecisionKind,
)
from consultor_juridico.domain.evidence import EvidenceCandidate, SelectedEvidence

__all__ = [
    "AnswerDecision",
    "AnswerDecisionKind",
    "AnswerDraft",
    "Citation",
    "CitationValidation",
    "ClarificationRequest",
    "ClarificationTurn",
    "ConsultationOutcome",
    "ConsultationResult",
    "EvidenceCandidate",
    "Interpretation",
    "Question",
    "RelevanceDecision",
    "RelevanceDecisionKind",
    "SelectedEvidence",
]
