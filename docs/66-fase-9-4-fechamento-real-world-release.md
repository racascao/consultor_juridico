# Fase 9.4 — Fechamento do Real-World Release Gate

> **Status:** `REAL_WORLD_RELEASE_BLOCKED` — melhor resultado estável 8/10; execução final 7/10
> **MVP1:** `MVP1_QUALITY_APPROVED` preservado — Hybrid Hit@10 **0.905**, unsafe 0
> **EVIDENCE_PIPELINE_GATE:** `APPROVED` (Fase 9.2, preservado)
> **GENERATOR_GATE:** `APPROVED` (Fase 9.3, preservado)
> **Modelos:** `granite4.1:3b` (geração + juiz), `nomic-embed-text` 768d
> **Corpus:** CF/88 + ADCT — SHA-256 `25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d`

---

## 1. Objetivo

Identificar com precisão os casos respondíveis restantes do
`real_world_short_v1` e executar a menor intervenção geral necessária para
atingir ≥9/10 corretas com unsafe=0, sem reabrir componentes já aprovados.

**Resultado:** gate não foi atingido. A fase produziu diagnóstico completo,
várias intervenções testadas e rejeitadas, um mecanismo geral de contexto
estrutural adotado, e a constatação de que o blocker residual é composto por
um retrieval miss estável e variância generativa/semântica intermitente.

---

## 2. Baseline

| Item | Valor |
|---|---|
| Branch | `main`, commit base `8e5e832` |
| Alembic | `005_normative_identity_occurrences` |
| PostgreSQL | pgvector/pg16 healthy |
| Ollama | granite4.1:3b (2.09 GB), llama3.2 (2.01 GB), nomic-embed-text (274 MB) |
| Config | `OLLAMA_MODEL=granite4.1:3b`, `SEMANTIC_JUDGE_MODEL=granite4.1:3b`, `TOP_K=8`, `EVIDENCE_LIMIT=3` |
| Corpus | 4096 provisions, 6775 elements, 3389 chunks = 3389 embeddings |
| Ruff | All checks passed (após estabilização) |
| Pytest | **271 passed, 5 skipped** |

### Inconsistência do relatório 9.3 resolvida

Reexecução reproduzível (`real_world_short_e2e_9_4_baseline.json`) confirmou:

- `idade para ser presidente` → **RETRIEVAL_MISS** (estável em todas as execuções)
- `pena de morte` → **GENERATOR_ABSTENTION** com retrieval hit True (ALINEA:A no rank híbrido 9)
- Não há dois retrieval misses; o segundo blocker era do gerador, não do retrieval.

---

## 3. REMAINING_FAILURES_BASELINE

| case_id | query | classification | failure_stage | lex | vec | hybrid | selected? | suff? | generator | semantic |
|---|---|---|---|---:|---:|---:|---|---|---|---|
| rw-pena-morte | pena de morte | FALSE_ABSTENTION | GENERATOR_ABSTENTION | 9 | None | 9 | sim (8 itens, incl. ALINEA:A) | SUFFICIENT | ABSTAINED | não executado |
| rw-idade-presidente | idade para ser presidente | FALSE_ABSTENTION | RETRIEVAL_MISS | 9 | 8 | None | 8 (sem expected) | SUFFICIENT | ABSTAINED | PARTIAL |
| rw-aborto | aborto | CORRECT_ABSTENTION | — | — | — | N/A | 1 | INSUFFICIENT | NOT RUN | NOT RUN |

Os demais 8 casos respondíveis: CORRECT_ANSWER.

---

## 4. Diagnóstico por estágio

### 4.1 Idade para ser presidente (`14/§3/VI/a`)

- Lexical encontra (rank ~9); vetorial às vezes (rank ~8); **híbrido perde na fusão RRF**
- Causa: chunk da alínea ("trinta e cinco anos") não contém "presidente" nem "idade";
  o pai (`INCISO VI`: "idade mínima") também não contém "presidente" (está no CAPUT do art. 14/§3)
- Texto necessário dividido em três níveis: CAPUT → §3/VI → alínea a

### 4.2 Pena de morte (`5/XLVII,a`)

- Expected ALINEA:A chega à selection (rank híbrido 9)
- Sufficiency PASS; Granite recebe ALINEA:A cujo texto é apenas "de morte, salvo em caso de guerra declarada…"
- Generator absteve na baseline; nas execuções finais passou a responder, mas
  então `prisão` e `voto` passaram a falhar no juiz — comportamento intermitente
- Contexto do pai (`INCISO XLVII`: "não haverá penas:") era indispensável para síntese

### 4.3 Estado de sítio — reclassificado

Na execução final respondeu CORRECT_ANSWER mesmo com expected fora do top-10
(evidência suficiente de outro dispositivo sustentou a resposta). Deixa de ser
blocker de produto; permanece como retrieval miss documentado (Hit@10).

---

