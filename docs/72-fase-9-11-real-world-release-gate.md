# Fase 9.11 — Reavaliação End-to-End e Real-World Release Gate

## Configuração congelada

Generator e Semantic Judge: `granite4.1:3b`. Embedding:
`nomic-embed-text:latest`. Retrieval, selection, sufficiency, attribution,
Polarity Guard, Semantic Validator, prompts, thresholds e datasets não foram
alterados. A Fase 9.10 estava commitada (`9a97f24`) e o working tree estava
limpo antes da execução.

## Resultados

O retrieval híbrido manteve Hit@10 `0,905`, MRR `0,627` e Recall@10 `0,881`.
O dataset de qualidade manteve abstenção correta `100%` e `unsafe_answers=0`.
O dataset `semantic_support_v1` registrou accuracy `0,800`, SUPPORTED precision
`1,000`, recall `1,000`, contratos inválidos `0` e unsafe acceptance `0`.

No `real_world_short_v1`, foram obtidas 6/10 respostas corretas, 4 false
abstentions, 1/1 abstenção correta e zero respostas inseguras. As falhas foram:

| Caso | Resultado | Estágio |
|---|---|---|
| pena de morte | false abstention | EVIDENCE_SELECTION_MISS |
| prisão perpétua | false abstention | EVIDENCE_SELECTION_MISS |
| liberdade religiosa | correto | — |
| racismo | correto | — |
| extradição | correto | — |
| direito à vida | correto | — |
| liberdade de expressão | correto | — |
| idade para ser presidente | false abstention | RETRIEVAL_MISS |
| voto obrigatório | false abstention | EVIDENCE_SELECTION_MISS |
| estado de sítio | correto | — |
| aborto | abstenção correta | — |

O artefato completo está em
`evaluation/results/real_world_short_e2e_9_11.json`. A regressão offline dos
casos congelados está em `evaluation/results/polarity_regression_9_11.json`;
inversões explícitas foram classificadas como `CONTRADICTED` e o guard não
permitiu promoção de claim.

## Persistência, segurança e CLI

Não existem citations inválidas (`is_valid=false=0`) e o SHA da captura continua
`25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d`. As
avaliações criaram apenas EvidenceSets/Claims/Citations diagnósticos auditáveis;
nenhuma ingestão foi executada e `raw_bytes` permaneceu intacto. O smoke test
`consultor-juridico --help` passou sem traceback.

## Gate e decisão

`MVP1_QUALITY_APPROVED` e `POLARITY_GUARD_GATE=APPROVED` permanecem válidos.
`REAL_WORLD_RELEASE_GATE=BLOCKED`, pois o requisito mínimo de 9/10 não foi
atingido. Não houve tuning ou correção nesta fase. A próxima intervenção deve
ser decidida separadamente, focando os misses de retrieval/selection.
