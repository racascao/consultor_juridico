# Consultor Jurídico

Mecanismo CLI-first de consulta jurídica baseado em fontes oficiais,
versionadas e rastreáveis. O MVP2 está sendo reconstruído com escopo reduzido;
nesta etapa existem um corpus funcional e auditável e uma primeira medição de
retrieval lexical, ainda sem geração de consulta jurídica.

## Estado do projeto

A tag `v0.1.0` preserva o MVP1 e permanece imutável. A branch `mvp-v0.2`, na
versão `0.2.0.dev0`, concluiu a Fase 0 e mediu a Fase 1 com a Lei nº
9.784/1999 como ato piloto.

```text
MVP2_STATUS: PHASE_1_LEXICAL_COVERAGE_MEASURED
PILOT_LEGAL_ACT: BR-FED-LEI-9784-1999
PARSER: IMPLEMENTED
CORPUS: MATERIALIZED_AND_AUDITABLE
RETRIEVAL: POSTGRESQL_FTS_STRICT_RELAXED_OR_AND_COVERAGE
FTS: IMPLEMENTED_AND_MEASURED
EMBEDDINGS: NOT_IMPLEMENTED
LLM: NOT_IMPLEMENTED
```

O PostgreSQL v0.2 é isolado do legado:

```text
database: consultor_juridico_v02
volume:   consultor_juridico_v02_pgdata
host:     localhost:5434
```

O banco e o volume do MVP1 não são migrados nem reutilizados. O baseline
Alembic ativo da branch v0.2 cria somente as tabelas da fundação documental;
as migrations históricas continuam preservadas pela tag `v0.1.0`.

## Retrieval lexical da Fase 1

O baseline recebe obrigatoriamente um `version_hash` e pesquisa somente
`SearchUnit.search_text` com a configuração portuguesa do PostgreSQL:
`websearch_to_tsquery`, `to_tsvector`, `ts_rank_cd` e desempate por
`unit_key`. A migration `002_v02_postgresql_fts` adiciona um índice GIN de
expressão, sem alterar a projeção `provision-text/1`.

O DEV congelado contém 40 consultas naturais, cinco em cada uma de oito
categorias. Seu SHA-256 é
`bc47eb6e7364931767fb2305cc9ce5a55ce7763e9f88cb6bbf224609dbe221aa`.
O baseline strict obteve Hit@1/3/5/10 e MRR iguais a `0,000`; um controle
positivo literal passou 3/3, demonstrando que a falha estava na conjunção das
perguntas naturais, não no funcionamento mecânico do FTS. Um único experimento
PostgreSQL-native `RELAXED_OR` elevou Hit@10 para `0,800` e MRR para `0,549`.
Seus oito misses restantes possuem match lexical, mas ficam entre ranks 11 e
59 por diluição do ranking. O experimento posterior
`RELAXED_OR_COVERAGE`, sem mudar os candidatos, elevou Hit@10 para `0,875` e
MRR para `0,661`: três misses entraram no top 10, nenhum foi perdido e uma
posição regrediu de rank 5 para 6. A Fase 1 permanece aberta para revisão.

O relatório e a classificação das 40 falhas estão em
[`docs/retrieval/phase-1-fts-baseline.md`](docs/retrieval/phase-1-fts-baseline.md).
O diagnóstico causal e o experimento de cobertura estão em
[`docs/retrieval/phase-1-relaxed-or-ranking-diagnostic.md`](docs/retrieval/phase-1-relaxed-or-ranking-diagnostic.md)
e
[`docs/retrieval/phase-1-lexical-coverage-ranking.md`](docs/retrieval/phase-1-lexical-coverage-ranking.md).
Não foram usados embeddings, busca vetorial, RRF, reranker, LLM ou RAG.

## Arquitetura da Fase 0

```text
Source
  → SourceSnapshot
  → LegalAct
  → ActVersion
  → Provision
  → SearchUnit
  → SearchUnitProvision
```

- `SourceSnapshot.raw_bytes` preserva exatamente a resposta HTTP, com SHA-256
  calculado sobre esses bytes e proteção de imutabilidade no PostgreSQL.
