"""Retrieval, embeddings e evaluator do MVP2 sem Ollama real."""

from contextlib import contextmanager
from dataclasses import replace

from consultor_juridico.application.retrieval import (
    BuildRetrievalIndex,
    EmbeddingDocument,
    EmbeddingMode,
    HybridCandidateRetriever,
    RankedSearchUnit,
    RetrievalCase,
    diversify_article_families,
    evaluate_retrieval,
    reciprocal_rank_fusion,
)
from consultor_juridico.domain import CitationItem, Question


def ranked(identity: str) -> RankedSearchUnit:
    return RankedSearchUnit(
        identity,
        "ARTICLE",
        "CF88",
        f"CF88/ARTICLE:{identity}",
        f"CF88/ARTICLE:{identity}",
        f"Artigo {identity}",
        (CitationItem(f"CF88/ARTICLE:{identity}", identity, "Texto", "block:1"),),
        "block:1",
        "https://planalto.example",
        "a" * 64,
    )


def test_rrf_is_deterministic_and_preserves_source_ranks():
    result = reciprocal_rank_fusion(
        (ranked("14"), ranked("143")), (ranked("143"), ranked("5")), 3
    )
    assert [item.search_unit_id for item in result] == ["143", "14", "5"]
    assert result[0].lexical_rank == 2
    assert result[0].vector_rank == 1


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-768"
    dimensions = 768

    def __init__(self):
        self.modes = []

    def embed(self, texts, mode):
        self.modes.append(mode)
        return tuple((float(index),) * 768 for index, _ in enumerate(texts, start=1))


class FakeRepository:
    def __init__(self, documents=None):
        self.documents = documents or (EmbeddingDocument("14", "texto", "a" * 64),)
        self.saved = []
        self.lock_entries = 0

    @contextmanager
    def index_build_lock(self):
        self.lock_entries += 1
        yield

    def lexical(self, query, limit):
        return (ranked("14"), ranked("143"))

    def vector(self, query_vector, model, limit):
        return (ranked("143"), ranked("14"))

    def embedding_documents(self, provider, model):
        return self.documents

    def save_embeddings(self, documents, vectors, provider, model, dimensions):
        self.saved.append((documents, vectors, provider, model, dimensions))
        saved_ids = {item.search_unit_id for item in documents}
        self.documents = tuple(
            item for item in self.documents if item.search_unit_id not in saved_ids
        )


def test_hybrid_candidate_mapping_and_request_scoped_labels():
    provider = FakeProvider()
    candidates = HybridCandidateRetriever(FakeRepository(), provider).retrieve(
        Question("alistamento"), 2
    )
    assert [item.candidate_id for item in candidates] == ["E1", "E2"]
    assert candidates[0].stable_reference == "CF88/ARTICLE:14"
    assert candidates[0].lexical_rank == 1
    assert candidates[0].vector_rank == 2
    assert provider.modes == [EmbeddingMode.QUERY]


def test_index_build_is_idempotent_and_refreshes_only_stale_documents():
    repository = FakeRepository()
    provider = FakeProvider()
    builder = BuildRetrievalIndex(repository, provider)
    assert builder.execute().embedded == 1
    assert repository.saved[0][4] == 768
    assert builder.execute().embedded == 0
    assert provider.modes == [EmbeddingMode.DOCUMENT]
    assert repository.lock_entries == 2


def test_index_build_persists_batches_and_resumes_only_missing_documents():
    documents = tuple(
        EmbeddingDocument(str(index), f"texto {index}", f"{index:064d}")
        for index in range(5)
    )
    repository = FakeRepository(documents)

    class FailingSecondBatch(FakeProvider):
        def embed(self, texts, mode):
            if len(self.modes) == 1:
                raise RuntimeError("timeout persistente")
            return super().embed(texts, mode)

    first_provider = FailingSecondBatch()
    builder = BuildRetrievalIndex(repository, first_provider, batch_size=2)
    try:
        builder.execute()
    except RuntimeError as exc:
        assert "timeout" in str(exc)
    else:
        raise AssertionError("Falha induzida deveria interromper o primeiro build.")

    assert len(repository.documents) == 3
    assert len(repository.saved) == 1
    progress = []
    resumed = BuildRetrievalIndex(
        repository,
        FakeProvider(),
        batch_size=2,
        progress=lambda completed, total: progress.append((completed, total)),
    ).execute()
    assert resumed.embedded == 3
    assert repository.documents == ()
    assert progress == [(2, 3), (3, 3)]


def test_retrieval_evaluator_requires_all_targets_for_ambiguity():
    repository = FakeRepository()
    retriever = HybridCandidateRetriever(repository, FakeProvider())
    cases = (
        RetrievalCase("C1", "voto", ("CF88/ARTICLE:14",)),
        RetrievalCase(
            "C2",
            "alistamento",
            ("CF88/ARTICLE:14", "CF88/ARTICLE:143"),
            "AMBIGUOUS",
        ),
    )
    result = evaluate_retrieval(retriever, cases, limit=2)
    assert result.cases == 2
    assert result.hit_at_10 == 1
    assert not result.failures
    assert result.case_results[0].final_rank == 1
    assert result.case_results[0].candidates[0].lexical_rank == 1
    assert result.case_results[0].unique_article_families == 2


