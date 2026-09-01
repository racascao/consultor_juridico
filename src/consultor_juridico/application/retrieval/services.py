"""Caso de uso mínimo para recuperar SearchUnits."""

from consultor_juridico.application.retrieval.ports import SearchUnitRetriever
from consultor_juridico.domain.retrieval import RetrievalCandidate, RetrievalRequest


class RetrieveSearchUnits:
    def __init__(self, retriever: SearchUnitRetriever) -> None:
        self._retriever = retriever

    def execute(self, request: RetrievalRequest) -> tuple[RetrievalCandidate, ...]:
        return self._retriever.search(request)
