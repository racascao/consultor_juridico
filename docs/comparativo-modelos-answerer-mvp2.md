# Comparativo dos modelos locais para o answerer jurídico — MVP2

> **Status:** seleção concluída  
> **Fase:** `PHASE_2_GOLD_EVIDENCE_MODEL_CAPABILITY` — concluída  
> **Answerer selecionado:** `gemma4:12b` com `ollama_format=json`  
> **Freeze:** `gold-evidence-selected-answerer/1`  
> **Prompt:** `gold-evidence-answering/2`

## 1. Objetivo

Este documento registra a comparação dos modelos locais avaliados para o answerer jurídico do MVP2, os principais prós e contras observados, os riscos materiais encontrados e a justificativa técnica para a seleção do `gemma4:12b`.

A comparação preserva uma distinção central da avaliação:

- **qualidade material jurídica**: correção, grounding, completude e comportamento diante de fatos insuficientes;
- **conformidade operacional**: JSON válido, schema de saída, decisão esperada e estabilidade do contrato;
- **segurança metodológica**: ausência de aplicação factual prematura, inversão de polaridade e outros riscos congelados.

A seleção não foi feita por uma única métrica agregada. Em um sistema jurídico, uma resposta formalmente perfeita, mas juridicamente errada ou prematuramente conclusiva, é mais perigosa do que uma resposta materialmente correta que falha apenas no envelope de saída.

---

## 2. Modelos avaliados

Foram caracterizados os seguintes candidatos:

1. `qwen3:4b-instruct-2507-q4_K_M`
2. `qwen3.5:9b`
3. `phi4-mini:3.8b-q4_K_M`
4. `gemma3:4b`
5. `gemma4:12b`

O `gemma4:12b` passou ainda por uma rodada controlada de reconsideração com uma única variável adicional:

```text
ollama_format=json
```

O prompt, dataset, seeds e demais parâmetros de geração permaneceram congelados.

---

## 3. Comparação quantitativa

### 3.1 Rodada cross-model original

| Modelo | Automatic pass | Correção jurídica | Groundedness | Completude | Human all-pass | Strict | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Qwen3 4B | 25/32 | 29/32 | 29/32 | 25/32 | 25/32 | 22/32 | REJECT |
| Qwen3.5 9B | **27/32** | 29/32 | 29/32 | 26/32 | 26/32 | **25/32** | REJECT |
| Phi-4 Mini 3.8B | 21/32 | 26/32 | 28/32 | 18/32 | 17/32 | 16/32 | REJECT |
| Gemma3 4B | 1/32 | 23/32 | 28/32 | 19/32 | 18/32 | 1/32 | REJECT |
| Gemma4 12B — baseline | 12/32 | **32/32** | **32/32** | **29/32** | **29/32** | 12/32 | RECONSIDER |

### 3.2 Gemma4 após structured output

A rodada de reconsideração alterou somente:

```text
ollama_format=json
```

| Métrica | Gemma4 baseline | Gemma4 + `format=json` | Delta |
|---|---:|---:|---:|
| JSON válido | 13/32 | **32/32** | +19 |
| Schema válido | 12/32 | **31/32** | +19 |
| Payload válido | 12/32 | **31/32** | +19 |
| Decisão esperada | 12/32 | **30/32** | +18 |
| Automatic pass | 12/32 | **30/32** | +18 |
| Cobertura obrigatória de citações | 18/32 | **32/32** | +14 |
| Estabilidade | 5/12 | **12/12** | +7 |
| Correção jurídica | **32/32** | **32/32** | 0 |
| Groundedness | **32/32** | **32/32** | 0 |
| Completude | 29/32 | 29/32 | 0 |
| Human all-pass | 29/32 | 29/32 | 0 |
| Strict | 12/32 | **29/32** | +17 |
| GOLD-012 automático | 3/3 | 3/3 | 0 |
| GOLD-012 material | 3/3 | 3/3 | 0 |

O resultado demonstrou que structured output resolveu o principal bloqueio operacional sem regressão material observável.

---

## 4. Qwen3 4B

### Pontos positivos

- Bom desempenho automático para um modelo de aproximadamente 4B.
- `25/32` no evaluator automático.
- `25/32` em human all-pass.
- `22/32` strict.
- Estabilidade de decisão de `12/12`.
- Boa relação entre tamanho e capacidade.
- Comportamento consistente em casos de evidência insuficiente.
- Groundedness e correção jurídica relativamente altos (`29/32` em ambos).

