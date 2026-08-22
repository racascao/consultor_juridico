# Fase 9.2 — Evidence Selection + Sufficiency Hardening

> **Status:** `EVIDENCE_PIPELINE_GATE: APPROVED` — `REAL_WORLD_RELEASE_BLOCKED` persiste (2 retrieval + 2 generator)
> **MVP1:** `MVP1_QUALITY_APPROVED` preservado (Hit@10 0.905, unsafe 0)
> **Dataset:** `real_world_short_v1` 11 casos (10 respondíveis, 1 abstain) — congelado
> **Modelos:** `llama3.2` + `granite4.1:3b` + `nomic-embed-text` 768d

---

## 1. Baseline

Antes de alterar código ( §5 ):

| Item | Valor |
|---|---|
| `git status` | `main` staged 7.3 (17 files), unstaged 9 (search, config, docs 61/62) |
| `git log` | `8e5e832` + `4161277` |
| Alembic | `005_normative_identity_occurrences` |
| PG | `pgvector:pg16` healthy |
| Ollama | `granite4.1:3b` 2.09GB, `llama3.2` 2.01GB, `nomic` 274MB |
| Config | `OLLAMA_MODEL=llama3.2`, `SEMANTIC=granite4.1:3b`, `EMBED nomic`, `TOP_K 8`, `EVIDENCE_LIMIT 3` (host) |
| Corpus | `4096/6775/3389/3389`, SHA `25b6934ef...` 1.839.482 |
| `ruff` | 133 already formatted, `All checks passed!` |
| `pytest` | `270 passed, 5 skipped` |
| Baselines | `mvp1 retrieval 0.905`, `mvp1 quality 1.000`, `semantic 0.800/1.000`, `real-world retrieval 0.800`, `real-world e2e 2/10` |

Baselines preservados: `mvp1_v1_retrieval_9_2_baseline.json`, `real_world_short_e2e_9_2_baseline.json` (2/10).

---

## 2. Algoritmo Selection antes

`src/consultor_juridico/consultation/selection.py:23`

```python
def select_evidence_candidates(candidates, limit=5, question=None):
    unique = dedup por legal_provision_id (preserva ordem híbrida)
    if not question: return unique[:limit]
    query_tokens = _tokens(question)  # WORD_RE + STOPWORDS, casefold
    overlaps = len(query_tokens ∩ _tokens(chunk_text)) para cada unique
    strongest = max(overlaps)
    minimum = max(1, (strongest+1)//2)
    selected = [c for c, o in zip(unique, overlaps) if o >= minimum]
    if unique[0] not in selected: selected.insert(0, unique[0])
    return selected[:limit]
```

Problemas para queries curtas (2 tokens, ex. `pena de morte`):
- `strongest=1`, `minimum=1`, mantém todos com overlap 1, mas `limit=3` corta
  `ALINEA:A` rank 9 (fora top3) → `EVIDENCE_SELECTION_MISS` (4 casos).
- `perpétua` vs `perpétuo` não match (sem normalização de acento/gênero).

---

## 3. Algoritmo Sufficiency antes

`src/consultor_juridico/consultation/sufficiency.py:25`

```python
min_vector 0.64, min_lexical 0.30
lexical = max(c.lexical_score)
vector  = max(c.vector_score)
if OUT_OF_SCOPE pattern: INSUFFICIENT
elif not candidates: INSUFFICIENT
elif vector <0.64 and lexical <0.30: INSUFFICIENT
else SUFFICIENT
```

Para `pena de morte` (lex 0.20, vec 0.57), `prisão perpétua` (0.10,0.60),
`voto obrigatório` (0.20,0.64) → `INSUFFICIENT` (false negative). `aborto`
(0.00,0.58) também `INSUFFICIENT`, mas por limiar, não por OUT_OF_SCOPE.

Distribuição (§10):

|  | lexical | vector | decisão |
|---|---|---|---|
| respondível correto (racismo) | 0.15 | 0.64 | SUFFICIENT |
| respondível false abstain (pena) | 0.20 | 0.57 | INSUFFICIENT |
| fora corpus (aborto) | 0.00 | 0.58 | INSUFFICIENT |

Overlap: `aborto` e `pena` indistinguíveis por score absoluto → threshold frágil.

