# Runbook cross-model Gold Evidence v1

Este runbook executa manualmente os quatro candidatos congelados no manifest
`evaluation/runs/gold_evidence_cross_model_manifest_v1.json`. Ele usa somente o
Ollama do Docker Compose, não baixa modelos, não altera inputs e não acessa o
HOLDOUT.

Antes da primeira execução, conferir:

```bash
sha256sum \
  evaluation/runs/gold_evidence_cross_model_manifest_v1.json \
  evaluation/runs/gold_evidence_input_prompt_v2.jsonl \
  evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
  evaluation/datasets/lei_9784_gold_evidence_dev_v1.json

docker compose exec ollama ollama list
```

Hashes esperados, na mesma ordem:

```text
f9f57938f4ffd6b29e4bd1eab2922aada847e5d344a4ad9c6451e21d97910639
dd91a0d68f5e7e78ec9739b8fcde333308362a246d934c5a38da6810af3bdd98
88dcfeef9eccadcff745f6e2ddaa1caa8c274c35d03b720d5d44462012686ea8
56231c6a051a7093f3e1c2fb4cfc5af176b41021a064f3a601c7caa40c4fe319
68a319031b7ca3f9da912761ab5328ef6bf37251f8750b3e24207c7258622f65
```

As inferências continuam lendo seus respectivos inputs. Todas as validações
automáticas, inclusive stability e `GOLD-012`, usam o **full bundle v2** como
fonte materializada de Gold Evidence. O modo `frozen-bundle` não cria engine,
sessão ou conexão PostgreSQL e valida o SHA antes de processar respostas. Seu
namespace de citações é parcial e qualquer chave estruturalmente plausível não
conhecida falha fechadamente com `INCOMPLETE_FROZEN_CITATION_NAMESPACE`.

## Ordem congelada

Executar o procedimento completo de um candidato antes de configurar o
seguinte. Não interromper depois do primeiro resultado aparentemente favorável.

### A. Qwen3.5 9B

```bash
export GOLD_MODEL='qwen3.5:9b'
export GOLD_SLUG='qwen3_5_9b'
export GOLD_THINKING_MODE='disabled'
```

### B. Phi-4-mini

```bash
export GOLD_MODEL='phi4-mini:3.8b-q4_K_M'
export GOLD_SLUG='phi4_mini_3_8b'
export GOLD_THINKING_MODE='auto'
```

### C. Gemma3 4B

```bash
export GOLD_MODEL='gemma3:4b'
export GOLD_SLUG='gemma3_4b'
export GOLD_THINKING_MODE='auto'
```

### D. Gemma4 12B

```bash
export GOLD_MODEL='gemma4:12b'
export GOLD_SLUG='gemma4_12b'
export GOLD_THINKING_MODE='disabled'
```

`auto` preserva a ausência do campo `think` para os modelos que não declaram a
capacidade de thinking. `disabled` envia o campo nativo `think=false`, sem
alterar o prompt, para Qwen3.5 e Gemma4.

## Procedimento completo por candidato

Após exportar as três variáveis do candidato atual, executar todo este bloco.
Os caminhos contêm o slug definido acima e os comandos recusam sobrescrita.

### 1. Full Gold — 32 casos, seed 42

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_input_prompt_v2.jsonl \
  --model "$GOLD_MODEL" \
  --base-url http://localhost:11435 \
  --seed 42 \
  --thinking-mode "$GOLD_THINKING_MODE" \
  --output "evaluation/runs/${GOLD_SLUG}_prompt_v2_full_responses.jsonl" \
  --metadata "evaluation/runs/${GOLD_SLUG}_prompt_v2_full_metadata.json"

