"""Representações imutáveis de evidências candidatas e selecionadas."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    """Unidade candidata entregue pelo retriever ao workflow."""

    candidate_id: str
    text: str
    citation_label: str
    source_locator: str

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.text.strip():
            raise ValueError("Candidato deve possuir identidade e texto.")


@dataclass(frozen=True, slots=True)
class SelectedEvidence:
    """Candidata aprovada pelo julgamento de relevância."""

    candidate_id: str
    text: str
    citation_label: str
    source_locator: str

    @classmethod
    def from_candidate(cls, candidate: EvidenceCandidate) -> "SelectedEvidence":
        return cls(
            candidate_id=candidate.candidate_id,
            text=candidate.text,
            citation_label=candidate.citation_label,
            source_locator=candidate.source_locator,
        )