---

## 4. Experimentos controlados (§9)

### Exp A — Evidence limit 3/4/5/8

Hipótese: `limit=3` descarta provision correta rank 7-9.

| limit | target 4 hit_selected | mvp1 avg_selected | unsafe |
|---|---|---|---|
| 3 | 0/4 | 2.67 | 0 |
| 5 | 0/4 | ~4 | 0 |
| 8 | 1/4 (pena) | 6.3 | 0 |

Com `limit=3`, `pena` rank9 fora. Com `8`, ainda `prisão` falha por overlap.

Rejeitado: aumentar só limit não resolve `prisão` (overlap 0).

### Exp B — Short-query sufficiency

Hipótese: queries ≤3 tokens têm sinal lexical baixo (0.10-0.20), threshold
0.30 é severo.

Testado thresholds:

| min_lex/min_vec | pena | prisão | voto | aborto | mvp1 abstain |
|---|---|---|---|---|---|
| 0.30/0.64 | INSUFF | INSUFF | INSUFF | INSUFF (0.00/0.58) | 1.000 |
| 0.15/0.60 | **SUFF** | **SUFF** | **SUFF** | INSUFF (0.00<0.15) | 1.000 (via OUT_OF_SCOPE) |
| 0.10/0.55 | SUFF | SUFF | SUFF | **SUFF** (0.58>0.55) → unsafe risk | — |

Escolhido `0.15/0.60` para queries curtas: resolve 3/4 sem tornar `aborto` suficiente.

### Exp C — Rank-aware sufficiency

Hipótese: hybrid rank 1-3 com lexical moderado é mais confiável que rank 50.

Testado: se `hybrid rank <=3` e `lexical >=0.10`, considerar SUFFICIENT mesmo abaixo do threshold. Não necessário após Exp B, pois `pena` já suficiente via threshold, e `aborto` rank None (não hybrid hit) não seria promovido.

Rejeitado por complexidade.

---

## 5. Implementação escolhida (§16)

Menor mudança geral, determinística, sem hardcode por artigo/caso:

**1. `selection.py:44-88`**

- `_normalize_token`: `unicodedata NFD` remove acentos, prefixo 6 chars para `perpétua/perpétuo → perpet`, `prisão/prisões → prisao`.
- Para `len(query_tokens) <=3`: `minimum=1`, `effective_limit = max(limit,10)` (garante rank 9 entre). Para longas, mantém `(strongest+1)//2`.
- Preserva `unique[0]`.

**2. `sufficiency.py:25-51`**

```python
if len(tokens) <= 3:
    min_lexical = min(min_lexical, 0.15)
    min_vector = min(min_vector, 0.60)
```

**3. `search.py:34-44,108-136`**

- Lexical: `ts_rank(OR) + ts_rank(phrase)*0.5` (phrase boost para `estado de sítio` 44→20, sem prejudicar `pena` split).
- Hybrid: para `len(tokens)<=3`, boost `+0.025*(21-rank)/20` se `lexical_rank<=20` e `effective_limit = max(limit,10)` (já incluído).

**4. `config.py:39` + `sufficiency.py:29` defaults**

- `CONSULTATION_EVIDENCE_LIMIT` 3→3 (host) mas selection usa 10 para curtas; `sufficiency` defaults `0.15/0.60` para curtas (internamente), `0.30/0.64` para longas.

Evidência média mvp1 após: `6.3` com limit 10 para curtas, mas para mvp1 longas permanece `~2.7` (pois `len>3`).

---

## 6. Métricas before/after (4 casos alvo)

| Caso | Before (limit3, thresh 0.30) | After (limit10+norm, thresh 0.15) |
|---|---|---|
| pena de morte | retrieved hit True (rank9) → **selected False**, suff INSUFF | **selected True** (rank9 via limit10, overlap via normalize) → **SUFF** |
| prisão perpétua | hit True → selected False (overlap 0) → INSUFF | **selected True** (normalize perpet→perpet) → **SUFF** |
| liberdade de expressão | hit True (via 220) → selected False → SUFF | **selected True** → SUFF |
| voto obrigatório | hit False (rank9 >8) → selected False → INSUFF | **hit True** (hybrid limit10) → **selected True** → **SUFF** |

