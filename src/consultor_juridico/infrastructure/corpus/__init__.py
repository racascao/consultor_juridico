"""Adapters do corpus contextual v0.2."""

from consultor_juridico.infrastructure.corpus.parser import (
    PARSER_VERSION,
    ConstitutionCorpusParser,
)
from consultor_juridico.infrastructure.corpus.repository import (
    SqlAlchemyCorpusRepository,
)
from consultor_juridico.infrastructure.corpus.source import PlanaltoHttpSourceFetcher

__all__ = [
    "ConstitutionCorpusParser",
    "PARSER_VERSION",
    "PlanaltoHttpSourceFetcher",
    "SqlAlchemyCorpusRepository",
]
