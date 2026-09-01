"""Adapter PostgreSQL do baseline Full Text Search."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from consultor_juridico.domain.retrieval import (
    RetrievalCandidate,
    RetrievalContext,
    RetrievalRequest,
)

_STRICT_SEARCH_SQL = text(
    """
    WITH query AS (
        SELECT websearch_to_tsquery('portuguese', :question) AS value
    )
    SELECT
        su.id AS search_unit_id,
        su.unit_key,
        su.search_text,
        ts_rank_cd(
            to_tsvector('portuguese', su.search_text),
            query.value
        ) AS score,
        array_agg(p.stable_key ORDER BY sup.position) AS provision_stable_keys
    FROM search_units AS su
    JOIN act_versions AS av ON av.id = su.act_version_id
    JOIN search_unit_provisions AS sup ON sup.search_unit_id = su.id
    JOIN provisions AS p ON p.id = sup.provision_id
    CROSS JOIN query
    WHERE av.version_hash = :version_hash
      AND to_tsvector('portuguese', su.search_text) @@ query.value
    GROUP BY su.id, su.unit_key, su.search_text, query.value
    ORDER BY score DESC, su.unit_key ASC
    LIMIT :limit
    """
)

_RELAXED_OR_SEARCH_SQL = text(
    """
    WITH normalized AS (
        SELECT tsvector_to_array(
            to_tsvector('portuguese', :question)
        ) AS lexemes
    ),
    query AS (
        SELECT websearch_to_tsquery(
            'portuguese',
            array_to_string(lexemes, ' OR ')
        ) AS value
        FROM normalized
    )
    SELECT
        su.id AS search_unit_id,
        su.unit_key,
        su.search_text,
        ts_rank_cd(
            to_tsvector('portuguese', su.search_text),
            query.value
        ) AS score,
        array_agg(p.stable_key ORDER BY sup.position) AS provision_stable_keys
    FROM search_units AS su
    JOIN act_versions AS av ON av.id = su.act_version_id
    JOIN search_unit_provisions AS sup ON sup.search_unit_id = su.id
    JOIN provisions AS p ON p.id = sup.provision_id
    CROSS JOIN query
    WHERE av.version_hash = :version_hash
      AND to_tsvector('portuguese', su.search_text) @@ query.value
    GROUP BY su.id, su.unit_key, su.search_text, query.value
    ORDER BY score DESC, su.unit_key ASC
    LIMIT :limit
    """
)

_RELAXED_OR_COVERAGE_SEARCH_SQL = text(
    """
    WITH normalized AS (
        SELECT tsvector_to_array(
            to_tsvector('portuguese', :question)
        ) AS lexemes
    ),
    query AS (
        SELECT
            lexemes,
            cardinality(lexemes) AS lexeme_count,
            websearch_to_tsquery(
                'portuguese',
                array_to_string(lexemes, ' OR ')
            ) AS value
        FROM normalized
    ),
    ranked_units AS (
        SELECT
            su.id AS search_unit_id,
            su.unit_key,
            su.search_text,
            ts_rank_cd(
                to_tsvector('portuguese', su.search_text),
                query.value
            ) AS score,
            (
                SELECT count(DISTINCT query_lexeme)
                FROM unnest(query.lexemes) AS lexeme(query_lexeme)
                WHERE query_lexeme = ANY(
                    tsvector_to_array(
                        to_tsvector('portuguese', su.search_text)
                    )
                )
            )::double precision / NULLIF(query.lexeme_count, 0)
                AS query_coverage
        FROM search_units AS su
        JOIN act_versions AS av ON av.id = su.act_version_id
        CROSS JOIN query
        WHERE av.version_hash = :version_hash
          AND query.lexeme_count > 0
          AND to_tsvector('portuguese', su.search_text) @@ query.value
    )
    SELECT
        ranked.search_unit_id,
        ranked.unit_key,
        ranked.search_text,
        ranked.score,
        ranked.query_coverage,
        array_agg(p.stable_key ORDER BY sup.position) AS provision_stable_keys
    FROM ranked_units AS ranked
    JOIN search_unit_provisions AS sup
      ON sup.search_unit_id = ranked.search_unit_id
    JOIN provisions AS p ON p.id = sup.provision_id
    GROUP BY
        ranked.search_unit_id,
        ranked.unit_key,
        ranked.search_text,
        ranked.score,
        ranked.query_coverage
    ORDER BY
        ranked.query_coverage DESC,
        ranked.score DESC,
        ranked.unit_key ASC
    LIMIT :limit
    """
)

_CONTEXT_SQL = text(
    """
    SELECT
        la.act_code AS legal_act_code,
        av.id AS act_version_id,
        av.version_hash,
        ss.sha256 AS source_snapshot_sha256,
        av.parser_name,
        av.parser_version,
        av.projection_name,
        av.projection_version
    FROM act_versions AS av
    JOIN legal_acts AS la ON la.id = av.legal_act_id
    JOIN source_snapshots AS ss ON ss.id = av.source_snapshot_id
    WHERE av.version_hash = :version_hash
    """
)

_PROVISION_KEYS_SQL = text(
    """
    SELECT p.stable_key
    FROM provisions AS p
    JOIN act_versions AS av ON av.id = p.act_version_id
    WHERE av.version_hash = :version_hash
    """
)


class _PostgresFullTextSearchRetriever:
    implementation_name: str
    search_sql: object
    retrieval_config: dict[str, str | int]

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, request: RetrievalRequest) -> tuple[RetrievalCandidate, ...]:
        rows = self._session.execute(
            self.search_sql,
            {
                "question": request.question,
                "version_hash": request.version_hash,
                "limit": request.limit,
            },
        ).mappings()
        return tuple(
            RetrievalCandidate(
                rank=rank,
                search_unit_id=UUID(str(row["search_unit_id"])),
                unit_key=row["unit_key"],
                score=float(row["score"]),
                provision_stable_keys=tuple(row["provision_stable_keys"]),
                search_text=row["search_text"],
            )
            for rank, row in enumerate(rows, start=1)
        )

    def context(self, version_hash: str) -> RetrievalContext:
        row = (
            self._session.execute(_CONTEXT_SQL, {"version_hash": version_hash})
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError(f"ActVersion não encontrada: {version_hash}")
        return RetrievalContext(
            legal_act_code=row["legal_act_code"],
            act_version_id=UUID(str(row["act_version_id"])),
            version_hash=row["version_hash"],
            source_snapshot_sha256=row["source_snapshot_sha256"],
            parser_name=row["parser_name"],
            parser_version=row["parser_version"],
            projection_name=row["projection_name"],
            projection_version=row["projection_version"],
        )

    def provision_keys(self, version_hash: str) -> frozenset[str]:
        return frozenset(
            self._session.scalars(_PROVISION_KEYS_SQL, {"version_hash": version_hash})
        )


class PostgresFullTextSearchRetriever(_PostgresFullTextSearchRetriever):
    """Baseline estrito preservado: websearch_to_tsquery usa AND."""

    implementation_name = "POSTGRESQL_FTS_STRICT"
    search_sql = _STRICT_SEARCH_SQL
    retrieval_config = {
        "text_search_config": "portuguese",
        "query_function": "websearch_to_tsquery",
        "candidate_generation": "STRICT",
        "rank_function": "ts_rank_cd",
        "ranking_primary": "ts_rank_cd DESC",
        "max_rank": 10,
        "tie_break": "unit_key ASC",
    }


class PostgresRelaxedOrFullTextSearchRetriever(_PostgresFullTextSearchRetriever):
    """Variante OR com lexemas normalizados exclusivamente pelo PostgreSQL."""

    implementation_name = "POSTGRESQL_FTS_RELAXED_OR"
    search_sql = _RELAXED_OR_SEARCH_SQL
    retrieval_config = {
        "text_search_config": "portuguese",
        "query_function": "websearch_to_tsquery",
        "candidate_generation": "RELAXED_OR",
        "rank_function": "ts_rank_cd",
        "ranking_primary": "ts_rank_cd DESC",
        "max_rank": 10,
        "tie_break": "unit_key ASC",
    }


class PostgresRelaxedOrCoverageFullTextSearchRetriever(
    _PostgresFullTextSearchRetriever
):
    """Variante OR ordenada por cobertura lexical distinta da pergunta."""

    implementation_name = "POSTGRESQL_FTS_RELAXED_OR_COVERAGE"
    search_sql = _RELAXED_OR_COVERAGE_SEARCH_SQL
    retrieval_config = {
        "text_search_config": "portuguese",
        "query_function": "websearch_to_tsquery",
        "candidate_generation": "RELAXED_OR",
        "rank_function": "ts_rank_cd",
        "ranking_primary": "query_coverage DESC",
        "ranking_secondary": "ts_rank_cd DESC",
        "query_coverage": ("DISTINCT_MATCHED_QUERY_LEXEMES / DISTINCT_QUERY_LEXEMES"),
        "max_rank": 10,
        "tie_break": "unit_key ASC",
    }