### Pontos negativos

O problema principal foi material e não apenas formal.

O modelo reproduziu:

- `RISK-01 — PREMATURE_FACTUAL_APPLICATION`;
- `RISK-02 — EVIDENCE_COMPREHENSION / NEGATION_POLARITY_FAILURE`.

Nos casos de referência `GOLD-029` e `GOLD-030`, o modelo apresentou tendência reproduzível a aplicar a regra jurídica ao caso concreto antes de possuir fatos suficientes para concluir.

Esse comportamento é especialmente problemático para um consultor jurídico: uma conclusão prematura pode parecer plausível e bem formatada, mas estar juridicamente condicionada a fatos que ainda não foram fornecidos.

### Síntese

**Perfil:** pequeno, eficiente, estável e disciplinado, porém excessivamente conclusivo em situações que deveriam resultar em clarificação.

**Verdict:** `REJECT`.

---

## 5. Qwen3.5 9B

### Pontos positivos

Foi o melhor modelo da rodada original em métricas operacionais combinadas:

- `27/32` automatic pass;
- `26/32` human all-pass;
- `25/32` strict — melhor resultado strict da rodada cross-model original;
- `29/32` correção jurídica;
- `29/32` groundedness;
- `26/32` completude;
- nenhuma citação inválida ou fora da evidência;
- bom cumprimento do contrato de saída.

O modelo também não reproduziu o problema de polaridade observado em `GOLD-012` em outros candidatos.

### Pontos negativos

Apesar do ótimo desempenho agregado, reproduziu o risco mais importante para a segurança da aplicação:

- `RISK-01 — PREMATURE_FACTUAL_APPLICATION`.

Nos casos `GOLD-029` e `GOLD-030`, respondeu `ANSWER` em `3/3` seeds quando deveria solicitar fatos adicionais.

Portanto, o principal problema não era a interface de saída, mas o próprio comportamento decisório.

### Síntese

**Perfil:** o melhor candidato da rodada original em disciplina operacional, mas ainda propenso a decidir casos concretos sem informações suficientes.

**Verdict:** `REJECT`.

---

## 6. Phi-4 Mini 3.8B

### Pontos positivos

- Modelo pequeno.
- Groundedness relativamente forte: `28/32`.
- `21/32` automatic pass.
- Nenhuma aceitação insegura nos casos classificados como evidência insuficiente.
- Em algumas amostras mostrou maior disposição para reconhecer insuficiência factual.

### Pontos negativos

Foi o modelo com o problema semântico mais preocupante em `GOLD-012`.

Em uma das execuções, o modelo **inverteu a polaridade da regra jurídica**, afirmando com confiança o oposto do conteúdo da evidência.

Além disso, apresentou sinais de:

- `RISK-02 — EVIDENCE_COMPREHENSION / NEGATION_POLARITY_FAILURE`;
- `RISK-03 — MATERIAL_QUALIFIER_OR_EXCEPTION_OMISSION`;
- `RISK-04 — MULTI_PART_QUESTION_INCOMPLETENESS`;
- `RISK-05 — CLARIFICATION_CONTENT_INCOMPLETENESS`;
- `RISK-08 — COMPOSITE_CITATION_SAMPLING_VARIABILITY`.

A completude material ficou em apenas `18/32`, e o human all-pass em `17/32`.

### Síntese

**Perfil:** relativamente grounded, mas vulnerável a incompletude e a erro de compreensão jurídica de alta gravidade, incluindo inversão de polaridade.

**Verdict:** `REJECT`.

---

## 7. Gemma3 4B

### Pontos positivos

O resultado automático de `1/32` subestima fortemente sua capacidade material.

Na revisão humana, o modelo obteve:

- `23/32` correção jurídica;
- `28/32` groundedness;
- `19/32` completude;
- `18/32` human all-pass.

Também respondeu corretamente materialmente aos probes de `GOLD-012`.

### Pontos negativos

A conformidade operacional foi inadequada:

- `31/32` respostas foram produzidas dentro de Markdown code fences;
- apenas `1/32` passou integralmente pelo contrato automático.

Além disso, mesmo ignorando o problema de envelope, o modelo também reproduziu:

- `RISK-01 — PREMATURE_FACTUAL_APPLICATION`.

Portanto, remover fences não seria suficiente para torná-lo seguro para seleção.

### Síntese