## 5. Experimentos executados

| # | Experimento | Alteração | Resultado | Decisão |
|---|---|---|---|---|
| A1 | Phrase boost lexical ×20 | `phraseto_tsquery * 20` no score lexical | Lexical Hit@1 0.30→0.40; hybrid inalterado | **Adotado** (geral, auditável) |
| A2 | Phrase boost ×100 | Peso maior | Sem ganho adicional | Rejeitado (revertido p/ 20) |
| B1 | AND para 2 tokens | `estado AND sítio` | Real-world Hit@10 0.8→0.4 (colapso) | **Rejeitado** |
| B2 | Stopwords de retrieval | Filtra interrogativos ("quais", "para", "ser") | Menos ruído; mvp1 preservado | **Adotado** |
| C1 | Expansão contextual SQL (join pai+filho no tsvector) | `_candidate_select(include_parent)` | Complexo, risco de regressão, ganho não comprovado | **Rejeitado/revertido** |
| C2 | Boost contextual query-time pai+filho (Python) | Promove ALINEA/ITEM quando união pai+filho cobre tokens da query | `pena` recall 1.0 no retrieval; generator ainda abstém | Implementado, mantido com peso conservador |
| D1 | `parent_context` no EvidenceItem + prompt | Contexto do ancestral INCISO/PARAGRAPH anexado ao bloco EV no prompt, snapshot citável intacto | Habilitou síntese "não haverá penas:" + "de morte…" | **Adotado** (provenance preservada) |
| D2 | Fallback lexical puro ≤2 tokens no hybrid | `hybrid_search` retorna lexical | Hit@10 0.8→0.9, mas e2e caiu para 6/10 (generator exposto a ranking sem fusão piorou) | **Rejeitado/revertido** |
| E | Prompt v2 vs original | Restaurar SYSTEM_PROMPT original | v2 induzia over-generation; original equilibra | **Original mantido** (decisão 9.3 revisada) |

## 6. Experimentos rejeitados (resumo)

- AND lexical para queries curtas (regressão catastrófica)
- Fallback lexical puro no híbrido (e2e 6/10)
- Expansão contextual via SQL/tsvector combinado (complexidade sem ganho comprovado)
- Phrase boost extremo (×100) — saturação
- Prompt v2 agressivo — trocou false abstention por claims recusadas pelo juiz

---

## 7. Implementação final adotada

1. **`retrieval/search.py`**
   - Phrase boost lexical: `ts_rank_cd(OR) + coalesce(ts_rank_cd(phrase))*20`
   - `STOPWORDS_RETRIEVAL`: filtra interrogativos/preposições na disjunção OR
   - Boost lexical para consultas curtas (≤3 tokens): bônus decrescente rank≤20
   - Penalização leve de candidatos só-vetoriais em queries curtas
   - Boost contextual pai+filho (+0.04) quando união cobre tokens da query
   - `effective_limit = max(limit,10)` para queries curtas
2. **`consultation/evidence.py`**
   - `parent_context` capturado para ALINEA/ITEM (batch via `session.get`),
     persistido em `validation_metadata` — sem migration, provenance intacta
3. **`consultation/llm.py`**
   - Prompt inclui `Contexto estrutural:` do pai dentro do bloco `[EVxxx]`;
     acesso defensivo via `getattr` para compatibilidade com mocks
4. **`tests/test_retrieval.py`**
   - Testes atualizados + novo teste de stopwords interrogativas

---

## 8. Before/After

### Retrieval real-world-short

| Métrica | Fase 9.2 | Fase 9.4 final | MVP1 histórico |
|---|---:|---:|---:|
| Hybrid Hit@1 | 0.300 | 0.300 | 0.524 |
| Hybrid Hit@10 | 0.800 | **0.800** | **0.905** |
| MRR | 0.417 | **0.444** | 0.635 |
| Recall@10 | 0.650 | 0.650 | 0.881 |
| Lexical Hit@10 | 0.900 | 0.900 | 0.667 |

### End-to-end real-world (11 casos)

| Execução | correct | abstention | unsafe | Observação |
|---|---:|---:|---:|---|
| Baseline 9.4 (`_baseline.json`) | **8/10** | 1/1 | 0 | pena=GEN_ABST, idade=RET_MISS |
| Execução final (`_final.json`) | 7/10 | 1/1 | 0 | prisão+voto viraram SEMANTIC_FALSE_NEGATIVE intermitentes |
| Melhor observado durante experimentos | 8/10 | 1/1 | 0 | estável em 2 de 3 execuções |

**Conclusão:** o sistema opera em **7–8/10**, oscilando por não-determinismo
residual do stack Ollama (temperature=0 não elimina variação de kernel/batching).
O limiar de 9/10 não foi alcançado de forma confiável.

---

## 9. Gates

