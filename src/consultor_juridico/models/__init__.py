"""Módulo de entidades declarativas do SQLAlchemy do Consultor Jurídico."""

from consultor_juridico.models.chunk import Chunk, ChunkLegalElement
from consultor_juridico.models.claim import Citation, Claim
from consultor_juridico.models.embedding import Embedding
from consultor_juridico.models.evidence import EvidenceItem, EvidenceSet
from consultor_juridico.models.legal import LegalAct, LegalElement, LegalVersion
from consultor_juridico.models.parsing import ParsingRun
from consultor_juridico.models.source import Source, SourceDocument

__all__ = [
    "Source",
    "SourceDocument",
    "LegalAct",
    "LegalVersion",
    "LegalElement",
    "ParsingRun",
    "Chunk",
    "ChunkLegalElement",
    "Embedding",
    "EvidenceSet",
    "EvidenceItem",
    "Claim",
    "Citation",
]
