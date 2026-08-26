# Fase 91 — Definitive MVP1 Model Benchmark

## Estado da execução

O benchmark definitivo não foi concluído. O ambiente Docker/Ollama estava
saudável e continha os sete modelos exigidos, mas a inferência sequencial em CPU
foi operacionalmente longa demais para completar a matriz nesta execução.

Foi criado um harness resumível em
`evaluation/model_benchmark_91.py`. Ele grava cada chamada atomicamente e usa
manifesto implícito dos pares congelados. O artefato parcial contém somente sete
chamadas do Granite 3B, todas em controles de relevance; não há base para
rankear modelos, judges ou configurações end-to-end.

### Ambiente observado

- Ollama: `0.32.15`;
- PostgreSQL/Compose: saudável;
- modelos presentes: Granite 3B/8B, Qwen 4B/9B, Ministral 3B/8B e DeepSeek-R1
  8B;
- quantização observada: Q4_K_M;
- nenhum modelo adicional foi baixado;
- retrieval, embeddings, corpus e produção não foram alterados.

### Limitação operacional

Cada chamada individual do estágio de relevance levou dezenas de segundos em
CPU. A matriz mínima desse estágio já exige 735 chamadas (7 modelos × 21 pares
× 5 repetições), antes de semantic support, generator, matriz de combinações e
estabilidade final. A execução foi interrompida com `Ctrl+C`, sem converter
timeouts em resultados incorretos.

O checkpoint parcial está em:

`evaluation/results/model_benchmark_91_relevance.json`

Ele pode ser retomado sem repetir as sete chamadas já gravadas. Nenhum resultado
parcial foi usado para escolher modelo.

## Decisão

Não é possível determinar Generator, Semantic Judge, Relevance Judge ou
configuração end-to-end vencedora. A exploração de modelos permanece aberta até
que a matriz definida no protocolo seja executada integralmente, possivelmente
com lotes mais eficientes e os mesmos prompts/datasets congelados.

Nenhum modelo foi integrado em produção. Nenhuma migration, ingestão, alteração
de retrieval, embedding ou dataset foi realizada.

DEFINITIVE_MODEL_BENCHMARK:
INCONCLUSIVE

MODELS_TESTED:
granite4.1:3b (parcial; 7 chamadas)

BEST_GENERATOR:
NONE

BEST_SEMANTIC_JUDGE:
NONE

BEST_RELEVANCE_JUDGE:
NONE

BEST_END_TO_END_GENERATOR:
NONE

BEST_END_TO_END_JUDGE:
NONE

BEST_END_TO_END_RELEVANCE_JUDGE:
NONE

REAL_WORLD_CORRECT_MEAN:
N/A

REAL_WORLD_CORRECT_MIN:
N/A

REAL_WORLD_CORRECT_MAX:
N/A

FALSE_ABSTENTION_MEAN:
N/A

UNSAFE_PRODUCT_ANSWERS:
N/A

FALSE_RELEVANT:
N/A

FALSE_SUPPORT:
N/A

WRONG_LEGAL_ACTOR:
N/A

TRUE_BUT_IRRELEVANT:
N/A

SUPPORTED_BUT_OFF_TARGET:
N/A

QUALIFIER_PRESERVATION:
N/A

CORRECT_ABSTENTION:
N/A

INVALID_CITATION_CHAINS:
N/A

MVP1_HIT_AT_10:
0.905 (baseline histórico, não reavaliado)

GENERATOR_CONSISTENCY:
N/A

JUDGE_CONSISTENCY:
N/A

BEST_CONFIG_LATENCY_MEAN:
N/A

BEST_CONFIG_LATENCY_P95:
N/A

BEST_CONFIG_RAM:
N/A

MVP1_GENERATOR_MODEL:
NONE

MVP1_SEMANTIC_JUDGE_MODEL:
NONE

MVP1_RELEVANCE_JUDGE_MODEL:
NONE

MODEL_SELECTION:
NO_MODEL_MEETS_MVP1_GATE

MVP1_QUALITY_GATE:
BLOCKED

MODEL_TOPIC:
OPEN

NEXT_STEP:
RETURN_TO_ARCHITECTURE

PRODUCTION_INTEGRATION:
NOT_ENABLED

COMMIT:
DO_NOT_COMMIT_YET
