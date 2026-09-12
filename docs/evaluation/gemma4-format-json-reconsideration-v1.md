# Gemma4 format JSON reconsideration v1

## Escopo

`GEMMA4_FORMAT_JSON_RECONSIDERATION_V1` é um experimento pós-cross-model
separado. A hipótese é que o structured output do Ollama, ativado por
`format="json"`, corrige falhas do envelope de saída sem regressão jurídica
material.

O controle é o baseline congelado do `gemma4:12b`, cujo veredito permanece
`RECONSIDER`. A única variável independente é `OLLAMA_FORMAT_JSON`. Modelo,
digest, quantização, prompt `gold-evidence-answering/2`, bundles, evidências,
seeds, thinking, timeout e configuração de geração permanecem inalterados.
Nenhum threshold de promoção foi definido nesta preparação.

```text
EXPERIMENT: GEMMA4_FORMAT_JSON_RECONSIDERATION_V1
HYPOTHESIS: structured output corrige falha de envelope sem regressão jurídica
INDEPENDENT_VARIABLE: ollama format=json
CONTROL: Gemma4 baseline congelado
OTHER_CONFIG_CHANGED: NO
INFERENCE_EXECUTED: NO
PREPARATION_STATUS: COMPLETED_READY_FOR_MANUAL_RUNS
HOLDOUT_READ: NO
```

Configuração congelada:

```text
model=gemma4:12b
temperature=0.7
top_p=0.8
top_k=20
repeat_penalty=1.0
num_predict=1024
num_ctx=8192
stream=false
timeout=180s
thinking_mode=disabled
format=json
```

O campo `format` é opt-in e genérico no runner. Sem `--ollama-format`, o request
permanece igual ao comportamento histórico. Não há stripping de Markdown,
reparo de JSON, parser tolerante ou retry.

## Execução manual

Executar a partir da raiz do repositório. Os comandos recusam sobrescrita e não
substituem nenhum artifact do baseline.

### 1. Full — 32 casos, seed 42

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_input_prompt_v2.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 42 \
  --thinking-mode disabled \
  --ollama-format json \
  --output evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_full_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_full_metadata.json
```

### 2. Stability — seed 42

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 42 \
  --thinking-mode disabled \
  --ollama-format json \
  --output evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_stability_seed42_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_stability_seed42_metadata.json
```

### 3. Stability — seed 43

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 43 \
  --thinking-mode disabled \
  --ollama-format json \
  --output evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_stability_seed43_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_stability_seed43_metadata.json
```

### 4. Stability — seed 44

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 44 \
  --thinking-mode disabled \
  --ollama-format json \
  --output evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_stability_seed44_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_stability_seed44_metadata.json
```

### 5. GOLD-012 — seed 42

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 42 \
  --thinking-mode disabled \
  --ollama-format json \
  --output evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_gold012_seed42_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_gold012_seed42_metadata.json
```

### 6. GOLD-012 — seed 43

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 43 \
  --thinking-mode disabled \
  --ollama-format json \
  --output evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_gold012_seed43_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_gold012_seed43_metadata.json
```

### 7. GOLD-012 — seed 44

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 44 \
  --thinking-mode disabled \
  --ollama-format json \
  --output evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_gold012_seed44_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_format_json_reconsideration_v1_gold012_seed44_metadata.json
