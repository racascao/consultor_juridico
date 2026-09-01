# Fase 1 — baseline PostgreSQL FTS

## Objetivo e congelamento

A Fase 1 mede, sem otimização posterior, a capacidade de PostgreSQL Full Text
Search recuperar dispositivos juridicamente relevantes da Lei nº 9.784/1999.
O corpus é a `ActVersion` explícita
`298028477a55a61cdd1df94bda3aec784e6fe94d17c485ae6a2f6c77fe2b7a74`,
derivada do snapshot
`face6f55eb86aa7e13f31e03ce6f8f0854a95647c235a29dd661ea83b64ce355`.

A projeção permaneceu congelada em `provision-text/1`: cada unidade textual
contém somente o `citation_text` da Provision ligada. Não foram acrescentados
ancestrais, contexto, paráfrases, sinônimos ou rótulos sintéticos.

## Dataset DEV

O DEV foi escrito e seus targets foram validados contra a ActVersion antes da
implementação do retriever:

```text
arquivo: evaluation/datasets/lei_9784_retrieval_dev_v1.json
casos: 40
SHA-256: bc47eb6e7364931767fb2305cc9ce5a55ce7763e9f88cb6bbf224609dbe221aa
```

Há cinco casos em cada categoria: `DIRECT_RULE`, `PARAPHRASE`, `NEGATIVE`,
`DEADLINE`, `COMPETENCE`, `ENUMERATION`, `EXCEPTION` e `PROCEDURE`. O target
jurídico é sempre `Provision.stable_key`; uma SearchUnit só conta como hit se
um vínculo `SearchUnitProvision` apontar para um target explicitamente listado.
Não existe equivalência automática por artigo, pai, filho ou irmão.

O HOLDOUT não foi criado, lido nem solicitado.

## Implementação lexical

O adapter `PostgresFullTextSearchRetriever` preserva o baseline estrito:

```text
text search config: portuguese
query:              websearch_to_tsquery
match:              to_tsvector(search_text) @@ query
rank:               ts_rank_cd
ordenação:          score DESC, unit_key ASC
profundidade:       10 no DEV
```

A migration `002_v02_postgresql_fts` adiciona o índice de expressão GIN
`ix_search_units_fts_portuguese`. Toda busca exige `version_hash`, e o filtro
de ActVersion integra a própria consulta SQL. Scores são apenas valores
técnicos de ordenação, não confiança ou probabilidade jurídica.

Não há fallback lexical, busca vetorial, embeddings, RRF, reranker, LLM, RAG,
query rewriting, query expansion, sinônimos manuais ou regras específicas.

## Métricas

Hit@K é verdadeiro quando qualquer Provision esperada está ligada a uma das
primeiras K SearchUnits. MRR usa o primeiro target no máximo até rank 10.

A medição DEV completa foi executada exatamente uma vez. Artefato imutável:

```text
arquivo: evaluation/results/lei_9784_fts_baseline_v1.json
SHA-256: 86e56d80ce6ef80e075f29f3d83c5de066346afdb6363d88e66d80aea41dd367
```

| Métrica | Resultado |
|---|---:|
| Hit@1 | 0,000 |
| Hit@3 | 0,000 |
| Hit@5 | 0,000 |
| Hit@10 | 0,000 |
| MRR | 0,000 |
| latência p50 | 0,354 ms |
| latência p95 observada | 0,698 ms |

Todas as oito categorias tiveram Hit@10 e MRR iguais a zero. Todos os casos
produziram lista vazia: sob `websearch_to_tsquery`, os lexemas relevantes da
pergunta são combinados conjuntivamente, e nenhuma unidade isolada satisfez a
expressão completa.

## Hipóteses diagnósticas do baseline estrito

A classificação foi feita após o congelamento, comparando as perguntas e seus
targets oficiais, sem nova medição e sem mudança de runtime. Cada caso recebe
uma hipótese primária; a conjunção estrita é o único mecanismo de falha
demonstrado nesse resultado sem candidatos. As demais classes não foram
consideradas causas definitivamente provadas antes de remover esse bloqueio.