**Perfil:** materialmente melhor do que a métrica automática sugere, mas com disciplina de saída muito fraca e ainda com risco jurídico decisório relevante.

**Verdict:** `REJECT`.

---

## 8. Gemma4 12B — baseline

### Pontos positivos

Foi o modelo materialmente mais forte de toda a comparação:

- `32/32` correção jurídica;
- `32/32` groundedness;
- `29/32` completude;
- `29/32` human all-pass.

Mais importante, não reproduziu os dois riscos centrais que eliminaram candidatos anteriores:

- `RISK-01`: não observado nos casos de referência;
- `RISK-02`: não observado no full nem nos probes de `GOLD-012`.

Nos casos `GOLD-029` e `GOLD-030`, o modelo solicitou os fatos necessários em vez de aplicar prematuramente a regra jurídica.

Também preservou corretamente:

- qualificadores e exceções;
- perguntas multipartes;
- regras de recurso;
- efeito suspensivo;
- revisão administrativa;
- citações materiais relevantes.

### Pontos negativos

O baseline tinha um grave problema operacional:

- JSON válido: `13/32`;
- automatic pass: `12/32`;
- strict: `12/32`;
- estabilidade formal: `5/12`.

A maioria das falhas estava relacionada ao envelope de saída, especialmente JSON envolto em Markdown fences ou pequenas violações do contrato.

### Síntese

**Perfil:** melhor capacidade jurídica, porém ainda inviável operacionalmente no contrato congelado original.

**Verdict baseline:** `RECONSIDER`.

---

## 9. Gemma4 12B com `format=json`

A reconsideração foi desenhada como experimento controlado de uma única variável.

### Variável independente

```text
ollama_format=json
```

Permaneceram congelados:

- modelo e digest;
- prompt `gold-evidence-answering/2`;
- dataset;
- evidence bundle;
- seeds;
- `temperature=0.7`;
- `top_p=0.8`;
- `top_k=20`;
- `repeat_penalty=1.0`;
- `num_predict=1024`;
- `num_ctx=8192`;
- `thinking_mode=disabled`.

### Resultado

O structured output transformou o comportamento operacional:

- JSON válido: `13/32 → 32/32`;
- schema válido: `12/32 → 31/32`;
- automatic pass: `12/32 → 30/32`;
- estabilidade: `5/12 → 12/12`;
- strict: `12/32 → 29/32`.

Ao mesmo tempo, as métricas materiais permaneceram exatamente estáveis:

- correção jurídica: `32/32 → 32/32`;
- groundedness: `32/32 → 32/32`;
- completude: `29/32 → 29/32`;
- human all-pass: `29/32 → 29/32`.

Não houve reaparecimento de:

- `RISK-01`;
- `RISK-02`.

### Limitações residuais

Mesmo após a aceitação, três limitações permanecem registradas:

1. `GOLD-027_OUTPUT_SCHEMA_FAILURE_CITATIONS_IDS`  
   Em um caso, o modelo retornou `citations_ids` em vez de `citations`.

2. `GOLD-031_CLARIFICATION_DECISION_FAILURE`  
   O modelo retornou `ABSTAIN` quando a decisão esperada era `CLARIFY`.

3. `RISK-05_CLARIFICATION_CONTENT_INCOMPLETENESS`  
   Em alguns casos, o modelo reconhece corretamente que faltam fatos, mas não formula todas as perguntas necessárias para completar a análise.

Essas limitações são conhecidas, permanecem fail-closed no runtime e não foram ocultadas pela seleção.

---

## 10. Comparação qualitativa final

| Dimensão | Melhor resultado |
|---|---|
| Correção jurídica | **Gemma4 12B** |
| Groundedness | **Gemma4 12B** |
| Completude | **Gemma4 12B** |
| Human all-pass | **Gemma4 12B** |
| Disciplina operacional na rodada original | **Qwen3.5 9B** |
| Disciplina operacional após structured output | **Gemma4 12B + `format=json`** |
| Comportamento com fatos insuficientes | **Gemma4 12B** |
| Resistência a inversão de polaridade | **Gemma4 12B / Qwen3.5 9B** |
| Estabilidade após configuração final | **Gemma4 12B + `format=json` — 12/12** |
| Strict final | **Gemma4 12B + `format=json` — 29/32** |

---

## 11. Por que o Qwen3.5 não foi escolhido?

Essa é a comparação mais importante.

Na rodada original:

```text
Qwen3.5 strict: 25/32
Gemma4 baseline strict: 12/32
```

