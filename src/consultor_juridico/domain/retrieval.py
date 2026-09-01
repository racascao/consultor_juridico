"""Contratos puros do baseline lexical da Fase 1."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class RetrievalMode(StrEnum):
    STRICT = "strict"
    RELAXED_OR = "relaxed-or"
    RELAXED_OR_COVERAGE = "relaxed-or-coverage"


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    question: str
    version_hash: str
    limit: int = 10

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("A pergunta de retrieval não pode ser vazia")
        if len(self.version_hash) != 64 or any(
            char not in "0123456789abcdef" for char in self.version_hash
        ):
            raise ValueError("version_hash deve ser um SHA-256 hexadecimal minúsculo")
        if not 1 <= self.limit <= 100:
            raise ValueError("limit deve estar entre 1 e 100")


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    rank: int
    search_unit_id: UUID
    unit_key: str
    score: float
    provision_stable_keys: tuple[str, ...]
    search_text: str


@dataclass(frozen=True, slots=True)
class RetrievalContext:
    legal_act_code: str
    act_version_id: UUID
    version_hash: str
    source_snapshot_sha256: str
    parser_name: str
    parser_version: str
    projection_name: str
    projection_version: str