.venv/bin/consultor-juridico eval gold validate-responses \
  --dataset evaluation/datasets/lei_9784_gold_evidence_dev_v1.json \
  --version-hash 298028477a55a61cdd1df94bda3aec784e6fe94d17c485ae6a2f6c77fe2b7a74 \
  --responses "evaluation/runs/${GOLD_SLUG}_prompt_v2_full_responses.jsonl" \
  --prompt-version 2 \
  --gold-evidence-source frozen-bundle \
  --gold-bundle evaluation/runs/gold_evidence_input_prompt_v2.jsonl \
  --gold-bundle-sha256 dd91a0d68f5e7e78ec9739b8fcde333308362a246d934c5a38da6810af3bdd98 \
  --output "evaluation/results/${GOLD_SLUG}_prompt_v2_full_automatic_evaluation.json"

sha256sum \
  "evaluation/runs/${GOLD_SLUG}_prompt_v2_full_responses.jsonl" \
  "evaluation/runs/${GOLD_SLUG}_prompt_v2_full_metadata.json" \
  "evaluation/results/${GOLD_SLUG}_prompt_v2_full_automatic_evaluation.json"
```

A validação cria também o template
`evaluation/results/${GOLD_SLUG}_prompt_v2_full_automatic_evaluation_human_review.json`.
Ele deve ser preenchido manualmente, sem LLM judge e com a mesma rubrica do
baseline.

### 2. Estabilidade — 12 casos, seeds 42/43/44

```bash
for GOLD_SEED in 42 43 44; do
  .venv/bin/consultor-juridico eval gold run-ollama \
    --input evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
    --model "$GOLD_MODEL" \
    --base-url http://localhost:11435 \
    --seed "$GOLD_SEED" \
    --thinking-mode "$GOLD_THINKING_MODE" \
    --output "evaluation/runs/${GOLD_SLUG}_prompt_v2_stability_seed${GOLD_SEED}_responses.jsonl" \
    --metadata "evaluation/runs/${GOLD_SLUG}_prompt_v2_stability_seed${GOLD_SEED}_metadata.json"

  .venv/bin/consultor-juridico eval gold validate-responses \
    --dataset evaluation/datasets/lei_9784_gold_evidence_dev_v1.json \
    --version-hash 298028477a55a61cdd1df94bda3aec784e6fe94d17c485ae6a2f6c77fe2b7a74 \
    --responses "evaluation/runs/${GOLD_SLUG}_prompt_v2_stability_seed${GOLD_SEED}_responses.jsonl" \
    --case-subset evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
    --prompt-version 2 \
    --gold-evidence-source frozen-bundle \
    --gold-bundle evaluation/runs/gold_evidence_input_prompt_v2.jsonl \
    --gold-bundle-sha256 dd91a0d68f5e7e78ec9739b8fcde333308362a246d934c5a38da6810af3bdd98 \
    --output "evaluation/results/${GOLD_SLUG}_prompt_v2_stability_seed${GOLD_SEED}_automatic_evaluation.json"
done

.venv/bin/consultor-juridico eval gold stability-summarize \
  --dataset evaluation/datasets/lei_9784_gold_evidence_dev_v1.json \
  --seed42-evaluation "evaluation/results/${GOLD_SLUG}_prompt_v2_stability_seed42_automatic_evaluation.json" \
  --seed43-evaluation "evaluation/results/${GOLD_SLUG}_prompt_v2_stability_seed43_automatic_evaluation.json" \
  --seed44-evaluation "evaluation/results/${GOLD_SLUG}_prompt_v2_stability_seed44_automatic_evaluation.json" \
  --output "evaluation/results/${GOLD_SLUG}_prompt_v2_stability_v1.json"