def test_rrf_deduplicates_only_same_search_unit():
    contextual = replace(ranked("14"), search_unit_id="context-14")
    result = reciprocal_rank_fusion((ranked("14"), contextual), (), 10)
    assert len(result) == 2


def test_rrf_does_not_double_count_duplicate_identity_in_one_modality():
    duplicate = ranked("14")

    result = reciprocal_rank_fusion(
        (duplicate, duplicate, ranked("143")), (ranked("143"),), 2
    )

    assert [item.search_unit_id for item in result] == ["143", "14"]
    assert result[1].lexical_rank == 1


def test_hybrid_fetches_deeper_modality_pools_before_final_top_k():
    class RecordingRepository(FakeRepository):
        def __init__(self):
            super().__init__()
            self.limits = []

        def lexical(self, query, limit):
            self.limits.append(("lexical", limit))
            return tuple(ranked(str(index)) for index in range(1, 31))

        def vector(self, query_vector, model, limit):
            self.limits.append(("vector", limit))
            return tuple(ranked(str(index)) for index in range(30, 0, -1))

    repository = RecordingRepository()
    result = HybridCandidateRetriever(repository, FakeProvider()).retrieve(
        Question("consulta genérica"), 10
    )

    assert repository.limits == [("lexical", 30), ("vector", 30)]
    assert len(result) == 10


def test_deeper_pool_can_promote_target_beyond_old_modality_cutoff():
    lexical = tuple(ranked(str(index)) for index in range(1, 13))
    vector = tuple(ranked(str(index)) for index in (*range(30, 20, -1), 11, 12))

    result = reciprocal_rank_fusion(lexical, vector, 24)

    assert result[0].search_unit_id == "11"
    assert result[0].lexical_rank == 11
    assert result[0].vector_rank == 11


def test_article_family_diversification_preserves_best_specific_unit():
    article = ranked("14")
    specific = replace(
        ranked("14-II"),
        search_unit_type="CONTEXTUAL_PROVISION",
        stable_reference="CF88/ARTICLE:14/PARAGRAPH:1/INCISO:II",
        article_reference="CF88/ARTICLE:14",
    )
    sibling = replace(
        ranked("14-I"),
        search_unit_type="CONTEXTUAL_PROVISION",
        stable_reference="CF88/ARTICLE:14/PARAGRAPH:1/INCISO:I",
        article_reference="CF88/ARTICLE:14",
    )
    other = ranked("143")

    result = diversify_article_families((specific, sibling, article, other), 2)

    assert [item.search_unit_id for item in result] == ["14-II", "143"]


def test_article_family_diversification_fills_remaining_slots_deterministically():
    family_14 = tuple(
        replace(
            ranked(f"14-{index}"),
            stable_reference=f"CF88/ARTICLE:14/INCISO:{index}",
            article_reference="CF88/ARTICLE:14",
        )
        for index in range(1, 4)
    )
    other = ranked("143")

    result = diversify_article_families((*family_14, other), 4)

    assert [item.search_unit_id for item in result] == [
        "14-1",
        "143",
        "14-2",
        "14-3",
    ]


def test_diversification_keeps_order_when_there_is_no_family_crowding():
    candidates = tuple(ranked(str(index)) for index in (14, 143, 5))

    assert diversify_article_families(candidates, 3) == candidates


def test_document_metadata_participates_in_fusion_and_diversification():
    metadata = replace(
        ranked("metadata"),
        search_unit_type="DOCUMENT_METADATA",
        stable_reference="CF88/METADATA:FACT_DATE",
        article_reference=None,
    )
    article = ranked("5")

    fused = reciprocal_rank_fusion((metadata,), (article, metadata), 2)
    result = diversify_article_families(fused, 2)

    assert {item.stable_reference for item in result} == {
        "CF88/METADATA:FACT_DATE",
        "CF88/ARTICLE:5",
    }


def test_retrieval_target_matching_is_exact_for_parent_child_and_act():
    class StaticRetriever:
        def __init__(self, references):
            self.references = references

        def retrieve(self, question, limit):
            return tuple(
                replace(
                    HybridCandidateRetriever(FakeRepository(), FakeProvider()).retrieve(
                        question, 1
                    )[0],
                    stable_reference=reference,
                )
                for reference in self.references
            )

    cases = (
        RetrievalCase("exact", "q", ("CF88/ARTICLE:5",)),
        RetrievalCase("child", "q", ("CF88/ARTICLE:5/INCISO:XI",)),
        RetrievalCase("other-act", "q", ("ADCT/ARTICLE:5",)),
    )
    result = evaluate_retrieval(StaticRetriever(("CF88/ARTICLE:5",)), cases, limit=10)

    assert result.hit_at_10 == 1 / 3
    assert {failure.case_id for failure in result.failures} == {
        "child",
        "other-act",
    }
