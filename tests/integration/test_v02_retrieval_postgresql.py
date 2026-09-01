"""Regressões físicas do baseline lexical em PostgreSQL descartável."""

import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from consultor_juridico.domain.retrieval import RetrievalRequest
from consultor_juridico.infrastructure.corpus.models import (
    ActVersionModel,
    LegalActModel,
    ProvisionModel,
    SearchUnitModel,
    SearchUnitProvisionModel,
    SourceModel,
    SourceSnapshotModel,
)
from consultor_juridico.infrastructure.retrieval import (
    PostgresFullTextSearchRetriever,
    PostgresRelaxedOrCoverageFullTextSearchRetriever,
    PostgresRelaxedOrFullTextSearchRetriever,
)

DATABASE_URL = os.getenv("V02_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="V02_TEST_DATABASE_URL não configurada"
)
ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def session_factory():
    engine = create_engine(DATABASE_URL)
    factory = sessionmaker(engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(session_factory):
    with session_factory() as session, session.begin():
        session.execute(
            text(
                "TRUNCATE search_unit_provisions, search_units, provisions, "
                "act_versions, legal_acts, source_snapshots, sources CASCADE"
            )
        )


def _seed_version(
    session,
    *,
    suffix: str,
    unit_texts: tuple[tuple[str, str], ...],
) -> tuple[str, UUID]:
    raw = f"<html>{suffix}</html>".encode()
    source = SourceModel(
        authority_code=f"AUTH-{suffix}",
        official_url=f"https://example.test/{suffix}",
        name=f"Fonte {suffix}",
    )
    session.add(source)
    session.flush()
    snapshot = SourceSnapshotModel(
        source_id=source.id,
        sha256=sha256(raw).hexdigest(),
        raw_bytes=raw,
        byte_length=len(raw),
        content_type="text/html",
    )
    act = LegalActModel(
        act_code=f"ACT-{suffix}",
        jurisdiction="BR",
        act_type="LEI",
        number=suffix,
        year=2000,
        title=f"Lei {suffix}",
    )
    session.add_all((snapshot, act))
    session.flush()
    version_hash = sha256(f"version-{suffix}".encode()).hexdigest()
    version = ActVersionModel(
        legal_act_id=act.id,
        source_snapshot_id=snapshot.id,
        parser_name="parser",
        parser_version="1",
        projection_name="projection",
        projection_version="1",
        version_hash=version_hash,
    )
    session.add(version)
    session.flush()
    for position, (unit_key, search_text) in enumerate(unit_texts, start=1):
        stable_key = f"ARTICLE:{suffix}/PARAGRAPH:{position}"
        provision = ProvisionModel(
            act_version_id=version.id,
            stable_key=stable_key,
            provision_type="PARAGRAPH",
            number_label=str(position),
            document_order=position,
            citation_text=search_text,
            source_locator={"paragraph_start": position, "paragraph_end": position},
            content_hash=sha256(search_text.encode()).hexdigest(),
            legal_status="IN_FORCE",
        )
        unit = SearchUnitModel(
            act_version_id=version.id,
            unit_key=unit_key,
            search_text=search_text,
            content_hash=sha256(search_text.encode()).hexdigest(),
        )
        session.add_all((provision, unit))
        session.flush()
        session.add(
            SearchUnitProvisionModel(
                search_unit_id=unit.id,
                provision_id=provision.id,
                position=0,
            )
        )
    session.flush()
    return version_hash, version.id


def test_portuguese_fts_rank_and_search_unit_provision_resolution(session_factory):
    with session_factory() as session, session.begin():
        version_hash, _ = _seed_version(
            session,
            suffix="A",
            unit_texts=(
                ("UNIT:A", "As decisões administrativas deverão ser motivadas."),
            ),
        )
    with session_factory() as session:
        results = PostgresFullTextSearchRetriever(session).search(
            RetrievalRequest("decisões administrativas motivadas", version_hash)
        )
    assert len(results) == 1
    assert results[0].score > 0
    assert results[0].provision_stable_keys == ("ARTICLE:A/PARAGRAPH:1",)


def test_gin_expression_index_exists(session_factory):
    with session_factory() as session:
        definition = session.scalar(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname='public' "
                "AND indexname='ix_search_units_fts_portuguese'"
            )
        )
    assert "USING gin" in definition
    assert "to_tsvector('portuguese'::regconfig, search_text)" in definition


