# Arquitetura do Consultor Jurídico — MVP2

## 1. Objetivo do MVP2

O MVP2 é uma aplicação CLI-first de RAG jurídico local. Responde perguntas
normativas a partir de corpus oficial versionado, com evidências e citações
auditáveis, sem tratar o modelo como fonte jurídica. PostgreSQL e Ollama são
serviços locais do Docker Compose; não há frontend ou API web. O bootstrap pode
adquirir a fonte oficial, mas não há acesso web durante consultas.

## 2. Escopo do corpus

O corpus contém a Lei nº 9.784/1999, ato `BR-FED-LEI-9784-1999`, com
`SOURCE_KIND=LOCAL_VERSIONED`. A captura canônica é
`docs/corpus/artifacts/lei-9784-1999-planalto-2026-08-31.raw.html`, SHA-256
`b4abab2e47732f76a16a99e8b00311dcb420b378f89e99c096b609ae84529261`.
O parser `planalto-lei-structural/1` usa `windows-1252` estrito e a projeção
`provision-text/1` cria SearchUnits. O `version_hash` congelado é
`bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6`.
A URL do Planalto é proveniência. `BOOTSTRAP_WEB_FETCH=ENABLED` somente quando o
snapshot esperado está ausente; `QUERY_TIME_WEB_FETCH=DISABLED`.

## 3. Arquitetura de alto nível

```text
LEGAL_RULE
Pergunta → PostgreSQL FTS → SearchUnits → expansão de filhos diretos
         → Evidence Assembly → answerer → validação JSON
         → Citation Validation → RagResult auditável

CASE_APPLICATION
Pergunta → CLARIFY determinístico
         → retrieval=NOT_EXECUTED → answerer=NOT_EXECUTED → citations=[]
```

`QueryMode` é explícito. Inferência pelo texto criaria um classifier implícito e
não auditável; por isso o caller deve informar o modo.

## 4. Componentes

- **Corpus:** `SourceSnapshot` preserva bytes/hash; `ActVersion` identifica uma
  materialização completa.
- **Parser:** produz `Provision` hierárquica com ordem, `stable_key`, texto,
  status e locator.
- **Modelo relacional:** migrations Alembic criam snapshots, atos, versões,
  provisions, SearchUnits e vínculos.
- **SearchUnits:** unidades recuperáveis ligadas às provisions sustentadoras.
- **Retrieval:** PostgreSQL FTS em português e versão explícita.
- **Expansão:** adiciona filhos diretos em ordem documental, com deduplicação.
- **Evidence Assembly:** preserva texto, locator, URL e hash do snapshot.
- **Answerer:** Ollama congelado, sem retry semântico ou reparo pós-geração.
- **Contrato:** JSON com `decision`, `answer` e `citations`; falha fechada.
- **Citation Validation:** somente `stable_key` presente na evidência da consulta.
- **CLI/trace:** administração, consulta e ranks/evidências/identidades auditáveis.
- **Bootstrap:** orquestrador idempotente sobre migrations, aquisição,
  materialização, auditoria e provisionamento do modelo; não altera o motor RAG.
- **Interface Rich:** apresenta modelo, readiness e indicador de processamento;
  não altera o payload `stream=false` nem simula streaming do answerer.

## 5. Retrieval congelado

O runtime usa `POSTGRESQL_FTS_RELAXED_OR_WEIGHTED_COVERAGE`: candidatos por OR,
ordenados por cobertura da pergunta, score textual e chave determinística, com
ponderação pela frequência documental. Vector e RRF não demonstraram ganho geral
que justificasse a complexidade e não integram o runtime.

A expansão `DIRECT_CHILDREN_ONLY` acrescenta até oito filhos por pai e no máximo
24 EvidenceItems, seguindo `parent_id` e `document_order`, com deduplicação.

## 6. Answerer congelado

```text
freeze: gold-evidence-selected-answerer/1
model: gemma4:12b
digest: 4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c
prompt: gold-evidence-answering/2
thinking: disabled
format: json
temperature: 0.7
top_p: 0.8
top_k: 20
repeat_penalty: 1.0
num_predict: 1024
num_ctx: 8192
stream: false
timeout: 180 seconds
```

