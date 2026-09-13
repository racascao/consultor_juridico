# Blind HOLDOUT MVP2 v1

## Estado

```text
HOLDOUT_CREATED: YES
HOLDOUT_SEALED: YES
HOLDOUT_RUNTIME_FIRST_READ: YES
HOLDOUT_RUNTIME_FIRST_READ_AT: 2026-09-13T19:37:36.652025+00:00
BLIND_HOLDOUT_FIRST_MEASUREMENT: COMPLETE
HOLDOUT_TUNING: NO
HUMAN_REVIEW_HOLDOUT: COMPLETE
MVP2_FINAL_DECISION: MVP2_ACCEPTED_WITH_KNOWN_LIMITATIONS
```

A primeira e única campanha cega oficial executou 36 casos contra o runtime
`integrated-runtime-mvp2/1`, SHA-256
`5f0df6b41f0d35fcba0a514777a2370385620007ff3e6122473ca6793067514d`.
Não houve retry, stability, alteração de caso ou tuning. O corpus foi a versão
local `bfa031c3...8cc6`; nenhum acesso web ocorreu no runtime.

## Integridade

O pacote permaneceu byte-identical antes e depois da campanha:

```text
dataset: c9136a1f359e1c4e697defa4b7a3957aa0c1559f3e8b233cd2618f2b848014c0
mapping: eca28c6ebe828ecd963325059c9b3dcbb3eb38fcdca14f3f3058ea7ee89837c9
```

O mapping lacrado definiu 31 casos `LEGAL_RULE` e cinco
`CASE_APPLICATION`. Os cinco casos de aplicação retornaram `CLARIFY` sem
retrieval, LLM ou citações, sem violações da política de modo.

## Resultado automático

```text
JSON_VALID: 36/36
OUTPUT_SCHEMA_VALID: 34/36
DECISION_PAYLOAD_VALID: 34/36
EXPECTED_DECISION_MATCH: 30/36
AUTOMATIC_PASS: 25/36
FALSE_ABSTENTION: 3
UNSAFE_INSUFFICIENT: 1
MISSED_CLARIFICATION: 0
INVALID_CITATIONS: 0
OUT_OF_EVIDENCE: 0
REQUIRED_CITATION_COVERED: 22/31 LEGAL_RULE
RETRIEVAL_REQUIRED_CITATION_RECALL: 26/44 = 0.590909
EVIDENCE_ASSEMBLY_REQUIRED_CITATION_RECALL: 40/44 = 0.909091
LEGAL_RULE_FULL_EVIDENCE_COVERAGE: 27/31
LEGAL_RULE_EXPECTED_DECISION_MATCH: 25/31
CASE_APPLICATION_EXPECTED_DECISION_MATCH: 5/5
CASE_APPLICATION_CLARIFY_RATE: 5/5
CASE_APPLICATION_RETRIEVAL_CALLS: 0
CASE_APPLICATION_LLM_CALLS: 0
QUERY_MODE_POLICY_VIOLATIONS: 0
TIMEOUTS: 0
```

As falhas automáticas foram classificadas como quatro `RETRIEVAL_MISS`, três
`ANSWERER_DECISION_FAILURE`, uma `ANSWERER_OUTPUT_CONTRACT_FAILURE` e três
`MATERIAL_REVIEW_REQUIRED`. Houve uma resposta `ANSWER` em caso esperado como
evidência insuficiente (`RISK-01=1`). Esse resultado é preservado, não corrigido.
`RISK-02`, `RISK-03` e `RISK-04` dependem da revisão material humana;
`RISK-08=NOT_MEASURED_SINGLE_RUN`.

## Performance

```text
LEGAL_RULE_MEAN_LATENCY_MS: 11029.718
LEGAL_RULE_MEDIAN_LATENCY_MS: 9283.696
LEGAL_RULE_MAX_LATENCY_MS: 27601.891
CASE_APPLICATION_MEAN_LATENCY_MS: 0.418
CASE_APPLICATION_MEDIAN_LATENCY_MS: 0.024
CASE_APPLICATION_MAX_LATENCY_MS: 1.960
TOTAL_LLM_GENERATION_TIME_MS: 341921.262
```

## Artefatos imutáveis

```text
blind_holdout_raw_v1.json: be2a543b47cb0cd1637501f7bb32d8db58ac5773457ec0374a460826fa819d2e
blind_holdout_automatic_v1.json: c2e877a14b9dd49e6a5690e5d08c83db67bc967bdc3e4b06a8129a94fff8ed98
blind_holdout_retrieval_diagnostic_v1.json: 96484436282f84ba7652e23ea418919ccc824f9cf4666e27e9ba5c83aaaa29c4
blind_holdout_human_review_v1.json: 93b4f4d18975a36331d58ffa2884294eda979d1782ec7b001dc28a8bce35da68
blind_holdout_vs_integrated_dev_v2_v1.json: 97784166aba23036f3e6e4c8167e74275f85964e6f9dd49ec3cd7509175f40c2
```

Os artefatos ficam em `evaluation/results/blind_holdout_mvp2_v1/`. O template
de revisão permanece vazio e nenhum LLM judge foi utilizado.

## Consolidação humana

O arquivo preenchido foi validado pelo SHA-256
`0ce5772b49435c1845afd487654fc96199ccde4aebddfd6d72ab448a267a5eae`.
A consolidação preservou todos os julgamentos e notas:

```text
LEGAL_CORRECTNESS: 34/36
GROUNDEDNESS: 36/36
COMPLETENESS: 32/36
MODE_BOUNDARY_CORRECTNESS: 36/36
HUMAN_ALL_PASS: 32/36
```

Falharam dimensões humanas em `HOLDOUT-003`, `HOLDOUT-014`, `HOLDOUT-024`
e `HOLDOUT-029`. Houve nove divergências entre o passe automático e o all-pass
humano. Em particular, `HOLDOUT-027` preserva `AUTOMATIC_RISK_01=OBSERVED`, mas
`HUMAN_CONFIRMED_RISK_01=NO`: o gold e a decisão automática não foram alterados.
Dos três false abstentions automáticos, `HOLDOUT-006` e `HOLDOUT-008` passaram
em todas as dimensões substantivas humanas; `HOLDOUT-003` não passou.

## Conclusão

Não existia threshold formal pré-HOLDOUT. A decisão é, portanto, qualitativa e
não redefine sucesso retroativamente: `MVP2_ACCEPTED_WITH_KNOWN_LIMITATIONS`.
O runtime demonstrou groundedness humano integral, boundary de aplicação de caso
integralmente validado e forte ganho da expansão estrutural (`26/44` provisions
no retrieval inicial para `40/44` no assembly). Permanecem limitações reais de
retrieval, contrato de output, correção e completude.

O HOLDOUT v1 está encerrado como instrumento de avaliação e não pode virar DEV.
Qualquer evolução deverá ser uma `POST_HOLDOUT_METHOD_PHASE`, com novo baseline,
hipótese e datasets de desenvolvimento. Não houve tuning pós-HOLDOUT.
