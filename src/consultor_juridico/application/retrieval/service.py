"""CandidateRetriever híbrido que retorna somente objetos de domínio."""

from consultor_juridico.application.retrieval.ports import (
    EmbeddingProvider,
    RetrievalRepository,
)
from consultor_juridico.application.retrieval.rrf import (
    diversify_article_families,
    reciprocal_rank_fusion,
)
from consultor_juridico.application.retrieval.types import EmbeddingMode
from consultor_juridico.domain import EvidenceCandidate, Question


class HybridCandidateRetriever:
    def __init__(
        self, repository: RetrievalRepository, embedding_provider: EmbeddingProvider
    ) -> None:
        self._repository = repository
        self._embedding_provider = embedding_provider

    def retrieve(self, question: Question, limit: int) -> tuple[EvidenceCandidate, ...]:
        pool_limit = max(limit * 3, 10)
        lexical = self._repository.lexical(question.text, pool_limit)
        try:
            query_vector = self._embedding_provider.embed(
                (question.text,), EmbeddingMode.QUERY
            )[0]
            vector = self._repository.vector(
                query_vector, self._embedding_provider.model_name, pool_limit
            )
        except (RuntimeError, IndexError):
            vector = ()
        fusion_limit = len(lexical) + len(vector)
        fused = reciprocal_rank_fusion(lexical, vector, fusion_limit)
        diversified = diversify_article_families(fused, limit)
        return tuple(
            EvidenceCandidate(
                candidate_id=f"E{index}",
                text=item.search_text,
                citation_label=item.stable_reference,
                source_locator=item.source_locator,
                search_unit_id=item.search_unit_id,
                search_unit_type=item.search_unit_type,
                legal_act_code=item.legal_act_code,
                stable_reference=item.stable_reference,
                article_reference=item.article_reference,
                citation_items=item.citation_items,
                lexical_rank=item.lexical_rank,
                vector_rank=item.vector_rank,
                fused_rank=index,
                source_url=item.source_url,
                source_snapshot_sha=item.source_snapshot_sha,
            )
            for index, item in enumerate(diversified, start=1)
        )
