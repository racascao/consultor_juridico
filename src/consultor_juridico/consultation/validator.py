"""Validação determinística de claims, citations e cadeia documental."""

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from consultor_juridico.consultation.support_slots import validate_support_slot
from consultor_juridico.consultation.types import GeneratedResponse, ValidationReport
from consultor_juridico.models import (
    Chunk,
    ChunkLegalElement,
    EvidenceItem,
    EvidenceSet,
    LegalElement,
    LegalVersion,
    SourceDocument,
)

EVIDENCE_CODE_RE = re.compile(r"\bEV\d{3,}\b")


def validate_citations(
    session: Session,
    evidence_set: EvidenceSet,
    response: GeneratedResponse,
    *,
    support_slots: tuple[Any, ...] = (),
) -> ValidationReport:
    errors: list[str] = []
    items = {item.evidence_code: item for item in evidence_set.items}
    for slot in support_slots:
        errors.extend(validate_support_slot(session, evidence_set, slot))
    if response.abstain:
        if response.claims:
            errors.append("Resposta abstida não pode conter claims.")
        return ValidationReport(not errors, tuple(errors), 0, len(response.claims))
    if not response.claims:
        errors.append("Resposta fundamentada sem claims.")
    claim_codes: set[str] = set()
    cited: set[str] = set()
    for claim in response.claims:
        if not claim.claim_code.strip() or claim.claim_code in claim_codes:
            errors.append(f"Claim code inválido/duplicado: {claim.claim_code!r}.")
        claim_codes.add(claim.claim_code)
        if not claim.text.strip():
            errors.append(f"Claim {claim.claim_code} sem texto.")
        if not claim.evidence_codes:
            errors.append(f"Claim {claim.claim_code} sem citação.")
        for code in claim.evidence_codes:
            item = items.get(code)
            if item is None:
                errors.append(
                    f"Claim {claim.claim_code} cita evidência desconhecida {code}."
                )
                continue
            cited.add(code)
            errors.extend(_validate_item_chain(session, evidence_set.id, item))
    unknown_in_answer = set(EVIDENCE_CODE_RE.findall(response.answer)) - set(items)
    if unknown_in_answer:
        errors.append(
            "Resposta menciona evidências desconhecidas: "
            + ", ".join(sorted(unknown_in_answer))
        )
    return ValidationReport(
        is_valid=not errors,
        errors=tuple(dict.fromkeys(errors)),
        cited_evidence=len(cited),
        total_claims=len(response.claims),
    )


def _validate_item_chain(session: Session, set_id, item: EvidenceItem) -> list[str]:
    if item.evidence_set_id != set_id or not item.is_validated:
        return [
            f"Evidência {item.evidence_code} não pertence/foi validada no conjunto."
        ]
    row = session.execute(
        select(Chunk.chunk_text, SourceDocument.url_source)
        .join(ChunkLegalElement, ChunkLegalElement.chunk_id == Chunk.id)
        .join(LegalElement, LegalElement.id == ChunkLegalElement.legal_element_id)
        .join(LegalVersion, LegalVersion.id == LegalElement.legal_version_id)
        .join(SourceDocument, SourceDocument.id == LegalVersion.source_document_id)
        .where(
            Chunk.id == item.chunk_id,
            LegalElement.id == item.legal_element_id,
            ChunkLegalElement.is_primary.is_(True),
            LegalElement.text_status == "CURRENT",
            LegalElement.content_role == "NORMATIVE",
        )
    ).one_or_none()
    if row is None:
        return [f"Cadeia documental inválida para {item.evidence_code}."]
    errors = []
    if row.chunk_text != item.text_snapshot:
        errors.append(f"Snapshot divergente do chunk em {item.evidence_code}.")
    if row.url_source != item.source_url:
        errors.append(f"URL oficial divergente em {item.evidence_code}.")
    return errors
