# Fase 1 — diagnóstico read-only do ranking RELAXED_OR

## Escopo

Este diagnóstico explica os oito misses Hit@10 do artefato congelado
`lei_9784_fts_relaxed_or_v1.json`. Nenhum benchmark foi reexecutado e nenhum
runtime, dataset, SearchUnit, projection, SQL ou banco foi alterado.

Os lexemas foram produzidos exclusivamente por
`to_tsvector('portuguese', ...)`. `query_coverage` atribui o mesmo peso a cada
lexema e corresponde a `matched_query_lexemes / query_lexemes`.

## Resultado agregado

```text
DIAGNOSTIC_CASE_COUNT: 8

DIAGNOSTIC_CLASS_COUNTS:
  RANK_FUNCTION_MISMATCH: 3
  TARGET_LOW_LEXICAL_COVERAGE: 1
  COVERAGE_TIE_DILUTION: 2
  POSSIBLE_REPRESENTATION_LIMIT: 2
  OTHER: 0

TARGETS_ENTERING_TOP10_WITH_COVERAGE_ONLY_SIMULATION: 3
TARGETS_ENTERING_TOP10_WITH_COVERAGE_THEN_TS_RANK_SIMULATION: 3
```

| Caso | Target rank | Coverage | Sim. coverage | Sim. coverage+rank | Classe |
|---|---:|---:|---:|---:|---|
| DEV-001 | 59 | 1/7 = 0,143 | 45 | 54 | `POSSIBLE_REPRESENTATION_LIMIT` |
| DEV-002 | 57 | 2/7 = 0,286 | 46 | 51 | `POSSIBLE_REPRESENTATION_LIMIT` |
| DEV-004 | 19 | 2/5 = 0,400 | 13 | 19 | `TARGET_LOW_LEXICAL_COVERAGE` |
| DEV-011 | 17 | 3/7 = 0,429 | 2 | 3 | `RANK_FUNCTION_MISMATCH` |
| DEV-014 | 30 | 2/6 = 0,333 | 19 | 21 | `COVERAGE_TIE_DILUTION` |
| DEV-030 | 24 | 2/5 = 0,400 | 14 | 14 | `COVERAGE_TIE_DILUTION` |
| DEV-031 | 11 | 3/8 = 0,375 | 7 | 10 | `RANK_FUNCTION_MISMATCH` |
| DEV-040 | 50 | 3/8 = 0,375 | 9 | 9 | `RANK_FUNCTION_MISMATCH` |

As posições simuladas são apenas diagnósticas e não constituem novas métricas
oficiais.

## Diagnósticos por caso

### DEV-001

```text
QUERY_LEXEMES: administr, autor, consider, federal, fins, process, é
TARGET: ARTICLE:1/PARAGRAPH:2/INCISO:III
TARGET_RANK: 59
TARGET_TS_RANK_CD: 0,100
TARGET_MATCHED_LEXEMES: autor
TARGET_QUERY_COVERAGE: 1/7 = 0,143
TOP10_LOWER/EQUAL/HIGHER: 0/0/10
SIMULATED_COVERAGE_ONLY_POSITION: 45
SIMULATED_COVERAGE_THEN_TS_RANK_POSITION: 54
CLASS: POSSIBLE_REPRESENTATION_LIMIT
```

O inciso isolado define “autoridade”, mas seu pai contém “Para os fins desta
Lei, consideram-se”, e o CAPUT do artigo contém “processo administrativo”,
“Administração Federal” e “fins”. A estrutura relacionada possui quatro dos
lexemas consultados que não aparecem na unidade-alvo.

