# Fase 90 — Controlled Relevance Model Benchmark

## Resultado

O benchmark foi executado para o primary e não foi concluído para o control por
limitação operacional de download. O resultado global é `INCONCLUSIVE` para a
comparação entre modelos, mas o primary isoladamente **falhou** o gate de
segurança.

Nenhum classificador foi integrado ao produto. Retrieval, VCSA, Evidence-Bound,
Generator, Semantic Validator, corpus e embeddings persistidos permaneceram
inalterados.

## Baseline e stack

- commit de referência: `5bc5093`;
- primary: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`;
- revision: `1427fd652930e4ba29e8149678df786c240d8825`;
- runtime: ONNX Runtime CPU;
- artefato: `onnx/model_quint8_avx2.onnx`;
- dependências experimentais adicionadas: `onnxruntime`, `transformers` e
  Torch CPU para o controle BGE;
- download source: Hugging Face Hub;
- Granite 3B não foi reexecutado.

O BGE foi consultado na revision
`953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, mas seu `model.safetensors`, de
aproximadamente 2 GB, não terminou de baixar. O JSON do controle registra
`NOT_RUN`; não há score ou inferência parcial.

## Dataset e metodologia

Foram usados os pares congelados das Fases 86–88: controles adversariais,
históricos e os targets de pena de morte e prisão perpétua. O modelo recebeu
somente `(query, assertion)`. Nenhum expected provision, artigo, case_id ou
resposta de referência foi enviado à inferência.

Os thresholds foram derivados uma vez da distribuição congelada:

```text
low  = max(score dos negativos) =  1.7888102531433105
high = min(score dos positivos) = -4.172726631164551
```

Como `low >= high`, não existe zona separável segura. A ordenação dos nomes
`low/high` é mantida no artefato para preservar o diagnóstico bruto; ela não
representa um threshold válido de produção.

## Primary — resultados

| Métrica | Resultado |
|---|---:|
| pares | 21 |
| relevantes | 14 |
| irrelevantes | 7 |
| false relevant | **3** |
| false irrelevant | 0 |
| unresolved | 0 |
| prisão perpétua | RELEVANT |
| pena de morte | RELEVANT |
| state of siege lateral | SAFE |
| média/p50/p95 | 2,20 / 2,20 / 2,20 ms |

Falha crítica:

```text
Query:      o presidente autoriza a medida
Assertion:  O tribunal autoriza a medida.
Esperado:   IRRELEVANT
Score:      1.7888102531433105
Decisão:    RELEVANT
```

O modelo também não separou os controles de forma útil. Embora tenha acertado
`TRUE_BUT_IRRELEVANT`, `SUPPORTED_BUT_OFF_TARGET` e
`RELATED_PROVISION_WRONG_ANSWER`, um único falso relevante já viola o gate.

## Controle BGE

`BAAI/bge-reranker-v2-m3` não foi executado. A falha operacional ocorreu antes
da inicialização do modelo, durante o download do peso. Portanto:

- não há decisão de qualidade;
- não há thresholds;
- não há latência;
- não é legítimo escolher ou rejeitar o BGE por score;
- a comparação entre os dois modelos permanece inconclusiva.

## Gate

O primary falhou porque `FALSE_RELEVANT != 0` e porque a distribuição positiva/
negativa não é separável. A ausência do controle impede concluir se o limite é
do MiniLM ou da arquitetura cross-encoder em geral.

O próximo passo, se autorizado, é apenas concluir a execução do BGE com os
mesmos pares e metodologia. Não ajustar thresholds, não alterar dados e não
testar terceiro modelo.

## Testes e artefatos

Foi criado o harness
`evaluation/relevance_model_benchmark_90.py` e testes focais em
`tests/test_relevance_model_benchmark.py`, cobrindo fixtures congeladas e a
zona `UNRESOLVED`. Os resultados estão em:

- `evaluation/results/relevance_model_benchmark_90_minilm.json`;
- `evaluation/results/relevance_model_benchmark_90_bge.json`;
- `evaluation/results/relevance_model_benchmark_90_summary.json`.

Não houve integração em produção, migration, ingestão, alteração de corpus ou
commit.

CONTROLLED_RELEVANCE_MODEL_BENCHMARK:
FAIL

PRIMARY_MODEL:
cross-encoder/mmarco-mMiniLMv2-L12-H384-v1

PRIMARY_GATE:
FAIL

CONTROL_MODEL:
BAAI/bge-reranker-v2-m3

CONTROL_GATE:
NOT_RUN

PRIMARY_HIGH_THRESHOLD:
-4.172726631164551

PRIMARY_LOW_THRESHOLD:
1.7888102531433105

CONTROL_HIGH_THRESHOLD:
N/A

CONTROL_LOW_THRESHOLD:
N/A

PRISAO_PERPETUA_PRIMARY:
RELEVANT

PRISAO_PERPETUA_CONTROL:
NOT_RUN

PENA_MORTE_PRIMARY:
RELEVANT

PENA_MORTE_CONTROL:
NOT_RUN

STATE_OF_SIEGE_PRIMARY:
SAFE

STATE_OF_SIEGE_CONTROL:
NOT_RUN

FALSE_RELEVANT_PRIMARY:
3

FALSE_IRRELEVANT_PRIMARY:
0

FALSE_RELEVANT_CONTROL:
N/A

FALSE_IRRELEVANT_CONTROL:
N/A

TRUE_BUT_IRRELEVANT_PRIMARY:
PASS

WRONG_LEGAL_ACTOR_PRIMARY:
FAIL

RELATED_PROVISION_PRIMARY:
PASS

SUPPORTED_BUT_OFF_TARGET_PRIMARY:
PASS

HISTORICAL_CORRECT_REGRESSIONS_PRIMARY:
0

PRIMARY_LATENCY_MEAN_MS:
2.196756428572501

PRIMARY_LATENCY_P50_MS:
2.196756428572501

PRIMARY_LATENCY_P95_MS:
2.196756428572501

CONTROL_LATENCY_MEAN_MS:
N/A

PRIMARY_RAM_MB:
N/A

CONTROL_RAM_MB:
N/A

OFFLINE_CORRECT_POTENTIAL:
9/10

UNSAFE_PRODUCT_ANSWERS:
0

BEST_MODEL:
NONE

SMALL_DISCRIMINATIVE_RELEVANCE:
NOT_JUSTIFIED

VCSA_DECISION:
KEEP_FOUNDATION

EVIDENCE_BOUND_DECISION:
KEEP_EXPERIMENTAL

RECOMMENDED_NEXT_STEP:
MODEL_ARCHITECTURE_REVIEW

PRODUCTION_INTEGRATION:
NOT_ENABLED

COMMIT:
DO_NOT_COMMIT_YET