O artifact canônico é
`evaluation/model_selection/gold_evidence_selected_answerer_freeze_v1.json`,
SHA-256 `d07d5b3ca9feb9c16193a400609215c55ecd5e04f8e26429a035ee51f950e12a`.

## 7. Comparativo de modelos

| Modelo | Automatic pass | Correção | Groundedness | Completude | Human all-pass | Strict | Veredito |
|---|---:|---:|---:|---:|---:|---:|---|
| Qwen3 4B | 25/32 | 29/32 | 29/32 | 25/32 | 25/32 | 22/32 | REJECT |
| Qwen3.5 9B | 27/32 | 29/32 | 29/32 | 26/32 | 26/32 | 25/32 | REJECT |
| Phi-4 Mini 3.8B | 21/32 | 26/32 | 28/32 | 18/32 | 17/32 | 16/32 | REJECT |
| Gemma3 4B | 1/32 | 23/32 | 28/32 | 19/32 | 18/32 | 1/32 | REJECT |
| Gemma4 12B baseline | 12/32 | 32/32 | 32/32 | 29/32 | 29/32 | 12/32 | RECONSIDER |

A reconsideração do Gemma4 alterou somente `ollama_format=json`:

| Métrica | Baseline | `format=json` |
|---|---:|---:|
| JSON válido | 13/32 | 32/32 |
| Schema/payload válido | 12/32 | 31/32 |
| Decisão esperada | 12/32 | 30/32 |
| Automatic pass | 12/32 | 30/32 |
| Cobertura obrigatória | 18/32 | 32/32 |
| Estabilidade | 5/12 | 12/12 |
| Correção / groundedness | 32/32 | 32/32 |
| Completude / human all-pass | 29/32 | 29/32 |
| Strict | 12/32 | 29/32 |

Gemma4 não foi escolhido pelo score automático inicial, mas pela melhor
combinação material de correção, groundedness, completude, prudência,
estabilidade e resistência a erros de polaridade. Seu bloqueio dominante era de
interface; `format=json` o resolveu sem mudar prompt, dataset ou regra por caso.
Nos demais candidatos, as falhas dominantes eram semânticas ou jurídicas.

```text
GEMMA4_BASELINE_VERDICT: RECONSIDER
GEMMA4_FORMAT_JSON_VERDICT: ACCEPT
FINAL_LEGAL_ANSWERER: ACCEPTED
```

## 8. Regras arquiteturais

- sem fine-tuning ou regra por `case_id`, artigo ou pergunta;
- nenhuma heurística derivada do HOLDOUT;
- `QueryMode` nunca inferido automaticamente;
- Citation Validation determinística e fail-closed;
- HOLDOUT nunca vira DEV;
- artifacts congelados identificados por SHA-256;
- web não integra o runtime de consulta;
- Ollama somente pelo Docker Compose;
- Gold Evidence é avaliação e nunca input do runtime RAG.

## 9. Limitações conhecidas

O Blind HOLDOUT obteve `25/36` passes automáticos, `34/36` em correção jurídica,
`36/36` em groundedness, `32/36` em completude e `32/36` all-pass. Retrieval
inicial cobriu `26/44` provisions e o assembly, `40/44`; o schema foi válido em
`34/36`. O corpus contém um ato, `CASE_APPLICATION` não aplica fatos concretos e
não há runtime web fetch.

## 10. Estado final

```text
MVP2_STATUS: CLOSED
MVP2_FINAL_DECISION: MVP2_ACCEPTED_WITH_KNOWN_LIMITATIONS
```

O runtime é `integrated-runtime-mvp2/1`, SHA-256
`5f0df6b41f0d35fcba0a514777a2370385620007ff3e6122473ca6793067514d`.

A camada de packaging, bootstrap e interface Rich foi finalizada depois desse
freeze. Ela não fazia parte da medição HOLDOUT e não modifica retrieval,
answerer, prompt, validação ou contrato de modos. O serviço `app` é um bootstrap
one-shot: seu encerramento com código zero é sucesso; PostgreSQL e Ollama
permanecem ativos para execuções posteriores da CLI.