```

### 3. Probe RISK-02 / GOLD-012 — fora do denominador histórico

```bash
for GOLD_SEED in 42 43 44; do
  .venv/bin/consultor-juridico eval gold run-ollama \
    --input evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
    --model "$GOLD_MODEL" \
    --base-url http://localhost:11435 \
    --seed "$GOLD_SEED" \
    --thinking-mode "$GOLD_THINKING_MODE" \
    --output "evaluation/runs/${GOLD_SLUG}_prompt_v2_gold012_seed${GOLD_SEED}_responses.jsonl" \
    --metadata "evaluation/runs/${GOLD_SLUG}_prompt_v2_gold012_seed${GOLD_SEED}_metadata.json"

  .venv/bin/consultor-juridico eval gold validate-responses \
    --dataset evaluation/datasets/lei_9784_gold_evidence_dev_v1.json \
    --version-hash 298028477a55a61cdd1df94bda3aec784e6fe94d17c485ae6a2f6c77fe2b7a74 \
    --responses "evaluation/runs/${GOLD_SLUG}_prompt_v2_gold012_seed${GOLD_SEED}_responses.jsonl" \
    --case-id GOLD-012 \
    --prompt-version 2 \
    --gold-evidence-source frozen-bundle \
    --gold-bundle evaluation/runs/gold_evidence_input_prompt_v2.jsonl \
    --gold-bundle-sha256 dd91a0d68f5e7e78ec9739b8fcde333308362a246d934c5a38da6810af3bdd98 \
    --output "evaluation/results/${GOLD_SLUG}_prompt_v2_gold012_seed${GOLD_SEED}_automatic_evaluation.json"
done
```

Classificar as três decisões somente como uma das alternativas pré-registradas:

```text
ANSWER / ANSWER / ANSWER  -> CORRECT_ANSWER_3_OF_3
ABSTAIN / ABSTAIN / ABSTAIN -> REPRODUCIBLE_FALSE_ABSTENTION_3_OF_3
qualquer outra combinação -> DECISION_SAMPLING_SENSITIVITY_OBSERVED
```

### 4. Revisão humana e consolidação

Depois de preencher manualmente o template full, executar:

```bash
.venv/bin/consultor-juridico eval gold summarize \
  --automatic-evaluation "evaluation/results/${GOLD_SLUG}_prompt_v2_full_automatic_evaluation.json" \
  --human-review "evaluation/results/${GOLD_SLUG}_prompt_v2_full_automatic_evaluation_human_review.json" \
  --output "evaluation/results/${GOLD_SLUG}_prompt_v2_full_final_review.json"
```

O comando recusa campos pendentes e divergências em dados preservados. Somente
depois de automatic, estabilidade, probe GOLD-012, revisão humana e scorecard de
risco o candidato pode receber `ACCEPT`, `REJECT` ou `RECONSIDER`.

### 5. Liberar o candidato antes do próximo

```bash
docker compose exec ollama ollama stop "$GOLD_MODEL"
```

Se qualquer run ultrapassar 180 segundos, falhar tecnicamente ou revelar
thinking separado apesar de `--thinking-mode disabled`, interromper aquele
candidato e preservar os artefatos parciais. Não aumentar timeout, não reparar
a resposta e não alterar o manifest.

## Checkpoint controlado: Gemma3 4B

Em 10 de setembro de 2026, `gemma3:4b` foi confirmado no Ollama do Docker
Compose com o digest congelado
`a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a`.
Os comandos abaixo são deliberadamente separados e devem ser executados
manualmente pelo usuário, a partir da raiz do repositório. Eles não foram
executados durante a preparação.

### Full — seed 42

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_input_prompt_v2.jsonl \
  --model gemma3:4b \
  --base-url http://localhost:11435 \
  --seed 42 \
  --thinking-mode auto \
  --output evaluation/runs/gemma3_4b_prompt_v2_full_responses.jsonl \
  --metadata evaluation/runs/gemma3_4b_prompt_v2_full_metadata.json
```

### Stability — seed 42

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --model gemma3:4b \
  --base-url http://localhost:11435 \
  --seed 42 \
  --thinking-mode auto \
  --output evaluation/runs/gemma3_4b_prompt_v2_stability_seed42_responses.jsonl \
  --metadata evaluation/runs/gemma3_4b_prompt_v2_stability_seed42_metadata.json
