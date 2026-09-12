# Diagnóstico read-only de retrieval para evidência insuficiente

## Objetivo e limites

Este diagnóstico descreve como o retrieval lexical já congelado se comporta
nas seis perguntas `INSUFFICIENT_EVIDENCE` do DEV Gold Evidence. Ele não é um
benchmark oficial da Fase 1, não mede acerto, precisão ou abstenção, não altera
runtime e não autoriza tuning.

Configuração preservada:

```text
ActVersion: 298028477a55a61cdd1df94bda3aec784e6fe94d17c485ae6a2f6c77fe2b7a74
candidate generation: RELAXED_OR
ranking: query_coverage DESC, ts_rank_cd DESC, unit_key ASC
limit: 10
```

Somente `question`, `version_hash` e `limit` foram fornecidos ao retrieval. As
categorias, decisões esperadas e listas Gold não participaram da consulta.

## Resultados

Todos os seis casos retornaram 10 candidatos. As tabelas apresentam os três
primeiros; `query_coverage` e `ts_rank_cd` são sinais de ordenação, não
probabilidades nem medidas calibradas entre perguntas.

### GOLD-021

Pergunta: “Qual é o prazo para a Administração concluir uma licitação pública?”

| rank | unit_key | Provisions | query_coverage | ts_rank_cd |
|---:|---|---|---:|---:|
| 1 | `ARTICLE:59/CAPUT` | `ARTICLE:59/CAPUT` | 0.500000 | 0.300000 |
| 2 | `ARTICLE:2/CAPUT` | `ARTICLE:2/CAPUT` | 0.333333 | 0.300000 |
| 3 | `ARTICLE:49-A/CAPUT` | `ARTICLE:49-A/CAPUT` | 0.333333 | 0.300000 |

### GOLD-022

Pergunta: “Qual é a pena criminal por falsificar documento apresentado em
processo administrativo?”

| rank | unit_key | Provisions | query_coverage | ts_rank_cd |
|---:|---|---|---:|---:|
| 1 | `ARTICLE:40/CAPUT` | `ARTICLE:40/CAPUT` | 0.500000 | 0.400000 |
| 2 | `ARTICLE:37/CAPUT` | `ARTICLE:37/CAPUT` | 0.375000 | 0.500000 |
| 3 | `ARTICLE:18/CAPUT` | `ARTICLE:18/CAPUT` | 0.375000 | 0.300000 |

### GOLD-023

Pergunta: “Qual é o prazo para ajuizar ação judicial contra uma decisão
administrativa?”

| rank | unit_key | Provisions | query_coverage | ts_rank_cd |
|---:|---|---|---:|---:|
| 1 | `ARTICLE:59/CAPUT` | `ARTICLE:59/CAPUT` | 0.500000 | 0.400000 |
| 2 | `ARTICLE:56/PARAGRAPH:3` | `ARTICLE:56/PARAGRAPH:3` | 0.375000 | 0.400000 |
| 3 | `ARTICLE:48/CAPUT` | `ARTICLE:48/CAPUT` | 0.250000 | 0.300000 |

### GOLD-024

Pergunta: “Qual valor deve ser pago a título de dano moral causado pela
Administração?”

| rank | unit_key | Provisions | query_coverage | ts_rank_cd |
|---:|---|---|---:|---:|
| 1 | `ARTICLE:43/CAPUT` | `ARTICLE:43/CAPUT` | 0.333333 | 0.400000 |
| 2 | `ARTICLE:17/CAPUT` | `ARTICLE:17/CAPUT` | 0.333333 | 0.300000 |
| 3 | `ARTICLE:23/PARAGRAPH:UNIQUE` | `ARTICLE:23/PARAGRAPH:UNIQUE` | 0.333333 | 0.300000 |

### GOLD-025

Pergunta: “Quais são os requisitos para aposentadoria de servidor público
federal?”

| rank | unit_key | Provisions | query_coverage | ts_rank_cd |
|---:|---|---|---:|---:|
| 1 | `ARTICLE:1/PARAGRAPH:2/INCISO:III` | `ARTICLE:1/PARAGRAPH:2/INCISO:III` | 0.333333 | 0.200000 |
| 2 | `ARTICLE:49-A/CAPUT` | `ARTICLE:49-A/CAPUT` | 0.333333 | 0.200000 |
| 3 | `PREAMBLE` | `PREAMBLE` | 0.333333 | 0.200000 |

### GOLD-026

Pergunta: “Em quais hipóteses dados pessoais podem ser compartilhados entre
órgãos públicos?”

| rank | unit_key | Provisions | query_coverage | ts_rank_cd |
|---:|---|---|---:|---:|
| 1 | `ARTICLE:49-A/CAPUT` | `ARTICLE:49-A/CAPUT` | 0.444444 | 0.400000 |
| 2 | `ARTICLE:35/CAPUT` | `ARTICLE:35/CAPUT` | 0.333333 | 0.500000 |
| 3 | `ARTICLE:22/PARAGRAPH:3` | `ARTICLE:22/PARAGRAPH:3` | 0.333333 | 0.300000 |

## Interpretação limitada

```text
OUT_OF_SCOPE_RETRIEVAL_BEHAVIOR: CANDIDATES_COMMONLY_PRESENT
RUNTIME_CHANGED_DUE_TO_DIAGNOSTIC: NO
THRESHOLD_DERIVED: NO
```

O resultado significa apenas que o candidate generator encontra unidades
lexicalmente relacionadas mesmo quando a Lei nº 9.784/1999 não fornece suporte
suficiente para a resposta solicitada. Esses candidatos não são chamados de
“falsos positivos”, e seus scores não estabelecem suficiência jurídica.

A Fase 2 Gold Evidence mede a capacidade intrínseca do modelo para `ANSWER`,
`ABSTAIN` e `CLARIFY` quando a evidência é declarada diretamente. A futura
integração RAG precisará testar a condição mais difícil: top-K não vazio com
evidência irrelevante ou apenas parcialmente relacionada deve ainda resultar
em abstenção segura. O Gold Evidence v1 não resolve nem mede essa integração.
