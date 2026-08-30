"""Chunking jurídico determinístico sobre ocorrências materializadas."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from consultor_juridico.models import LegalAct, LegalElement, LegalVersion

CHUNK_STRATEGY = "legal_occurrence_current_v1"
CHUNK_ELEMENT_TYPES = (
    "PREAMBLE",
    "TITLE",
    "CHAPTER",
    "SECTION",
    "SUBSECTION",
    "CAPUT",
    "PARAGRAPH",
    "INCISO",
    "ALINEA",
    "ITEM",
)


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    legal_version_id: UUID
    legal_element_id: UUID
    legal_provision_id: UUID
    chunk_text: str
    token_count: int


def build_chunk_drafts(session: Session) -> tuple[ChunkDraft, ...]:
    """Produz chunks somente de texto normativo corrente nas versões ativas."""
    rows = session.execute(
        select(LegalElement, LegalAct.short_name)
        .join(LegalVersion, LegalElement.legal_version_id == LegalVersion.id)
        .join(LegalAct, LegalElement.legal_act_id == LegalAct.id)
        .where(
            LegalVersion.is_active_for_query.is_(True),
            LegalElement.content_role == "NORMATIVE",
            LegalElement.text_status == "CURRENT",
            LegalElement.element_type.in_(CHUNK_ELEMENT_TYPES),
            LegalElement.legal_provision_id.is_not(None),
        )
        .order_by(LegalAct.short_name, LegalElement.document_order)
    )
    drafts = []
    for element, act_name in rows:
        assert element.legal_provision_id is not None
        identity = element.path or str(element.legal_provision_id)
        text = f"{act_name} | {identity}\n{element.normalized_text.strip()}"
        drafts.append(
            ChunkDraft(
                element.legal_version_id,
                element.id,
                element.legal_provision_id,
                text,
                len(text.split()),
            )
        )
    return tuple(drafts)