Uma seleção puramente baseada no evaluator automático favoreceria o Qwen3.5.

Porém, a causa das falhas era diferente.

### Qwen3.5

O problema dominante era **semântico/jurídico**:

```text
fatos insuficientes
→ modelo conclui
→ aplicação factual prematura
```

### Gemma4 baseline

O problema dominante era **operacional/de interface**:

```text
resposta juridicamente correta
→ envelope JSON inadequado
→ evaluator rejeita
```

Essa distinção foi decisiva.

Um sistema jurídico não deve preferir uma resposta perfeitamente serializada que conclui sobre fatos inexistentes a uma resposta juridicamente correta cuja serialização pode ser restringida genericamente pelo runtime.

O experimento `format=json` confirmou exatamente essa hipótese: o problema de interface era corrigível estruturalmente sem alterar a capacidade jurídica.

---

## 12. Motivo da seleção do Gemma4 12B

O `gemma4:12b` foi selecionado porque foi o único candidato que combinou, sob a configuração final:

- `32/32` em correção jurídica;
- `32/32` em groundedness;
- `29/32` em completude;
- `29/32` em human all-pass;
- `30/32` em automatic pass;
- `29/32` strict;
- `12/12` de estabilidade;
- `3/3` em GOLD-012 automático;
- `3/3` em GOLD-012 material;
- ausência observada de `RISK-01`;
- ausência observada de `RISK-02`;
- ausência de regressão material após structured output;
- `32/32` de JSON válido;
- `32/32` de cobertura obrigatória de citações.

O ganho operacional veio de uma mudança genérica do runtime:

```text
format=json
```

e não de:

- hardcode por pergunta;
- ajuste por `case_id`;
- prompt específico para falhas conhecidas;
- pós-processamento reparador;
- stripping de Markdown;
- retry oportunista;
- tuning baseado no benchmark.

Isso preserva a generalidade da solução.

---

## 13. Configuração selecionada e congelada

A identidade do answerer selecionado não é apenas o nome do modelo.

Ela é:

```text
model:
  gemma4:12b

digest:
  4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c

prompt:
  gold-evidence-answering/2

thinking_mode:
  disabled

ollama_format:
  json

temperature:
  0.7

top_p:
  0.8

top_k:
  20

repeat_penalty:
  1.0

num_predict:
  1024

num_ctx:
  8192

stream:
  false

timeout:
  180
```

Freeze canônico:

```text
gold-evidence-selected-answerer/1
```

Artifact:

```text
evaluation/model_selection/gold_evidence_selected_answerer_freeze_v1.json
```

Qualquer alteração em modelo, digest, prompt, configuração de geração, thinking mode, structured output ou contrato de saída invalida a identidade congelada e exige nova avaliação antes do HOLDOUT.

---

## 14. Conclusão

A seleção do `gemma4:12b` não ocorreu porque ele simplesmente teve o maior score automático.

Na rodada original, ele não teve.

Ele foi escolhido porque apresentou a melhor combinação de:

1. **correção jurídica material**;
2. **grounding na evidência fornecida**;
3. **prudência diante de fatos insuficientes**;
4. **resistência a erros de polaridade**;
5. **completude**;
6. **estabilidade**;
7. **contrato operacional robusto após uma intervenção genérica e controlada**.

A decisão final foi:

```text
GEMMA4_BASELINE_VERDICT:
RECONSIDER

GEMMA4_FORMAT_JSON_VERDICT:
ACCEPT

FINAL_LEGAL_ANSWERER:
ACCEPTED
```

O principal aprendizado arquitetural foi que o defeito dominante do Gemma4 era de **interface**, enquanto os melhores concorrentes ainda apresentavam defeitos **semânticos/jurídicos** mais difíceis de mitigar de maneira geral.

Por isso, para o MVP2, a configuração congelada `gemma4:12b + format=json` oferece o melhor equilíbrio observado entre capacidade jurídica, groundedness, segurança decisória, estabilidade e integração operacional.

---

## 15. Próximo passo

Com a Fase 2 concluída e o answerer congelado, o desenvolvimento segue para:

```text
RAG_INTEGRATION_END_TO_END
```

O próximo objetivo é integrar:

```text
consulta
→ retrieval
→ evidence assembly
→ answerer congelado
→ Citation Validation
→ resposta rastreável
```

O HOLDOUT permanece fechado até que o runtime integrado seja implementado, avaliado em DEV e congelado.