| Classe | Quantidade | Casos |
|---|---:|---|
| `LEXICAL_VOCABULARY_MISMATCH` | 10 | DEV-003, DEV-004, DEV-006, DEV-007, DEV-009, DEV-010, DEV-012, DEV-013, DEV-014, DEV-015 |
| `STRUCTURAL_CONTEXT_MISSING` | 5 | DEV-001, DEV-002, DEV-008, DEV-011, DEV-022 |
| `SEARCHUNIT_GRANULARITY` | 5 | DEV-026, DEV-027, DEV-028, DEV-029, DEV-030 |
| `QUERY_TOO_CONJUNCTIVE` | 20 | DEV-005, DEV-016–DEV-021, DEV-023–DEV-025, DEV-031–DEV-040 |
| `TARGET_LABEL_DEFECT` | 0 | — |
| `SOURCE_REPRESENTATION_LIMIT` | 0 | — |
| `OTHER` | 0 | — |

Nos casos de contexto estrutural, o inciso isolado não contém termos presentes
apenas em seus ancestrais. Nos casos de granularidade, a consulta descreve uma
enumeração distribuída entre CAPUT e incisos. Nos casos lexicais, pergunta e
fonte expressam o mesmo conceito com vocabulário diferente. Nos demais, o
target preserva grande parte dos termos, mas termos interrogativos ou
qualificadores adicionais tornam a consulta conjuntiva impossível para uma
única SearchUnit.

Não foi identificado target objetivamente incorreto no DEV.

## Controle positivo

Antes de implementar a variante OR, o baseline estrito foi submetido a um
controle positivo bloqueante. Foram escolhidos mecanicamente os três primeiros
`case_id` elegíveis, sem considerar ranking ou classificação anterior. Cada
query foi um trecho literal contíguo de seis palavras do `citation_text` do
target.

| Caso | Target | Query de controle | Rank | Score | Resultado |
|---|---|---|---:|---:|---|
| DEV-001 | `ARTICLE:1/PARAGRAPH:2/INCISO:III` | `autoridade - o servidor ou agente público` | 1 | 0,033333 | PASS |
| DEV-002 | `ARTICLE:3/CAPUT/INCISO:IV` | `fazer-se assistir, facultativamente, por advogado, salvo` | 1 | 0,033333 | PASS |
| DEV-003 | `ARTICLE:5/CAPUT` | `O processo administrativo pode iniciar-se de` | 1 | 0,100000 | PASS |

`POSITIVE_CONTROL: PASS_3_OF_3`. O strict é mecanicamente funcional: texto
conhecido presente na unidade produz match e score positivo. Uso efetivo do
índice GIN não integra esse gate de correção.

## Experimento RELAXED OR

### Hipótese e variável

A única variável alterada foi a semântica booleana de candidate generation:
`AND → OR`. A pergunta é normalizada exclusivamente por primitives do
PostgreSQL:

```text
to_tsvector('portuguese', question)
→ tsvector_to_array
→ lexemas unidos por OR
→ websearch_to_tsquery('portuguese', ...)
```

Pergunta sem lexemas retorna lista vazia. Permaneceram idênticos `ts_rank_cd`,
desempate por `unit_key`, top 10, filtro de ActVersion, índice GIN, dataset e
projeção. O strict continua disponível; a CLI exige seleção explícita por
`--mode`. Não houve migration nova.

O experimento completo foi executado exatamente uma vez:

```text
implementação: POSTGRESQL_FTS_RELAXED_OR
arquivo: evaluation/results/lei_9784_fts_relaxed_or_v1.json
SHA-256: 6cb07789e6e3ee259ba91ab01797d5cf2a3a0a4898581b0f34ff6cddf4944fe8
```