```

## Análise posterior

Somente após os sete runs serão comparados `AUTOMATIC_PASS`, `JSON_VALID`,
`OUTPUT_SCHEMA_VALID`, `DECISION_PAYLOAD_VALID`, `EXPECTED_DECISION_MATCH`,
`REQUIRED_CITATION_COVERED`, os três critérios humanos, `HUMAN_ALL_PASS`, a
interseção estrita, estabilidade e `RISK-01..RISK-08`. A análise deve preservar
separadamente os resultados automáticos/formais e humanos/materiais.

O controle opcional futuro `GEMMA3_FORMAT_JSON_GENERALITY_CONTROL_V1` não foi
executado e não reabre o veredito do Gemma3.

## Avaliação automática offline

Os sete runs foram executados manualmente e seus hashes e contagens passaram em
`7/7`. O evaluator canônico, com `FrozenGoldBundleRepository`, produziu:

| Métrica | Baseline | `format=json` | Delta |
|---|---:|---:|---:|
| JSON válido | 13/32 | 32/32 | +19 |
| Schema válido | 12/32 | 31/32 | +19 |
| Payload decisório válido | 12/32 | 31/32 | +19 |
| Decisão esperada | 12/32 | 30/32 | +18 |
| Passe automático | 12/32 | 30/32 | +18 |
| Citações obrigatórias cobertas | 18/32 | 32/32 | +14 |
| Decisão estável | 5/12 | 12/12 | +7 |
| `GOLD-012` automático | 3/3 | 3/3 | 0 |

`GOLD-027` falhou porque o raw usou `citations_ids` em vez de `citations`; o
evaluator preservou a falha sem renomear ou reparar o campo. `GOLD-031` retornou
`ABSTAIN` quando a decisão esperada era `CLARIFY`. Não houve falsa abstenção nos
casos respondíveis, resposta insegura em evidência insuficiente, citação
inválida ou citação fora da evidência; houve duas clarificações perdidas.

Nas três seeds, `GOLD-029` e `GOLD-030` permaneceram `CLARIFY`; `GOLD-018` e
`GOLD-020` conservaram decisões e conjuntos de citações idênticos; e
`GOLD-012` passou automaticamente em `3/3`. Esses são sinais formais ou
preliminares, não classificação material definitiva dos riscos.

```text
RAW_RUNS: COMPLETE
OFFLINE_AUTOMATIC_EVALUATION: COMPLETE
FORMAT_JSON_IMPROVED_JSON_VALIDITY: YES
FORMAT_JSON_IMPROVED_SCHEMA_VALIDITY: YES
FORMAT_JSON_IMPROVED_AUTOMATIC_PASS: YES
HUMAN_REVIEW: COMPLETE_29_OF_32_ALL_PASS
STRICT_AUTOMATIC_PLUS_HUMAN: 29/32
FINAL_COMPARISON: COMPLETE
RISK_SCORECARD: COMPLETE
CANDIDATE_VERDICT: ACCEPT
FINAL_LEGAL_ANSWERER: ACCEPTED
HOLDOUT_READ: NO
```

Artifacts principais:

- full automático:
  `evaluation/results/gemma4_12b_prompt_v2_format_json_reconsideration_v1_full_automatic_evaluation.json`;
- estabilidade:
  `evaluation/results/gemma4_12b_prompt_v2_format_json_reconsideration_v1_stability_v1.json`;
- summary `GOLD-012`:
  `evaluation/results/gemma4_12b_prompt_v2_format_json_reconsideration_v1_gold012_summary.json`;
- comparação automática:
  `evaluation/results/gemma4_12b_prompt_v2_format_json_reconsideration_v1_automatic_comparison.json`.

## Conclusão material e veredito

A revisão humana registrou `32/32` em correção jurídica, `32/32` em
groundedness, `29/32` em completude e `29/32` all-pass. As falhas de completude
foram `GOLD-027`, `GOLD-028` e `GOLD-031`. A interseção estrita por `case_id`
ficou em `29/32`, um ganho de 17 casos sobre o baseline. `GOLD-012` passou
materialmente em `3/3`.

`format=json` melhorou validade, schema, passe automático e estabilidade sem
regressão material agregada e sem reintroduzir `RISK-01` ou `RISK-02`.
`RISK-05` permanece observado; `GOLD-027` conserva sua falha de schema e
`GOLD-031` conserva a decisão `ABSTAIN` inadequada. Pela mesma metodologia dos
candidatos anteriores, a configuração genérica foi aceita:

```text
GEMMA4_BASELINE_VERDICT: RECONSIDER
GEMMA4_FORMAT_JSON_VERDICT: ACCEPT
FINAL_LEGAL_ANSWERER: ACCEPTED
MATERIAL_REGRESSION: NO
NEXT_GATE: FREEZE_SELECTED_MODEL_CONFIGURATION_AND_RUNTIME_BEFORE_RAG_INTEGRATION_OR_HOLDOUT
```

Artifacts finais:

- revisão final:
  `evaluation/results/gemma4_12b_prompt_v2_format_json_reconsideration_v1_full_final_review.json`;
- revisão material `GOLD-012`:
  `evaluation/results/gemma4_12b_prompt_v2_format_json_reconsideration_v1_gold012_material_review.json`;
- scorecard:
  `evaluation/results/gemma4_12b_prompt_v2_format_json_reconsideration_v1_risk_scorecard.json`;
- comparação final:
  `evaluation/results/gemma4_12b_prompt_v2_format_json_reconsideration_v1_final_comparison.json`.

## Freeze posterior à seleção

O resultado aceito foi congelado como `gold-evidence-selected-answerer/1` em
`evaluation/model_selection/gold_evidence_selected_answerer_freeze_v1.json`.
O freeze inclui modelo e digest, prompt v2 e hash, configuração integral de
geração, thinking desabilitado, `ollama_format=json`, contrato fail-closed,
runtime Compose-only e hashes das evidências de seleção. Ele não altera os
artifacts deste experimento nem o manifest cross-model.

Qualquer drift desses componentes invalida a identidade e exige reavaliação
antes do HOLDOUT. A integração RAG não foi iniciada nesta etapa.