| Rank | Unit key | Score | Matched | Coverage |
|---:|---|---:|---|---:|
| 1 | `ARTICLE:1/CAPUT` | 0,700 | administr, federal, fins, process | 4/7 |
| 2 | `ARTICLE:49-A/PARAGRAPH:1` | 0,500 | administr, autor, fins, process | 4/7 |
| 3 | `ARTICLE:18/CAPUT` | 0,400 | administr, autor, é, process | 4/7 |
| 4 | `ARTICLE:64-B/CAPUT` | 0,400 | administr, autor, federal | 3/7 |
| 5 | `PREAMBLE` | 0,400 | administr, federal, process | 3/7 |
| 6 | `ARTICLE:10/CAPUT` | 0,300 | administr, fins, process | 3/7 |
| 7 | `ARTICLE:17/CAPUT` | 0,300 | administr, autor, process | 3/7 |
| 8 | `ARTICLE:24/CAPUT` | 0,300 | administr, autor, process | 3/7 |
| 9 | `ARTICLE:37/CAPUT` | 0,300 | administr, process | 2/7 |
| 10 | `ARTICLE:48/CAPUT` | 0,300 | administr, process | 2/7 |

### DEV-002

```text
QUERY_LEXEMES: administr, advog, assist, interess, pod, process, ser
TARGET: ARTICLE:3/CAPUT/INCISO:IV
TARGET_RANK: 57
TARGET_TS_RANK_CD: 0,200
TARGET_MATCHED_LEXEMES: advog, assist
TARGET_QUERY_COVERAGE: 2/7 = 0,286
TOP10_LOWER/EQUAL/HIGHER: 0/1/9
SIMULATED_COVERAGE_ONLY_POSITION: 46
SIMULATED_COVERAGE_THEN_TS_RANK_POSITION: 51
CLASS: POSSIBLE_REPRESENTATION_LIMIT
```

O inciso contém a conduta “fazer-se assistir por advogado”, mas o sujeito e o
papel jurídico da enumeração estão no CAPUT: “O administrado tem os seguintes
direitos perante a Administração”. A unidade isolada perde esse contexto
governante.

| Rank | Unit key | Score | Matched | Coverage |
|---:|---|---:|---|---:|
| 1 | `ARTICLE:1/CAPUT` | 0,500 | administr, process | 2/7 |
| 2 | `ARTICLE:31/PARAGRAPH:2` | 0,500 | administr, interess, pod, process, ser | 5/7 |
| 3 | `ARTICLE:35/CAPUT` | 0,500 | administr, pod, process, ser | 4/7 |
| 4 | `ARTICLE:26/PARAGRAPH:3` | 0,400 | interess, pod, process, ser | 4/7 |
| 5 | `ARTICLE:37/CAPUT` | 0,400 | administr, interess, process | 3/7 |
| 6 | `ARTICLE:42/PARAGRAPH:2` | 0,400 | pod, process, ser | 3/7 |
| 7 | `ARTICLE:49-A/CAPUT` | 0,400 | administr, pod, ser | 3/7 |
| 8 | `ARTICLE:5/CAPUT` | 0,400 | administr, interess, pod, process | 4/7 |
| 9 | `ARTICLE:65/CAPUT` | 0,400 | administr, pod, process, ser | 4/7 |
| 10 | `ARTICLE:17/CAPUT` | 0,300 | administr, process, ser | 3/7 |

### DEV-004

```text
QUERY_LEXEMES: administr, competent, pod, renunc, ser
TARGET: ARTICLE:11/CAPUT
TARGET_RANK: 19
TARGET_TS_RANK_CD: 0,200
TARGET_MATCHED_LEXEMES: administr, competent
TARGET_QUERY_COVERAGE: 2/5 = 0,400
TOP10_LOWER/EQUAL/HIGHER: 1/3/6
SIMULATED_COVERAGE_ONLY_POSITION: 13
SIMULATED_COVERAGE_THEN_TS_RANK_POSITION: 19
CLASS: TARGET_LOW_LEXICAL_COVERAGE
```

A pergunta usa “renunciada”; a fonte usa “irrenunciável”. A informação está na
própria unidade, mas a normalização portuguesa não produz o mesmo lexema. A
simulação por cobertura continua fora do top 10.