```

### Stability — seed 43

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --model gemma3:4b \
  --base-url http://localhost:11435 \
  --seed 43 \
  --thinking-mode auto \
  --output evaluation/runs/gemma3_4b_prompt_v2_stability_seed43_responses.jsonl \
  --metadata evaluation/runs/gemma3_4b_prompt_v2_stability_seed43_metadata.json
```

### Stability — seed 44

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --model gemma3:4b \
  --base-url http://localhost:11435 \
  --seed 44 \
  --thinking-mode auto \
  --output evaluation/runs/gemma3_4b_prompt_v2_stability_seed44_responses.jsonl \
  --metadata evaluation/runs/gemma3_4b_prompt_v2_stability_seed44_metadata.json
```

### GOLD-012 — seed 42

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
  --model gemma3:4b \
  --base-url http://localhost:11435 \
  --seed 42 \
  --thinking-mode auto \
  --output evaluation/runs/gemma3_4b_prompt_v2_gold012_seed42_responses.jsonl \
  --metadata evaluation/runs/gemma3_4b_prompt_v2_gold012_seed42_metadata.json
```

### GOLD-012 — seed 43

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
  --model gemma3:4b \
  --base-url http://localhost:11435 \
  --seed 43 \
  --thinking-mode auto \
  --output evaluation/runs/gemma3_4b_prompt_v2_gold012_seed43_responses.jsonl \
  --metadata evaluation/runs/gemma3_4b_prompt_v2_gold012_seed43_metadata.json
```

### GOLD-012 — seed 44

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
  --model gemma3:4b \
  --base-url http://localhost:11435 \
  --seed 44 \
  --thinking-mode auto \
  --output evaluation/runs/gemma3_4b_prompt_v2_gold012_seed44_responses.jsonl \
  --metadata evaluation/runs/gemma3_4b_prompt_v2_gold012_seed44_metadata.json
```

## Checkpoint controlado: Gemma4 12B

Em 10 de setembro de 2026, `gemma4:12b` foi confirmado no Ollama do Docker
Compose com o digest congelado
`4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`.
O gate está `READY_FOR_MANUAL_RUNS`. Os comandos abaixo são deliberadamente
separados, devem ser executados manualmente pelo usuário a partir da raiz do
repositório e recusam sobrescrita. Nenhum deles foi executado durante a
preparação.

### Gemma4 full — seed 42

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_input_prompt_v2.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 42 \
  --thinking-mode disabled \
  --output evaluation/runs/gemma4_12b_prompt_v2_full_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_full_metadata.json
```

### Gemma4 stability — seed 42

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 42 \
  --thinking-mode disabled \
  --output evaluation/runs/gemma4_12b_prompt_v2_stability_seed42_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_stability_seed42_metadata.json
```

### Gemma4 stability — seed 43

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 43 \
  --thinking-mode disabled \
  --output evaluation/runs/gemma4_12b_prompt_v2_stability_seed43_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_stability_seed43_metadata.json
```

### Gemma4 stability — seed 44

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 44 \
  --thinking-mode disabled \
  --output evaluation/runs/gemma4_12b_prompt_v2_stability_seed44_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_stability_seed44_metadata.json
```

### Gemma4 GOLD-012 — seed 42

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 42 \
  --thinking-mode disabled \
  --output evaluation/runs/gemma4_12b_prompt_v2_gold012_seed42_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_gold012_seed42_metadata.json
```

### Gemma4 GOLD-012 — seed 43

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 43 \
  --thinking-mode disabled \
  --output evaluation/runs/gemma4_12b_prompt_v2_gold012_seed43_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_gold012_seed43_metadata.json
```

### Gemma4 GOLD-012 — seed 44

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
  --model gemma4:12b \
  --base-url http://localhost:11435 \
  --seed 44 \
  --thinking-mode disabled \
  --output evaluation/runs/gemma4_12b_prompt_v2_gold012_seed44_responses.jsonl \
  --metadata evaluation/runs/gemma4_12b_prompt_v2_gold012_seed44_metadata.json
```
