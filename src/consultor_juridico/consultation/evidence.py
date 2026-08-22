"""Construção e congelamento de evidências recuperadas."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from consultor_juridico.models import (
    Chunk,
    ChunkLegalElement,
    EvidenceItem,
    EvidenceSet,
    LegalAct,
    LegalElement,
    LegalProvision,
    LegalVersion,
    SourceDocument,
)
from consultor_juridico.retrieval import RetrievalCandidate


def build_evidence_set(
    session: Session,
    question: str,
    candidates: tuple[RetrievalCandidate, ...],
    *,
    retrieval_metadata: dict[str, object],
) -> EvidenceSet:
    evidence_set = EvidenceSet(
        query_text=question,
        retrieval_strategy="hybrid_rrf",
        validation_status="BUILDING",
        total_items=0,
        metadata_json=retrieval_metadata,
    )
    session.add(evidence_set)
    session.flush()

    for position, candidate in enumerate(candidates, start=1):
        row = session.execute(
            select(
                Chunk,
                LegalElement,
                LegalProvision,
                LegalAct,
                LegalVersion,
                SourceDocument,
            )
            .join(ChunkLegalElement, ChunkLegalElement.chunk_id == Chunk.id)
            .join(LegalElement, LegalElement.id == ChunkLegalElement.legal_element_id)
            .join(LegalProvision, LegalProvision.id == LegalElement.legal_provision_id)
            .join(LegalAct, LegalAct.id == LegalElement.legal_act_id)
            .join(LegalVersion, LegalVersion.id == Chunk.legal_version_id)
            .join(SourceDocument, SourceDocument.id == LegalVersion.source_document_id)
            .where(
                Chunk.id == candidate.chunk_id,
                LegalElement.id == candidate.legal_element_id,
                LegalProvision.id == candidate.legal_provision_id,
                ChunkLegalElement.is_primary.is_(True),
                LegalElement.text_status == "CURRENT",
                LegalElement.content_role == "NORMATIVE",
                LegalVersion.is_active_for_query.is_(True),
            )
        ).one_or_none()
        if row is None:
            continue
        chunk, element, provision, act, version, document = row
        if chunk.chunk_text != candidate.chunk_text:
            continue
        label = _citation_label(act.short_name, element, provision)
        # Para INCISO/ALINEA/ITEM, captura contexto estrutural do pai para auxiliar
        # geração e retrieval sem alterar snapshot citável (provenance preservada)
        parent_context = None
        if element.element_type in ("INCISO", "ALINEA", "ITEM") and element.parent_id:
            parent = session.get(LegalElement, element.parent_id)
            if parent and parent.normalized_text:
                parent_context = parent.normalized_text.strip()
        item = EvidenceItem(
            evidence_set_id=evidence_set.id,
            chunk_id=chunk.id,
            legal_element_id=element.id,
            evidence_code=f"EV{position:03d}",
            citation_label=label,
            text_snapshot=chunk.chunk_text,
            source_url=document.url_source,
            is_validated=True,
            validation_metadata={
                "legal_act": act.short_name,
                "legal_version_id": str(version.id),
                "legal_provision_id": str(provision.id),
                "identity_key": provision.identity_key,
                "text_status": element.text_status,
                "content_role": element.content_role,
                "lexical_rank": candidate.lexical_rank,
                "lexical_score": candidate.lexical_score,
                "vector_rank": candidate.vector_rank,
                "vector_score": candidate.vector_score,
                "rrf_score": candidate.rrf_score,
                "contextual_score": candidate.contextual_score,
                "parent_context": parent_context,
            },
        )
        session.add(item)
        evidence_set.items.append(item)
    evidence_set.total_items = len(evidence_set.items)
    evidence_set.validation_status = (
        "EVIDENCE_VALIDATED" if evidence_set.items else "INSUFFICIENT_EVIDENCE"
    )
    session.flush()
    return evidence_set


def _citation_label(
    act_name: str, element: LegalElement, provision: LegalProvision
) -> str:
    label = element.number_label or provision.number_label
    suffix = f" {label}" if label else ""
    return (
        f"{act_name}, {element.element_type}{suffix} "
        f"(identidade: {provision.identity_key})"
    )