def test_explicit_act_version_filter_prevents_cross_version_leakage(session_factory):
    common = "decisão administrativa motivada"
    with session_factory() as session, session.begin():
        hash_a, _ = _seed_version(session, suffix="A", unit_texts=(("UNIT:A", common),))
        hash_b, _ = _seed_version(session, suffix="B", unit_texts=(("UNIT:B", common),))
    with session_factory() as session:
        retriever = PostgresFullTextSearchRetriever(session)
        result_a = retriever.search(RetrievalRequest(common, hash_a))
        result_b = retriever.search(RetrievalRequest(common, hash_b))
    assert [item.unit_key for item in result_a] == ["UNIT:A"]
    assert [item.unit_key for item in result_b] == ["UNIT:B"]


def test_ties_are_broken_by_unit_key(session_factory):
    common = "processo administrativo federal"
    with session_factory() as session, session.begin():
        version_hash, _ = _seed_version(
            session,
            suffix="T",
            unit_texts=(("UNIT:B", common), ("UNIT:A", common)),
        )
    with session_factory() as session:
        results = PostgresFullTextSearchRetriever(session).search(
            RetrievalRequest(common, version_hash)
        )
    assert [item.unit_key for item in results] == ["UNIT:A", "UNIT:B"]
    assert [item.rank for item in results] == [1, 2]


def test_tsquery_without_useful_lexemes_returns_empty(session_factory):
    with session_factory() as session, session.begin():
        version_hash, _ = _seed_version(
            session,
            suffix="E",
            unit_texts=(("UNIT:E", "processo administrativo"),),
        )
    with session_factory() as session:
        results = PostgresFullTextSearchRetriever(session).search(
            RetrievalRequest("e de a", version_hash)
        )
    assert results == ()


def test_context_and_all_provision_keys_are_version_scoped(session_factory):
    with session_factory() as session, session.begin():
        version_hash, version_id = _seed_version(
            session,
            suffix="C",
            unit_texts=(("UNIT:C", "competência administrativa"),),
        )
    with session_factory() as session:
        retriever = PostgresFullTextSearchRetriever(session)
        context = retriever.context(version_hash)
        keys = retriever.provision_keys(version_hash)
    assert context.act_version_id == version_id
    assert context.legal_act_code == "ACT-C"
    assert context.parser_name == "parser"
    assert keys == {"ARTICLE:C/PARAGRAPH:1"}


def test_relaxed_or_generates_candidates_for_independent_lexemes(session_factory):
    with session_factory() as session, session.begin():
        version_hash, _ = _seed_version(
            session,
            suffix="O",
            unit_texts=(
                ("UNIT:A", "competência administrativa"),
                ("UNIT:B", "prazo para decisão"),
            ),
        )
    request = RetrievalRequest("competência prazo", version_hash)
    with session_factory() as session:
        strict = PostgresFullTextSearchRetriever(session).search(request)
        relaxed = PostgresRelaxedOrFullTextSearchRetriever(session).search(request)
    assert strict == ()
    assert {item.unit_key for item in relaxed} == {"UNIT:A", "UNIT:B"}


def test_relaxed_or_ignores_no_lexeme_match_without_special_fallback(session_factory):
    with session_factory() as session, session.begin():
        version_hash, _ = _seed_version(
            session,
            suffix="N",
            unit_texts=(("UNIT:N", "competência administrativa"),),
        )
    with session_factory() as session:
        results = PostgresRelaxedOrFullTextSearchRetriever(session).search(
            RetrievalRequest("palavra_inexistente competência", version_hash)
        )
    assert [item.unit_key for item in results] == ["UNIT:N"]


def test_relaxed_or_preserves_cross_version_isolation(session_factory):
    with session_factory() as session, session.begin():
        hash_a, _ = _seed_version(
            session,
            suffix="RA",
            unit_texts=(("UNIT:RA", "competência administrativa"),),
        )
        hash_b, _ = _seed_version(
            session,
            suffix="RB",
            unit_texts=(("UNIT:RB", "prazo administrativo"),),
        )
    with session_factory() as session:
        retriever = PostgresRelaxedOrFullTextSearchRetriever(session)
        result_a = retriever.search(RetrievalRequest("competência prazo", hash_a))
        result_b = retriever.search(RetrievalRequest("competência prazo", hash_b))
    assert [item.unit_key for item in result_a] == ["UNIT:RA"]
    assert [item.unit_key for item in result_b] == ["UNIT:RB"]


def test_relaxed_or_returns_empty_when_normalization_has_no_lexemes(session_factory):
    with session_factory() as session, session.begin():
        version_hash, _ = _seed_version(
            session,
            suffix="Z",
            unit_texts=(("UNIT:Z", "processo administrativo"),),
        )
    with session_factory() as session:
        results = PostgresRelaxedOrFullTextSearchRetriever(session).search(
            RetrievalRequest("e de a", version_hash)
        )
    assert results == ()


