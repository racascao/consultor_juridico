"""Representações imutáveis de evidências candidatas e selecionadas."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CitationItem:
    stable_key: str
    label: str | None
    citation_text: str
    source_locator: str | None


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    """Unidade candidata entregue pelo retriever ao workflow."""

    candidate_id: str
    text: str
    citation_label: str
    source_locator: str
    search_unit_id: str = ""
    search_unit_type: str = ""
    legal_act_code: str = ""
    stable_reference: str = ""
    article_reference: str | None = None
    citation_items: tuple[CitationItem, ...] = ()
    lexical_rank: int | None = None
    vector_rank: int | None = None
    fused_rank: int = 0
    source_url: str = ""
    source_snapshot_sha: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.text.strip():
            raise ValueError("Candidato deve possuir identidade e texto.")


@dataclass(frozen=True, slots=True)
class SelectedEvidence:
    """Candidata selecionada pelo resultado fundamentado da consulta."""

    candidate_id: str
    text: str
    citation_label: str
    source_locator: str
    stable_reference: str = ""
    citation_items: tuple[CitationItem, ...] = ()
    source_url: str = ""
    source_snapshot_sha: str = ""

    @classmethod
    def from_candidate(cls, candidate: EvidenceCandidate) -> "SelectedEvidence":
        return cls(
            candidate_id=candidate.candidate_id,
            text=candidate.text,
            citation_label=candidate.citation_label,
            source_locator=candidate.source_locator,
            stable_reference=candidate.stable_reference,
            citation_items=candidate.citation_items,
            source_url=candidate.source_url,
            source_snapshot_sha=candidate.source_snapshot_sha,
        )