- A aquisição usa `If-None-Match` e `If-Modified-Since` quando existem
  metadados anteriores. `304` reutiliza a captura sem alterar `acquired_at`;
  uma resposta `200` com o mesmo SHA também é idempotente.
- O contrato validado da fonte é `windows-1252`, sempre com decoding estrito.
- O parser `planalto-lei-structural/1` opera em memória e termina o documento
  estrutural no primeiro `</html>`. A cauda dinâmica posterior permanece intacta
  em `raw_bytes`, mas não entra na árvore jurídica.
- `ARTICLE` é o contêiner estrutural; `CAPUT` guarda seu texto normativo. As
  demais classes observadas são `DOCUMENT_ROOT`, `CHAPTER`, `PARAGRAPH` e
  `INCISO`.
- A materialização valida parser, cobertura e projeção antes de uma única
  transação. Falhas causam rollback integral.
- Não existe versão `active`, `current` ou `latest`. Cada `ActVersion` possui
  identidade natural e `version_hash` derivados explicitamente do snapshot e
  das versões do parser e da projeção.
- A projeção `provision-text/1` é intencionalmente simples:
  `SearchUnit.search_text = Provision.citation_text`, sem enriquecimento.
- Reprojeção é offline: recebe um SHA de snapshot persistido e não possui
  cliente HTTP ou fallback remoto.

Os contratos completos estão em
[`docs/corpus/foundation-corpus-v02.md`](docs/corpus/foundation-corpus-v02.md).
A investigação da fonte está em
[`docs/corpus/lei-9784-investigation.md`](docs/corpus/lei-9784-investigation.md).

## Banco e corpus

Com o PostgreSQL v0.2 ativo:

```bash
docker compose up -d db
uv run consultor-juridico db migrate
uv run consultor-juridico db status
```

Adquirir a fonte oficial sem materializá-la:

```bash
uv run consultor-juridico corpus adquirir
```

Materializar ou reprojetar um snapshot explicitamente, sem HTTP:

```bash
uv run consultor-juridico corpus materializar --snapshot-sha <sha256>
uv run consultor-juridico corpus reprojetar --snapshot-sha <sha256>
```

Listar e auditar versões:

```bash
uv run consultor-juridico corpus versoes
uv run consultor-juridico corpus auditar --version-hash <hash>
```

Rastrear uma unidade textual até a captura oficial:

```bash
uv run consultor-juridico corpus rastrear \
  --version-hash <hash> \
  --unit-key <unit_key>
```

Executar uma busca lexical isolada:

```bash
uv run consultor-juridico retrieval buscar \
  --mode strict \
  --version-hash <hash> \
  --limit 10 \
  "pergunta"
```

O evaluator grava um novo JSON e recusa sobrescrever resultados existentes:

```bash
uv run consultor-juridico eval retrieval \
  --mode relaxed-or-coverage \
  --dataset evaluation/datasets/lei_9784_retrieval_dev_v1.json \
  --version-hash <hash> \
  --output <novo-arquivo.json>
```

## Desenvolvimento

```bash
uv sync
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
```

Os testes automáticos não acessam o Planalto. A integração PostgreSQL usa um
banco descartável indicado por `V02_TEST_DATABASE_URL`.

## Governança e roadmap

A Fase 0 foi aceita depois da conferência humana de cinco amostras distribuídas
no documento. `citation_text`, limites estruturais, hierarquia, proveniência,
SourceSnapshot e URL oficial foram validados. A Fase 1 implementou e mediu uma
única vez o baseline strict e uma única vez a variante RELAXED_OR; aguarda
revisão humana do experimento `RELAXED_OR_COVERAGE` antes de qualquer nova
hipótese.

```text
Fase 0: Fundação e Corpus (concluída)
  → Fase 1: Retrieval isolado (strict + RELAXED_OR + coverage medidos; revisão pendente)
  → Gold Evidence
  → Integração
  → DEV
  → HOLDOUT
  → Teste manual
```

A governança do HOLDOUT está documentada em
[`docs/governance/holdout.md`](docs/governance/holdout.md), mas nenhum dataset
HOLDOUT foi criado ou lido nesta fase. O DEV conhecido da Fase 1 não é um
HOLDOUT. Não há alegação atual de qualidade ou prontidão do consultor.
