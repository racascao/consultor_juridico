# Estado canônico — MVP2

## Situação

```text
PROJECT: consultor_juridico
MVP: MVP2
BRANCH: mvp-v0.2
VERSION: 0.2.0.dev0
MVP2_STATUS: CLOSED
MVP2_FINAL_DECISION: MVP2_ACCEPTED_WITH_KNOWN_LIMITATIONS
POST_HOLDOUT_METHOD_PHASE: NOT_STARTED
NEXT_ACTION: NONE_FOR_MVP2
```

## Corpus

```text
LEGAL_ACT: Lei Federal nº 9.784/1999
ACT_CODE: BR-FED-LEI-9784-1999
SOURCE_KIND: LOCAL_VERSIONED
SOURCE_PATH: docs/corpus/artifacts/lei-9784-1999-planalto-2026-08-31.raw.html
SOURCE_SHA256: b4abab2e47732f76a16a99e8b00311dcb420b378f89e99c096b609ae84529261
ACT_VERSION_HASH: bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6
PARSER: planalto-lei-structural/1
PROJECTION: provision-text/1
PROVISIONS: 322
SEARCH_UNITS: 242
CORPUS_IDEMPOTENCY: PASS
```

`SOURCE_URL` é proveniência; não há acesso web no runtime de consulta.

## Runtime congelado

```text
INTEGRATED_RUNTIME_FREEZE: COMPLETE
FREEZE_ID: integrated-runtime-mvp2/1
FREEZE_SHA256: 5f0df6b41f0d35fcba0a514777a2370385620007ff3e6122473ca6793067514d
FROZEN_BASELINE_COMMIT: ea888a5f70d570e0ab4d505e4b3f5d695eb78cd5
RETRIEVAL: POSTGRESQL_FTS_RELAXED_OR_WEIGHTED_COVERAGE
STRUCTURAL_EXPANSION: DIRECT_CHILDREN_ONLY_MAX_8_GLOBAL_MAX_24
QUERY_MODES: LEGAL_RULE,CASE_APPLICATION
RUNTIME_WEB_FETCH: NOT_IMPLEMENTED
VECTOR: NOT_IMPLEMENTED
RRF: NOT_IMPLEMENTED
```

## Answerer

```text
ANSWERER_FREEZE_ID: gold-evidence-selected-answerer/1
ANSWERER_FREEZE_SHA256: d07d5b3ca9feb9c16193a400609215c55ecd5e04f8e26429a035ee51f950e12a
MODEL: gemma4:12b
MODEL_DIGEST: 4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c
PROMPT: gold-evidence-answering/2
THINKING: disabled
OLLAMA_FORMAT: json
OUTPUT_CONTRACT: STRICT_JSON_FAIL_CLOSED
OLLAMA_DEPLOYMENT: DOCKER_COMPOSE_ONLY
OLLAMA_INTERNAL_URL: http://ollama:11434
OLLAMA_HOST_URL: http://localhost:11435
```

## Contrato de modos

`LEGAL_RULE` executa retrieval, assembly, answerer e validação. O caller declara
o modo. `CASE_APPLICATION` retorna `CLARIFY` antes de abrir banco ou cliente LLM,
com retrieval e answerer não executados e citações vazias. O modo nunca é
inferido pela pergunta.

## Blind HOLDOUT

```text
HOLDOUT_STATUS: CLOSED_FOR_DEVELOPMENT
HOLDOUT_FIRST_MEASUREMENT: COMPLETE
HUMAN_REVIEW: COMPLETE
HOLDOUT_TUNING: NO
CASE_APPLICATION_BOUNDARY: VALIDATED
AUTOMATIC_PASS: 25/36
EXPECTED_DECISION_MATCH: 30/36
HUMAN_LEGAL_CORRECTNESS: 34/36
HUMAN_GROUNDEDNESS: 36/36
HUMAN_COMPLETENESS: 32/36
HUMAN_MODE_BOUNDARY: 36/36
HUMAN_ALL_PASS: 32/36
FORMAL_PREDEFINED_ACCEPTANCE_THRESHOLD: ABSENT
```

## Limitações conhecidas

- corpus limitado à Lei nº 9.784/1999;
- retrieval obrigatório inicial `26/44`, elevado a `40/44` pelo assembly;
- output schema válido em `34/36`;
- correção jurídica humana `34/36` e completude `32/36`;
- `CASE_APPLICATION` não aplica fatos concretos;
- sem runtime web fetch, vetor, embeddings ou RRF;
- divergências entre métricas automáticas e revisão humana.

## Referências

- [Arquitetura](ARCHITECTURE_MVP2.md)
- [Experimentos](EXPERIMENTS_MVP2.md)
- `evaluation/model_selection/gold_evidence_selected_answerer_freeze_v1.json`
- `evaluation/runtime_freeze/integrated_runtime_mvp2_freeze_v1.json`
- `evaluation/results/blind_holdout_mvp2_v1/blind_holdout_final_assessment_v1.json`

Qualquer evolução pertence a uma fase pós-HOLDOUT independente. O HOLDOUT v1
nunca vira DEV.