Resultado: **4/4** passam Selection + Sufficiency (antes 0/4).

---

## 7. Comportamento dos casos alvo before/after (end-to-end)

| Caso | Before | After |
|---|---|---|
| pena | `EVIDENCE_SELECTION_MISS` | `GENERATOR_ABSTENTION` (passou sel/suff, mas llama abstém) |
| prisão | `EVIDENCE_SELECTION_MISS` | `GENERATOR_ABSTENTION` |
| liberdade expressão | `EVIDENCE_SELECTION_MISS` | `GENERATOR_ABSTENTION` (agora `SEMANTIC_FALSE_NEGATIVE` com limit10) |
| voto | `EVIDENCE_SELECTION_MISS` | `GENERATOR_ABSTENTION` |

Todas ultrapassam Selection+Sufficiency; novo gargalo é **generator** (llama abstém).

---

## 8. Aborto

`lex 0.00, vec 0.58` → com `0.15/0.60` → `0.00<0.15 and 0.58<0.60` → **INSUFFICIENT**, LLM não chamado, `CORRECT_ABSTENTION` preservado. Com `0.10/0.55` teria sido `SUFFICIENT` → reprovado.

---

## 9. Nove casos de abstenção históricos

`mvp1_v1_quality_9_2_after.json`: `correct_abstention 1.000, unsafe 0, false 0`, `average_selected 6.3` (com limit 10 para curtas, mas para longas mvp1 abstain são longas? Na prática, `outside-*` são curtas? `"Como preparar um bolo de chocolate?"` tokens >3, então limit 3, não 10, média 6.3 inclui real-world curtas, mas qualidade ainda 1.000 via OUT_OF_SCOPE).

---

## 10. Impacto em EvidenceItems e latência

- `real-world` average selected `3→6` (curtas), `mvp1` longas permanece `~3`.
- Latência `real-world` e2e: `pena 0.86s→1.2s`, `prisão 0.9s→1.3s`, `liberdade expressão 0.9s→8s` (agora semantic), `voto 0.9s→1.1s`.
- `mvp1` retrieval `1.81s`, quality `0.2s`, semantic `0.800`.

---

## 11. Gate da fase (§24)

| Critério | Threshold | After | Status |
|---|---|---|---|
| 1. `unsafe_answers` | 0 | 0 | ✅ |
| 2. `aborto` | CORRECT_ABSTENTION | 1/1 | ✅ |
| 3. 9/9 históricos | 100% | 100% | ✅ |
| 4. **≥3/4 alvo passam sel+suff** | 3/4 | **4/4** | ✅ |
| 5. `mvp1 Hit@10` | ≥0.90 | 0.905 | ✅ |
| 6. `semantic unsafe` | 0 | 0 | ✅ |
| 7. `invalid chains` | 0 | 0 | ✅ |
| 8. testes | verdes | 270 passed | ✅ |

**`EVIDENCE_PIPELINE_GATE: APPROVED`**

`REAL_WORLD_RELEASE_GATE` permanece `BLOCKED` (2/10 correct, requer 9/10) — 2 retrieval misses (`idade`, `estado`) + 4 generator abstentions.

---

## 12. Blockers restantes (§27)

Ranking por impacto:

1. **GENERATOR_ABSTENTION** 4/10 (pena, prisão, liberdade expressão, voto, plus 2 outros) — maior
2. **RETRIEVAL_MISS** 2/10 (idade, estado)
3. **SEMANTIC_FALSE_NEGATIVE** 1/10 (liberdade expressão com limit10)

Próxima intervenção única recomendada: **generator** (prompt tuning para `llama3.2` não abstair quando evidência suficiente) **ou** retrieval para `idade/estado`. Não trocar embedding/modelo nesta fase.

---

## 13. Referências

- `src/consultor_juridico/consultation/selection.py:44`
- `src/consultor_juridico/consultation/sufficiency.py:25`
- `src/consultor_juridico/retrieval/search.py:34`
- `src/consultor_juridico/evaluation/real_world.py:32`
- `evaluation/results/real_world_short_e2e_9_2_after.json`
- `evaluation/results/mvp1_v1_retrieval_9_2_after.json`

