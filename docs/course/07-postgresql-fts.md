# 07. PostgreSQL FTS

## Objetivo

Implementar retrieval lexical funcional sobre SearchUnits de uma versão
explícita.

## Onde estamos e incremento

```text
question + version_hash → PostgreSQL FTS → RetrievalCandidate[]
```

## Arquivos desta etapa

- `domain/retrieval.py`;
- `application/retrieval/ports.py` e `services.py`;
- `infrastructure/retrieval.py`;
- `tests/test_v02_retrieval.py` e integração PostgreSQL correspondente.

## Conceitos necessários

`to_tsvector('portuguese', texto)` reduz texto a lexemas pesquisáveis. Uma
`tsquery` representa os lexemas da pergunta; `@@` testa correspondência e
`ts_rank_cd` pontua proximidade/densidade. O índice GIN do capítulo 3 acelera
esse predicado.

Uma consulta AND estrita perde unidades quando a pergunta contém palavras que
não aparecem juntas. O runtime cria termos OR, mede a fração de lexemas
encontrados e pondera cada match pela raridade no corpus.

## Contratos

```python
class RetrievalMode(StrEnum):
    STRICT = "STRICT"
    RELAXED_OR = "RELAXED_OR"
    RELAXED_OR_COVERAGE = "RELAXED_OR_COVERAGE"


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    question: str
    version_hash: str
    limit: int = 10


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    rank: int
    search_unit_id: UUID
    unit_key: str
    score: float
    provision_stable_keys: tuple[str, ...]
    search_text: str
```

Valide pergunta não vazia, hash hexadecimal e limite positivo em
`RetrievalRequest.__post_init__`.

## Porta e caso de uso

```python
class SearchUnitRetriever(Protocol):
    implementation_name: str
    retrieval_config: Mapping[str, str | int]

    def search(self, request: RetrievalRequest) -> tuple[RetrievalCandidate, ...]: ...
    def context(self, version_hash: str) -> RetrievalContext: ...
    def provision_keys(self, version_hash: str) -> frozenset[str]: ...


class RetrieveSearchUnits:
    def __init__(self, retriever: SearchUnitRetriever) -> None:
        self._retriever = retriever

    def execute(self, request: RetrievalRequest):
        return self._retriever.search(request)
```

## SQL final

O SQL real usa CTEs para extrair lexemas, contar document frequency e calcular
cobertura. O recorte didático abaixo preserva a ordenação essencial:

```sql
WITH query_terms AS (...), candidates AS (...), scored AS (...)
SELECT su.id, su.unit_key, su.search_text,
       SUM(idf_weight) / NULLIF(SUM(total_idf_weight), 0) AS weighted_coverage,
       COUNT(DISTINCT matched_lexeme)::float / query_lexeme_count AS coverage,
       ts_rank_cd(to_tsvector('portuguese', su.search_text), query) AS text_rank
FROM search_units su
JOIN act_versions av ON av.id = su.act_version_id
WHERE av.version_hash = :version_hash
GROUP BY su.id, query_lexeme_count
ORDER BY weighted_coverage DESC, coverage DESC, text_rank DESC, su.unit_key ASC
LIMIT :limit;
```

Consulte `infrastructure/retrieval.py` da tag para as CTEs literais. A chave
determinística resolve empates; `version_hash` impede vazamento entre versões.

## Implementação do adapter

`PostgresRelaxedOrCoverageFullTextSearchRetriever.search` executa o SQL com
parâmetros e converte mappings em candidates enumerados a partir de 1. Nunca
concatene a pergunta no SQL.

```python
rows = session.execute(search_sql, {
    "question": request.question,
    "version_hash": request.version_hash,
    "limit": request.limit,
}).mappings()
return tuple(RetrievalCandidate(rank=i, ...) for i, row in enumerate(rows, 1))
```

## Testes

Unitariamente, use fake rows para contrato, ordenação e contexto ausente. No
PostgreSQL, materialize fixtures e teste strict versus relaxed, coverage,
raridade, limite, isolamento por versão e desempate.

```bash
uv run pytest tests/test_v02_retrieval.py -q
V02_TEST_DATABASE_URL=postgresql+psycopg://... uv run pytest \
  tests/integration/test_v02_retrieval_postgresql.py -q
```

Exemplo esperado: uma pergunta normativa retorna até dez candidates; cada um
traz rank, score, texto e stable keys materializáveis.

## Decisões

Vector/RRF não integram o caminho principal porque não demonstraram ganho geral
estável. Veja [Experimentos de retrieval](../experiments/retrieval.md).

## Checkpoint

Com banco materializado, uma busca retorna candidates somente da versão pedida,
com ordem repetível e Hit@10 avaliável. Ainda não existe EvidenceSet nem LLM.

**Anterior:** [SearchUnits](06-search-units.md).  
**Próximo:** [Evidence Assembly](08-evidence-assembly.md).