| Rank | Unit key | Score | Matched | Coverage |
|---:|---|---:|---|---:|
| 1 | `ARTICLE:35/CAPUT` | 0,500 | administr, competent, pod, ser | 4/5 |
| 2 | `ARTICLE:1/CAPUT` | 0,400 | administr | 1/5 |
| 3 | `ARTICLE:49-A/CAPUT` | 0,400 | administr, pod, ser | 3/5 |
| 4 | `ARTICLE:12/CAPUT` | 0,300 | administr, competent, pod | 3/5 |
| 5 | `ARTICLE:17/CAPUT` | 0,300 | administr, competent, ser | 3/5 |
| 6 | `ARTICLE:22/PARAGRAPH:3` | 0,300 | administr, pod, ser | 3/5 |
| 7 | `ARTICLE:31/PARAGRAPH:2` | 0,300 | administr, pod, ser | 3/5 |
| 8 | `ARTICLE:33/CAPUT` | 0,300 | administr, pod | 2/5 |
| 9 | `ARTICLE:37/CAPUT` | 0,300 | administr, competent | 2/5 |
| 10 | `ARTICLE:42/PARAGRAPH:2` | 0,300 | pod, ser | 2/5 |

### DEV-011

```text
QUERY_LEXEMES: administr, cobr, despes, lei, pod, previsã, processu
TARGET: ARTICLE:2/PARAGRAPH:UNIQUE/INCISO:XI
TARGET_RANK: 17
TARGET_TS_RANK_CD: 0,200
TARGET_MATCHED_LEXEMES: despes, lei, processu
TARGET_QUERY_COVERAGE: 3/7 = 0,429
TOP10_LOWER/EQUAL/HIGHER: 8/2/0
SIMULATED_COVERAGE_ONLY_POSITION: 2
SIMULATED_COVERAGE_THEN_TS_RANK_POSITION: 3
CLASS: RANK_FUNCTION_MISMATCH
```

O target tem cobertura superior a oito candidatos top-10 e entraria no top 3
nas duas simulações.

| Rank | Unit key | Score | Matched | Coverage |
|---:|---|---:|---|---:|
| 1 | `ARTICLE:1/CAPUT` | 0,500 | administr, lei | 2/7 |
| 2 | `ARTICLE:49-A/CAPUT` | 0,400 | administr, lei, pod | 3/7 |
| 3 | `PREAMBLE` | 0,400 | administr, lei | 2/7 |
| 4 | `ARTICLE:1/PARAGRAPH:1` | 0,300 | administr, lei, pod | 3/7 |
| 5 | `ARTICLE:33/CAPUT` | 0,300 | administr, pod | 2/7 |
| 6 | `ARTICLE:49-A/PARAGRAPH:1` | 0,300 | administr, lei | 2/7 |
| 7 | `ARTICLE:49-B/CAPUT` | 0,300 | lei, pod | 2/7 |
| 8 | `ARTICLE:64-B/CAPUT` | 0,300 | administr, lei | 2/7 |
| 9 | `ARTICLE:69/CAPUT` | 0,300 | administr, lei | 2/7 |
| 10 | `ARTICLE:10/CAPUT` | 0,200 | administr, previsã | 2/7 |

### DEV-014

```text
QUERY_LEXEMES: administr, automat, decisã, efeit, recurs, suspend
TARGET: ARTICLE:61/CAPUT
TARGET_RANK: 30
TARGET_TS_RANK_CD: 0,200
TARGET_MATCHED_LEXEMES: efeit, recurs
TARGET_QUERY_COVERAGE: 2/6 = 0,333
TOP10_LOWER/EQUAL/HIGHER: 1/6/3
SIMULATED_COVERAGE_ONLY_POSITION: 19
SIMULATED_COVERAGE_THEN_TS_RANK_POSITION: 21
CLASS: COVERAGE_TIE_DILUTION
```

Seis candidatos top-10 empatam em cobertura com o target, e três a superam. A
ordenação por cobertura não o leva ao top 10.

