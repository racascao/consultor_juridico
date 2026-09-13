# Integrated DEV do MVP2

## Escopo e configuração

A primeira medição integrada executou os 32 casos conhecidos de
`lei_9784_gold_evidence_dev_v1` pelo pipeline RAG real. O Gold Evidence do
dataset foi usado exclusivamente como referência offline; a entrada do answerer
foi formada pelo PostgreSQL FTS real e pelo assembly estrutural.

```text
dataset_sha256=68a319031b7ca3f9da912761ab5328ef6bf37251f8750b3e24207c7258622f65
act_version=bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6
source_sha256=b4abab2e47732f76a16a99e8b00311dcb420b378f89e99c096b609ae84529261
retrieval=POSTGRESQL_FTS_RELAXED_OR_WEIGHTED_COVERAGE
expansion=DIRECT_CHILDREN_MAX_8_GLOBAL_MAX_24
model=gemma4:12b
digest=4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c
freeze=gold-evidence-selected-answerer/1
prompt=gold-evidence-answering/2
format=json
runtime=CUDA
```

Não houve retry, ajuste de timeout, tuning ou alteração do retrieval após a
observação dos resultados. O HOLDOUT permaneceu fechado e não foi localizado,
listado ou lido.

## Artefatos congelados

| Artefato | SHA-256 |
|---|---|
| `evaluation/results/integrated_dev_mvp2_v1/integrated_dev_raw_v1.json` | `4e6365c95dcf437f3be75594abaa87353718ec41d1f067714f13ed4cae63f974` |
| `evaluation/results/integrated_dev_mvp2_v1/integrated_dev_automatic_v1.json` | `230135d8d793420a647059a8c06ac509940fcf29b46193c75aee1357c0811b5e` |
| `evaluation/results/integrated_dev_mvp2_v1/integrated_dev_retrieval_diagnostic_v1.json` | `d807b3ad92c1475f253bf6e691942e2fc358b6271ca1c5b05518eabfc588cf07` |
| `evaluation/results/integrated_dev_mvp2_v1/integrated_dev_human_review_v1.json` | `1d62ac889bafd09481063617c329ec7f93a0a5d6820f88bce52b0729ac68bc91` |

## Resultado automático

| Métrica | Resultado |
|---|---:|
| JSON válido | 32/32 |
| Output schema válido | 32/32 |
| Payload de decisão válido | 32/32 |
| Decisão esperada | 25/32 |
| Automatic pass | 24/32 |
| Required citation coberta | 30/32 |
| False abstention | 1 |
| Unsafe answer em evidência insuficiente | 0 |
| Missed clarification | 6 |
| Citações inválidas | 0 |
| Citações fora da evidência | 0 |
| Recall de evidência obrigatória no retrieval | 27/34 = 0,794118 |
| Recall após evidence assembly | 32/34 = 0,941176 |
| Cobertura integral por caso | 30/32 |

A latência média foi 9,896 segundos por caso, a mediana 8,167 segundos, o
máximo 18,540 segundos e o total de geração aproximadamente 316,675 segundos.

## Diagnóstico por camada

Dois casos foram classificados como `RETRIEVAL_MISS`:

- `GOLD-003`: `ARTICLE:11/CAPUT` não chegou ao top-10; o answerer fez
  `ABSTAIN`, corretamente diante do conjunto efetivamente recebido.
- `GOLD-016`: `ARTICLE:48/CAPUT` não chegou ao top-10; o answerer respondeu
  apenas a parte sustentada por `ARTICLE:49/CAPUT`.

Não houve `EVIDENCE_ASSEMBLY_MISS`: a expansão estrutural aumentou a cobertura
de evidências obrigatórias de 27/34 para 32/34. Os seis casos `AMBIGUOUS`
(`GOLD-027..032`) foram `ANSWERER_DECISION_FAILURE`: todos retornaram `ANSWER`
condicional ou geral, em vez de `CLARIFY`. Isso reproduz de forma geral o
`RISK-05_CLARIFICATION_CONTENT_INCOMPLETENESS` observado no smoke manual.

```text
RETRIEVAL_MISS=2
EVIDENCE_ASSEMBLY_MISS=0
ANSWERER_DECISION_FAILURE=6
ANSWERER_OUTPUT_CONTRACT_FAILURE=0
CITATION_FAILURE=0
MATERIAL_REVIEW_REQUIRED=24
```

## Riscos e revisão material

O resultado automático não substitui julgamento jurídico. O template usa
`LEGAL_CORRECTNESS`, `GROUNDEDNESS` e `COMPLETENESS` para revisão humana dos 32
casos. O `RISK-05` foi observado em 6/6 casos ambíguos. A revisão preenchida
confirmou `30/32` em correção jurídica, `32/32` em groundedness, `24/32` em
completude e `24/32` all pass. Sua análise causal está em
[`integrated-dev-general-failure-analysis-v1.md`](integrated-dev-general-failure-analysis-v1.md).

## Próximo gate

O Integrated DEV está em `COMPLETE_FIRST_MEASUREMENT`, sem tuning. O próximo
passo é reconsiderar uma solução geral: o experimento lexical mínimo regrediu o
DEV, e um gate factual determinístico não é confiável sem representação
estruturada dos fatos. O runtime integrado ainda não foi congelado e o HOLDOUT
continua fechado.