def test_coverage_ranking_orders_one_two_and_three_distinct_matches(session_factory):
    with session_factory() as session, session.begin():
        version_hash, _ = _seed_version(
            session,
            suffix="COV",
            unit_texts=(
                ("UNIT:ONE", "competência"),
                ("UNIT:TWO", "competência prazo"),
                ("UNIT:THREE", "competência prazo decisão"),
            ),
        )
    with session_factory() as session:
        results = PostgresRelaxedOrCoverageFullTextSearchRetriever(session).search(
            RetrievalRequest("competência prazo decisão", version_hash)
        )
    assert [item.unit_key for item in results] == [
        "UNIT:THREE",
        "UNIT:TWO",
        "UNIT:ONE",
    ]


def test_coverage_ranking_counts_repeated_candidate_lexeme_once(session_factory):
    with session_factory() as session, session.begin():
        version_hash, _ = _seed_version(
            session,
            suffix="REP",
            unit_texts=(
                ("UNIT:REPEATED", "competência competência competência competência"),
                ("UNIT:COMPLETE", "competência prazo decisão"),
            ),
        )
    with session_factory() as session:
        results = PostgresRelaxedOrCoverageFullTextSearchRetriever(session).search(
            RetrievalRequest("competência prazo decisão", version_hash)
        )
    assert [item.unit_key for item in results] == ["UNIT:COMPLETE", "UNIT:REPEATED"]


def test_coverage_ranking_uses_ts_rank_cd_for_equal_coverage(session_factory):
    with session_factory() as session, session.begin():
        version_hash, _ = _seed_version(
            session,
            suffix="RANK",
            unit_texts=(
                ("UNIT:LOWER-RANK", "competência prazo"),
                ("UNIT:HIGHER-RANK", "competência competência prazo"),
            ),
        )
    with session_factory() as session:
        results = PostgresRelaxedOrCoverageFullTextSearchRetriever(session).search(
            RetrievalRequest("competência prazo decisão", version_hash)
        )
    assert [item.unit_key for item in results] == [
        "UNIT:HIGHER-RANK",
        "UNIT:LOWER-RANK",
    ]
    assert results[0].score > results[1].score


def test_coverage_ranking_uses_unit_key_for_complete_tie(session_factory):
    common = "competência prazo"
    with session_factory() as session, session.begin():
        version_hash, _ = _seed_version(
            session,
            suffix="TIE",
            unit_texts=(("UNIT:B", common), ("UNIT:A", common)),
        )
    with session_factory() as session:
        results = PostgresRelaxedOrCoverageFullTextSearchRetriever(session).search(
            RetrievalRequest("competência prazo decisão", version_hash)
        )
    assert [item.unit_key for item in results] == ["UNIT:A", "UNIT:B"]


def test_coverage_ranking_returns_empty_for_query_without_lexemes(session_factory):
    with session_factory() as session, session.begin():
        version_hash, _ = _seed_version(
            session,
            suffix="EMPTY",
            unit_texts=(("UNIT:EMPTY", "processo administrativo"),),
        )
    with session_factory() as session:
        results = PostgresRelaxedOrCoverageFullTextSearchRetriever(session).search(
            RetrievalRequest("e de a", version_hash)
        )
    assert results == ()


def test_coverage_ranking_preserves_explicit_version_isolation(session_factory):
    with session_factory() as session, session.begin():
        hash_a, _ = _seed_version(
            session,
            suffix="CA",
            unit_texts=(("UNIT:CA", "competência prazo"),),
        )
        hash_b, _ = _seed_version(
            session,
            suffix="CB",
            unit_texts=(("UNIT:CB", "competência prazo decisão"),),
        )
    with session_factory() as session:
        retriever = PostgresRelaxedOrCoverageFullTextSearchRetriever(session)
        result_a = retriever.search(
            RetrievalRequest("competência prazo decisão", hash_a)
        )
        result_b = retriever.search(
            RetrievalRequest("competência prazo decisão", hash_b)
        )
    assert [item.unit_key for item in result_a] == ["UNIT:CA"]
    assert [item.unit_key for item in result_b] == ["UNIT:CB"]


def test_migration_downgrade_and_upgrade_preserve_expected_index(session_factory):
    environment = os.environ | {"DATABASE_URL": DATABASE_URL}
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "001_v02_foundation_corpus"],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    with session_factory() as session:
        assert (
            session.scalar(
                text(
                    "SELECT count(*) FROM pg_indexes "
                    "WHERE indexname='ix_search_units_fts_portuguese'"
                )
            )
            == 0
        )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "002_v02_postgresql_fts"],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    with session_factory() as session:
        assert (
            session.scalar(
                text(
                    "SELECT count(*) FROM pg_indexes "
                    "WHERE indexname='ix_search_units_fts_portuguese'"
                )
            )
            == 1
        )