| Rank | Unit key | Score | Matched | Coverage |
|---:|---|---:|---|---:|
| 1 | `ARTICLE:1/CAPUT` | 0,400 | administr | 1/6 |
| 2 | `ARTICLE:56/PARAGRAPH:3` | 0,400 | administr, decisã, recurs | 3/6 |
| 3 | `ARTICLE:13/CAPUT/INCISO:II` | 0,300 | administr, decisã, recurs | 3/6 |
| 4 | `ARTICLE:48/CAPUT` | 0,300 | administr, decisã | 2/6 |
| 5 | `ARTICLE:49-A/CAPUT` | 0,300 | administr, decisã | 2/6 |
| 6 | `ARTICLE:54/CAPUT` | 0,300 | administr, efeit | 2/6 |
| 7 | `ARTICLE:57/CAPUT` | 0,300 | administr, recurs | 2/6 |
| 8 | `ARTICLE:59/CAPUT` | 0,300 | administr, decisã, recurs | 3/6 |
| 9 | `ARTICLE:63/PARAGRAPH:2` | 0,300 | administr, recurs | 2/6 |
| 10 | `ARTICLE:64-B/CAPUT` | 0,300 | administr, recurs | 2/6 |

### DEV-030

```text
QUERY_LEXEMES: administr, conhec, hipótes, qua, recurs
TARGET: ARTICLE:63/CAPUT
TARGET_RANK: 24
TARGET_TS_RANK_CD: 0,200
TARGET_MATCHED_LEXEMES: conhec, recurs
TARGET_QUERY_COVERAGE: 2/5 = 0,400
TOP10_LOWER/EQUAL/HIGHER: 5/4/1
SIMULATED_COVERAGE_ONLY_POSITION: 14
SIMULATED_COVERAGE_THEN_TS_RANK_POSITION: 14
CLASS: COVERAGE_TIE_DILUTION
```

O target supera cinco candidatos top-10, mas permanece no rank 14 em ambas as
simulações porque há um grupo maior com cobertura igual ou superior.

| Rank | Unit key | Score | Matched | Coverage |
|---:|---|---:|---|---:|
| 1 | `ARTICLE:1/CAPUT` | 0,400 | administr | 1/5 |
| 2 | `ARTICLE:63/PARAGRAPH:2` | 0,400 | administr, conhec, recurs | 3/5 |
| 3 | `ARTICLE:57/CAPUT` | 0,300 | administr, recurs | 2/5 |
| 4 | `ARTICLE:64-B/CAPUT` | 0,300 | administr, recurs | 2/5 |
| 5 | `ARTICLE:13/CAPUT/INCISO:II` | 0,200 | administr, recurs | 2/5 |
| 6 | `ARTICLE:1/PARAGRAPH:2/INCISO:I` | 0,200 | administr | 1/5 |
| 7 | `ARTICLE:33/CAPUT` | 0,200 | administr | 1/5 |
| 8 | `ARTICLE:37/CAPUT` | 0,200 | administr | 1/5 |
| 9 | `ARTICLE:3/CAPUT` | 0,200 | administr | 1/5 |
| 10 | `ARTICLE:3/CAPUT/INCISO:II` | 0,200 | administr, conhec | 2/5 |

### DEV-031

```text
QUERY_LEXEMES: administr, exig, firm, pod, process, reconhec, ser, situaçã
TARGET: ARTICLE:22/PARAGRAPH:2
TARGET_RANK: 11
TARGET_TS_RANK_CD: 0,300
TARGET_MATCHED_LEXEMES: exig, firm, reconhec
TARGET_QUERY_COVERAGE: 3/8 = 0,375
TOP10_LOWER/EQUAL/HIGHER: 1/5/4
SIMULATED_COVERAGE_ONLY_POSITION: 7
SIMULATED_COVERAGE_THEN_TS_RANK_POSITION: 10
CLASS: RANK_FUNCTION_MISMATCH
```

O target possui cobertura igual ou superior a seis candidatos top-10 e entra
no top 10 nas duas simulações.