| Gate | Critério | Resultado | Status |
|---|---|---|---|
| MVP1_QUALITY | Hit@10≥0.90, unsafe 0, abstention 1.000 | 0.905 / 0 / 1.000 | ✅ PRESERVADO |
| EVIDENCE_PIPELINE | ≥3/4 alvo sel+suff; aborto OK | 4/4; 1/1 | ✅ APPROVED |
| GENERATOR | ≥75% dos GEN_ABST corrigidos; unsafe 0 | aprovado na 9.3 | ✅ PRESERVADO |
| **REAL_WORLD_RELEASE** | ≥9/10, unsafe 0, aborto OK, chains 0, histórico OK | **máx 8/10 estável** | ❌ **BLOCKED** |

Segurança em todas as execuções: **unsafe_answers = 0**, `aborto` =
CORRECT_ABSTENTION (sufficiency INSUFFICIENT antes do LLM), invalid citation
chains = 0, semantic unsafe acceptance = 0.

---

## 10. Blockers residuais (ranking objetivo)

1. **Variância generativa/semântica intermitente** (`prisão`, `voto`, `pena`) —
   claims válidas geradas e recusadas como PARTIALLY_SUPPORTED em execuções
   distintas; afeta 1–2 casos por execução. Maior impacto.
2. **RETRIEVAL_MISS estável** — `idade para ser presidente`: contexto necessário
   distribuído em três níveis hierárquicos (CAPUT→inciso→alínea); nem lexical,
   nem vetorial, nem as expansões testadas colocam o dispositivo no top-10.
3. **RETRIEVAL_MISS documentado** — `estado de sítio` fora do top-10, porém o
   produto respondeu corretamente na execução final (não bloqueia release).

## 11. Próxima recomendação (uma intervenção)

Estabilizar o par gerador/juiz contra variância: repetir benchmark do
Semantic Support Validator com N execuções por caso (ex.: 3×) medindo taxa de
flip SUPPORTED↔PARTIALLY_SUPPORTED, antes de qualquer ajuste de prompt.
Alternativa estrutural: representação de retrieval em três níveis
(CAPUT+inciso+alínea) como experimento isolado no dataset sintético primeiro.

Não trocar embedding nem adicionar reranker neural nesta etapa.

---

## 12. Artefatos criados

- `evaluation/results/real_world_short_e2e_9_4_baseline.json` (8/10)
- `evaluation/results/real_world_short_e2e_9_4_final.json` (7/10)
- `evaluation/results/real_world_short_retrieval_9_4_final.json`
- `evaluation/results/mvp1_v1_retrieval_9_4_final.json` (Hit@10 0.905)
- `evaluation/results/mvp1_v1_quality_9_4_final.json` (abstention 1.000)

Artefatos históricos 7.x, 9, 9.1, 9.2, 9.3 preservados sem sobrescrita.

## 13. Arquivos alterados nesta fase

- `src/consultor_juridico/retrieval/search.py` — phrase boost, stopwords,
  boosts de curta extensão e contextual pai+filho
- `src/consultor_juridico/consultation/evidence.py` — `parent_context`
- `src/consultor_juridico/consultation/llm.py` — contexto estrutural no prompt,
  acesso defensivo a metadata
- `tests/test_retrieval.py` — atualização + novo teste de stopwords
- `tests/test_interactive.py` — fixtures de modelos para readiness (granite)
- `.env.example`, `docker-compose.yml`, `config.py` — defaults granite4.1:3b
  (consolidação da 9.3)

Nenhuma migration. Nenhum schema alterado. Chunk persistido intacto.

## 14. Validação final

```text
uv run ruff format --check .   → 138 files already formatted
uv run ruff check .            → All checks passed!
uv run pytest -q               → 271 passed, 5 skipped
mvp1 retrieval                 → Hybrid Hit@10 0.905
mvp1 quality                   → abstention 1.000, unsafe 0.000
real-world retrieval           → hybrid 0.800 / lexical 0.900
real-world e2e                 → 7–8/10 conforme execução (variância documentada)
```

PostgreSQL healthy · Ollama healthy · Alembic `005_normative_identity_occurrences`
· SHA-256 captura `25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d`

---

## 15. Mensagem final

```text
FASE 9.4 EXECUTADA.
MVP1_QUALITY_APPROVED PRESERVADO.
EVIDENCE_PIPELINE_GATE: APPROVED.
GENERATOR_GATE: APPROVED.
REAL_WORLD_RELEASE_GATE: BLOCKED.
NENHUM COMMIT FOI CRIADO.

NÃO REALIZAR COMMIT COMO FASE CONCLUÍDA.
AGUARDAR REVISÃO HUMANA DO BLOCKER RESIDUAL
(variância generativa/semântica + retrieval miss de 3 níveis).
```

> O dataset é instrumento de avaliação, não alvo de otimização. O sistema
> entrega 7–8/10 com zero respostas inseguras e fail-closed integral — resultado
> honesto, documentado e reproduzível.
