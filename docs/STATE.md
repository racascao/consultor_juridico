# Estado canônico — MVP2

```text
VERSION: 0.2.0
TAG: 0.2.0
RELEASE_COMMIT: c805ba8eddcbaa91737cb6f9b8cd8f4a6f7fcc3d
BRANCH_OFICIAL: main
STATUS: CLOSED
FINAL_DECISION: MVP2_ACCEPTED_WITH_KNOWN_LIMITATIONS
```

## Freeze

```text
ANSWERER: gold-evidence-selected-answerer/1
ANSWERER_SHA256: d07d5b3ca9feb9c16193a400609215c55ecd5e04f8e26429a035ee51f950e12a
RUNTIME: integrated-runtime-mvp2/1
RUNTIME_SHA256: 5f0df6b41f0d35fcba0a514777a2370385620007ff3e6122473ca6793067514d
```

## Corpus e runtime

```text
CORPUS: Lei Federal nº 9.784/1999
ACT_CODE: BR-FED-LEI-9784-1999
SOURCE_SHA256: b4abab2e47732f76a16a99e8b00311dcb420b378f89e99c096b609ae84529261
PROVISIONS: 322
SEARCH_UNITS: 242
RETRIEVAL: POSTGRESQL_FTS_RELAXED_OR_WEIGHTED_COVERAGE
STRUCTURAL_EXPANSION: DIRECT_CHILDREN_ONLY_MAX_8_GLOBAL_MAX_24
MODEL: gemma4:12b
QUERY_MODES: LEGAL_RULE,CASE_APPLICATION
QUERY_TIME_WEB_FETCH: DISABLED
```

## Limitações

Corpus de um ato; retrieval lexical; coverage imperfeita; contrato e completude
não perfeitos no HOLDOUT; `CASE_APPLICATION` não aplica fatos; streaming real
fora do freeze. O HOLDOUT v1 está fechado para desenvolvimento.

## Navegação

- [Curso](course/index.md)
- [Referência](reference/architecture.md)
- [Experimentos](experiments/index.md)

A próxima evolução funcional pertence ao MVP3 ou a uma versão posterior.
