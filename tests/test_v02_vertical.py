"""Integração vertical do core usando ports falsos, sem rede ou LLM real."""

from consultor_juridico.application.citation import TraceableCitationValidator
from consultor_juridico.application.retrieval import HybridCandidateRetriever
from consultor_juridico.application.retrieval.types import RankedSearchUnit
from consultor_juridico.application.workflow import (
    WorkflowContext,
    build_consultation_graph,
    initial_state,
)
from consultor_juridico.domain import (
    AnswerOutcome,
    CitationItem,
    ConsultationOutcome,
    Question,
)


class Repository:
    def lexical(self, query, limit):
        return (self._unit(),)

    def vector(self, query_vector, model, limit):
        return (self._unit(),)

    @staticmethod
    def _unit():
        return RankedSearchUnit(
            "unit-14",
            "ARTICLE",
            "CF88",
            "CF88/ARTICLE:14",
            "CF88/ARTICLE:14",
            "Art. 14. O alistamento eleitoral e o voto são facultativos...",
            (
                CitationItem(
                    "CF88/ARTICLE:14",
                    "Art. 14",
                    "Texto constitucional.",
                    "block:14",
                ),
            ),
            "block:14",
            "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
            "a" * 64,
        )


class Provider:
    provider_name = "fake"
    model_name = "fake"
    dimensions = 768

    def embed(self, texts, mode):
        return ((0.0,) * 768,)


class Responder:
    def respond(self, question, candidates):
        return AnswerOutcome(
            "Sim, nas hipóteses constitucionais indicadas.",
            (candidates[0].candidate_id,),
        )


def test_retrieval_graph_and_citation_form_a_traceable_vertical_slice():
    context = WorkflowContext(
        HybridCandidateRetriever(Repository(), Provider()),
        Responder(),
        TraceableCitationValidator(),
    )
    result = build_consultation_graph().invoke(
        initial_state(Question("O voto é facultativo?")), context=context
    )
    final = result["final_result"]
    assert final.outcome is ConsultationOutcome.ANSWERED
    assert final.evidence[0].stable_reference == "CF88/ARTICLE:14"
    assert final.evidence[0].source_snapshot_sha == "a" * 64
    assert final.citations[0].candidate_id == "E1"
