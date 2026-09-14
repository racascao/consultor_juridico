# Experimentos de retrieval

| Problema | Hipótese | Resultado | Decisão |
|---|---|---|---|
| FTS estrito falhava em linguagem natural | relaxed OR | Hit@10 0,800 | manter OR |
| relevantes diluídos | cobertura lexical | Hit@10 0,875; MRR 0,661 | integrar |
| frequência distorcia ranking | peso por raridade | DEV Hit@10 0,900 | integrar |
| regra dividida em pai/filhos | expansão estrutural | HOLDOUT 26/44 → 40/44 | integrar 8/24 |
| misses heterogêneos | vector/RRF geral | regressões | rejeitar |

O runtime final é
`POSTGRESQL_FTS_RELAXED_OR_WEIGHTED_COVERAGE`: OR produz candidatos; cobertura
ponderada pela raridade dos lexemas, cobertura simples, `ts_rank_cd` e
`unit_key` ordenam deterministicamente.

Embeddings, vetor e equal-weight RRF aumentaram complexidade e variabilidade
sem ganho geral estável. Reconsiderá-los exige novo corpus e DEV independente
que demonstre uma falha lexical sistemática.

A expansão por filhos diretos resolveu um problema diferente: uma regra
recuperada como pai frequentemente precisa dos seus incisos. Ela não altera o
ranking e preserva `stable_key`, locator e ordem documental.