| Métrica | STRICT | RELAXED_OR | Delta |
|---|---:|---:|---:|
| Hit@1 | 0,000 | 0,425 | +0,425 |
| Hit@3 | 0,000 | 0,675 | +0,675 |
| Hit@5 | 0,000 | 0,725 | +0,725 |
| Hit@10 | 0,000 | 0,800 | +0,800 |
| MRR | 0,000 | 0,549 | +0,549 |
| latência p50 | 0,354 ms | 4,367 ms | +4,013 ms |
| latência p95 observada | 0,698 ms | 6,413 ms | +5,715 ms |

Por categoria, Hit@10 foi `1,000` em `COMPETENCE`, `DEADLINE` e `PARAPHRASE`;
`0,800` em `ENUMERATION`, `EXCEPTION` e `PROCEDURE`; `0,600` em `NEGATIVE`; e
`0,400` em `DIRECT_RULE`.

### Misses restantes

Os oito targets restantes possuem match lexical no universo OR, mas aparecem
entre ranks 11 e 59. Assim, a classe primária demonstrada é
`RANKING_DILUTION`, não ausência total de match:

| Caso | Rank diagnóstico do target | Score |
|---|---:|---:|
| DEV-001 | 59 | 0,100 |
| DEV-002 | 57 | 0,200 |
| DEV-004 | 19 | 0,200 |
| DEV-011 | 17 | 0,200 |
| DEV-014 | 30 | 0,200 |
| DEV-030 | 24 | 0,200 |
| DEV-031 | 11 | 0,300 |
| DEV-040 | 50 | 0,200 |

```text
RELAXED_FAILURE_CLASS_COUNTS:
  RANKING_DILUTION: 8
  LEXICAL_VOCABULARY_MISMATCH: 0
  STRUCTURAL_CONTEXT_MISSING: 0
  SEARCHUNIT_GRANULARITY: 0
  TARGET_LABEL_DEFECT: 0
  SOURCE_REPRESENTATION_LIMIT: 0
  OTHER: 0
```

Contexto estrutural ou granularidade ainda podem contribuir para scores baixos,
mas este experimento não os isolou causalmente. Não foi identificado defeito de
target.

`RELAXED_OR_ASSESSMENT: STRONG_IMPROVEMENT`.

`GENERIC_SEARCHUNIT_V1_ASSESSMENT: POSSIBLE_LIMITATION`.

A normalização OR recuperou candidate generation de forma geral, mas matches
parciais frequentes diluíram oito targets além do top 10. Nenhum tuning foi
feito após o resultado.

## Avaliação

`GENERIC_FTS_BASELINE_ASSESSMENT: INSUFFICIENT`.

O baseline estrito é insuficiente; a variante OR produz melhora forte, mas não
resolve integralmente o retrieval. Esses resultados não decidem por busca
vetorial ou qualquer arquitetura futura. Dataset e projection permaneceram
inalterados, e cada runtime foi congelado depois de sua medição.

## Experimento posterior de cobertura lexical

Após diagnóstico read-only dos oito misses, foi autorizada uma variante que
preserva os candidatos `RELAXED_OR` e ordena primeiro pela cobertura distinta
dos lexemas da pergunta, depois por `ts_rank_cd` e `unit_key`. A medição única
obteve Hit@10 `0,875` e MRR `0,661`, contra `0,800` e `0,549` do RELAXED_OR.
Três misses entraram no top 10, nenhum hit top-10 foi perdido e uma posição
regrediu de rank 5 para 6.

O diagnóstico da configuração `portuguese`, a fórmula, regressões, latência,
casos e SHA do resultado estão em
[`phase-1-lexical-coverage-ranking.md`](phase-1-lexical-coverage-ranking.md).
Esse resultado não especifica suficiência ou abstenção e ainda aguarda revisão
humana.

## Limitações e questões abertas

- O corpus contém apenas 242 SearchUnits de um ato oficial.
- O DEV é conhecido e não substitui um HOLDOUT cego.
- O baseline não mede geração de resposta, suficiência ou qualidade de LLM.
- Alternativas de representação, matching ou retrieval somente poderão ser
  avaliadas em fase posterior, após revisão humana deste baseline.
