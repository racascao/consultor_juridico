"""Tipos imutáveis da materialização de Gold Evidence."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class GoldEvidenceItem:
    stable_key: str
    provision_type: str
    citation_text: str
    source_locator: dict[str, Any]
    source_snapshot_sha256: str
    official_url: str
    document_order: int


@dataclass(frozen=True, slots=True)
class GoldEvidenceContext:
    legal_act_code: str
    version_hash: str
    source_snapshot_sha256: str
    official_url: str
