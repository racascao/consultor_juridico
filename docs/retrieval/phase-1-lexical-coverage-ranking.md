# Fase 1 — experimento Lexical Coverage Ranking

## Hipótese isolada

O experimento preservou a geração de candidatos `RELAXED_OR` e alterou somente
a ordenação para:

```text
query_coverage DESC
ts_rank_cd DESC
unit_key ASC
```

`query_coverage` é a razão entre lexemas distintos da pergunta encontrados na
SearchUnit e os lexemas distintos da pergunta. Pergunta e candidato são
normalizados exclusivamente pelo PostgreSQL com a configuração `portuguese`.
Não foram adicionados pesos, filtros, thresholds, sinônimos ou tokenização
Python. Lexemas repetidos no candidato contam uma vez.

O dataset, a projeção `provision-text/1`, a ActVersion, o `ts_rank_cd` e a
geração `RELAXED_OR` permaneceram congelados. Não houve migration.

## Diagnóstico da configuração portuguesa

O PostgreSQL real foi consultado com `ts_debug('portuguese', ...)` antes da
implementação:

| Token | Dicionário | Lexemas | Stopword |
|---|---|---|---|
| `é` | `portuguese_stem` | `é` | não |
| `ser` | `portuguese_stem` | `ser` | não |
| `sou` | `portuguese_stem` | — | sim |
| `somos` | `portuguese_stem` | — | sim |
| `pode` | `portuguese_stem` | `pod` | não |
| `poder` | `portuguese_stem` | `pod` | não |
| `deve` | `portuguese_stem` | `dev` | não |
| `fazer` | `portuguese_stem` | `faz` | não |

O vetor observado foi:

```text
'dev':7 'faz':8 'pod':5,6 'ser':2 'é':1
```

`é` e outros lexemas comuns sobreviventes podem aumentar ruído e empates. Essa
é uma limitação conhecida, mas a configuração não foi alterada porque a
simulação que motivou o experimento já a utilizava.

As consultas DEV-001 e DEV-002 reproduziram exatamente o diagnóstico anterior:

```text
DEV-001: administr, autor, consider, federal, fins, process, é
DEV-002: administr, advog, assist, interess, pod, process, ser
```

## Regressões implementadas

Os testes PostgreSQL cobrem:

- cobertura de 1/3, 2/3 e 3/3;
- lexema repetido contado uma única vez para cobertura;
- desempate por `ts_rank_cd` quando a cobertura é igual;
- desempate final por `unit_key ASC`;
- pergunta sem lexemas;
- filtro explícito por ActVersion e ausência de vazamento entre versões.

## Medição congelada

A medição completa do DEV foi executada uma única vez:

```text
dataset: evaluation/datasets/lei_9784_retrieval_dev_v1.json
dataset SHA-256: bc47eb6e7364931767fb2305cc9ce5a55ce7763e9f88cb6bbf224609dbe221aa
version_hash: 298028477a55a61cdd1df94bda3aec784e6fe94d17c485ae6a2f6c77fe2b7a74
mode: relaxed-or-coverage
result: evaluation/results/lei_9784_fts_relaxed_or_coverage_v1.json
result SHA-256: 82c7189ff5ab4eb8ee3717a5506ed40ba099826f62df4b1f5a160de66c4391d7
```

| Métrica | RELAXED_OR | Coverage | Delta |
|---|---:|---:|---:|
| Hit@1 | 0,425 | 0,575 | +0,150 |
| Hit@3 | 0,675 | 0,700 | +0,025 |
| Hit@5 | 0,725 | 0,750 | +0,025 |
| Hit@10 | 0,800 | 0,875 | +0,075 |
| MRR | 0,549 | 0,661 | +0,112 |
| latência p50 | 4,367 ms | 11,639 ms | +7,272 ms |
| latência p95 observada | 6,413 ms | 16,629 ms | +10,216 ms |

Treze casos melhoraram, 26 permaneceram na mesma posição e DEV-024 regrediu
de rank 5 para rank 6. DEV-011, DEV-031 e DEV-040 entraram no top 10; nenhum
caso anteriormente presente no top 10 foi perdido.

```text
IMPROVED_CASES:
DEV-003, DEV-005, DEV-006, DEV-007, DEV-009, DEV-011, DEV-020,
DEV-022, DEV-029, DEV-031, DEV-032, DEV-039, DEV-040

REGRESSED_CASES:
DEV-024

RECOVERED_TOP10_CASES:
DEV-011, DEV-031, DEV-040

LOST_TOP10_CASES:
nenhum
```

## Misses residuais

| Caso | Posição diagnóstica | Classe principal |
|---|---:|---|
| DEV-001 | 54 | `POSSIBLE_REPRESENTATION_LIMIT` |
| DEV-002 | 51 | `POSSIBLE_REPRESENTATION_LIMIT` |
| DEV-004 | 19 | `LEXICAL_VOCABULARY_LIMIT` |
| DEV-014 | 21 | `COVERAGE_TIE_DILUTION` |
| DEV-030 | 14 | `COVERAGE_TIE_DILUTION` |

Os dois primeiros targets continuam sem o contexto governante presente em
pai/CAPUT. DEV-004 usa “renunciada” enquanto a fonte contém “irrenunciável”.
DEV-014 e DEV-030 permanecem diluídos entre candidatos com cobertura igual ou
superior.

## Avaliação e limites

`COVERAGE_RANKING_ASSESSMENT: CLEAR_IMPROVEMENT`.

O ganho ocorre em todos os agregados de qualidade, recupera três misses sem
perder hits top-10 e apresenta uma regressão limitada. A latência lexical
aumentou, embora permaneça na ordem de dezenas de milissegundos neste corpus.

O contrato atual mede apenas ranking positivo por `Provision.stable_key`. Ele
não mede suficiência, abstenção, ambiguidade ou suporte composto. Esses
contratos são obrigatórios antes de aceitação end-to-end futura e não devem ser
simulados com threshold ad hoc.

```text
OUT_OF_SCOPE_QUERY_RISK: OPEN
CURRENT_RETRIEVAL_CONTRACT_SUPPORTS_EVIDENCE_SUFFICIENCY: NO
CURRENT_RETRIEVAL_CONTRACT_SUPPORTS_ABSTENTION: NO
NEXT_HYPOTHESIS: KEEP_LEXICAL_COVERAGE_RANKING
```

A Fase 1 permanece aberta até revisão humana. Nenhuma técnica adicional está
autorizada por este resultado.
