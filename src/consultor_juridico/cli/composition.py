"""Composition root do pipeline MVP2; nenhuma regra de negócio vive aqui."""

from langgraph.checkpoint.memory import InMemorySaver

from consultor_juridico.application.citation import TraceableCitationValidator
from consultor_juridico.application.retrieval import (
    BuildRetrievalIndex,
    HybridCandidateRetriever,
)
from consultor_juridico.application.workflow import (
    WorkflowContext,
    WorkflowLimits,
    build_consultation_graph,
)
from consultor_juridico.application.workflow.diagnostics import WorkflowDiagnostics
from consultor_juridico.config import settings
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.infrastructure.ollama import (
    OllamaConsultationResponder,
    OllamaStructuredClient,
)
from consultor_juridico.infrastructure.retrieval import (
    OllamaEmbeddingProvider,
    PostgresRetrievalRepository,
)


def embedding_provider(
    diagnostics: WorkflowDiagnostics | None = None,
) -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(
        settings.ollama_base_url,
        settings.ollama_embedding_model,
        settings.ollama_timeout,
        settings.embedding_dimensions,
        diagnostics=diagnostics,
    )


def retrieval_repository() -> PostgresRetrievalRepository:
    return PostgresRetrievalRepository(SessionLocal)


def candidate_retriever(
    diagnostics: WorkflowDiagnostics | None = None,
) -> HybridCandidateRetriever:
    return HybridCandidateRetriever(
        retrieval_repository(), embedding_provider(diagnostics)
    )


def index_builder() -> BuildRetrievalIndex:
    return BuildRetrievalIndex(retrieval_repository(), embedding_provider())


def workflow_context() -> WorkflowContext:
    diagnostics = WorkflowDiagnostics()
    consultation_client = OllamaStructuredClient(
        settings.ollama_base_url,
        settings.ollama_consultation_model,
        settings.ollama_timeout,
        diagnostics=diagnostics,
    )
    return WorkflowContext(
        candidate_retriever(diagnostics),
        OllamaConsultationResponder(consultation_client),
        TraceableCitationValidator(),
        WorkflowLimits(max_clarification_turns=2),
        settings.retrieval_limit,
        diagnostics,
    )


def consultation_graph():
    return build_consultation_graph(InMemorySaver())