| Rank | Unit key | Score | Matched | Coverage |
|---:|---|---:|---|---:|
| 1 | `ARTICLE:1/CAPUT` | 0,500 | administr, process | 2/8 |
| 2 | `ARTICLE:35/CAPUT` | 0,500 | administr, pod, process, ser | 4/8 |
| 3 | `ARTICLE:22/PARAGRAPH:3` | 0,400 | administr, exig, pod, ser | 4/8 |
| 4 | `ARTICLE:31/PARAGRAPH:2` | 0,400 | administr, pod, process, ser | 4/8 |
| 5 | `ARTICLE:33/CAPUT` | 0,400 | administr, pod, reconhec | 3/8 |
| 6 | `ARTICLE:42/PARAGRAPH:2` | 0,400 | pod, process, ser | 3/8 |
| 7 | `ARTICLE:49-A/CAPUT` | 0,400 | administr, pod, ser | 3/8 |
| 8 | `ARTICLE:65/CAPUT` | 0,400 | administr, pod, process, ser | 4/8 |
| 9 | `ARTICLE:17/CAPUT` | 0,300 | administr, process, ser | 3/8 |
| 10 | `ARTICLE:22/CAPUT` | 0,300 | administr, exig, process | 3/8 |

### DEV-040

```text
QUERY_LEXEMES: administr, dev, faz, obter, pesso, prioridad, process, tramit
TARGET: ARTICLE:69-A/PARAGRAPH:1
TARGET_RANK: 50
TARGET_TS_RANK_CD: 0,200
TARGET_MATCHED_LEXEMES: administr, dev, pesso
TARGET_QUERY_COVERAGE: 3/8 = 0,375
TOP10_LOWER/EQUAL/HIGHER: 3/6/1
SIMULATED_COVERAGE_ONLY_POSITION: 9
SIMULATED_COVERAGE_THEN_TS_RANK_POSITION: 9
CLASS: RANK_FUNCTION_MISMATCH
```

O target possui cobertura igual ou superior a nove candidatos top-10 e entra
no rank 9 nas duas simulações.

| Rank | Unit key | Score | Matched | Coverage |
|---:|---|---:|---|---:|
| 1 | `ARTICLE:1/CAPUT` | 0,500 | administr, process | 2/8 |
| 2 | `ARTICLE:23/CAPUT` | 0,400 | dev, process, tramit | 3/8 |
| 3 | `ARTICLE:3/CAPUT/INCISO:II` | 0,400 | administr, obter, process, tramit | 4/8 |
| 4 | `ARTICLE:48/CAPUT` | 0,400 | administr, dev, process | 3/8 |
| 5 | `ARTICLE:17/CAPUT` | 0,300 | administr, dev, process | 3/8 |
| 6 | `ARTICLE:24/CAPUT` | 0,300 | administr, dev, process | 3/8 |
| 7 | `ARTICLE:26/CAPUT` | 0,300 | administr, process, tramit | 3/8 |
| 8 | `ARTICLE:28/CAPUT` | 0,300 | dev, process | 2/8 |
| 9 | `ARTICLE:31/PARAGRAPH:2` | 0,300 | administr, obter, process | 3/8 |
| 10 | `ARTICLE:37/CAPUT` | 0,300 | administr, process | 2/8 |

## Conclusão causal

A limitação lexical de ranking possui evidência forte: cinco dos oito casos são
`RANK_FUNCTION_MISMATCH` ou `COVERAGE_TIE_DILUTION`, e três targets entram no
top 10 nas duas simulações de cobertura. Há evidência parcial de limitação de
representação em dois incisos cujo contexto governante está em pai/CAPUT. Um
caso tem baixa cobertura decorrente de divergência lexical entre “renunciada”
e “irrenunciável”.

```text
STRICT_RELAXED_FUSION_CURRENT_DEV: DEGENERATE
VECTOR_JUSTIFIED: NO
SEARCHUNIT_REPRESENTATION_LIMITATION_EVIDENCE: PARTIAL
LEXICAL_RANKING_LIMITATION_EVIDENCE: STRONG
NEXT_HYPOTHESIS: LEXICAL_COVERAGE_RANKING
```

O contrato atual não mede insuficiência, ambiguidade ou suporte composto. Esses
problemas exigem contratos próprios e permanecem questões abertas.
