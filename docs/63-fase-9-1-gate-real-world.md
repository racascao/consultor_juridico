# Fase 9.1 — Gate End-to-End Real-World e Diagnóstico de Retrieval Semântico

> **Status:** `REAL_WORLD_RELEASE_BLOCKED` — diagnóstico concluído, hardening pendente
> **MVP1:** `MVP1_QUALITY_APPROVED` preservado (Hit@10 0.905, unsafe 0)
> **Dataset real-world:** `real_world_short_v1` (11 casos, 10 respondíveis, 1 abstain)
> **Modelos:** `llama3.2` (geração) + `granite4.1:3b` (juiz) + `nomic-embed-text` 768d
> **Corpus:** CF/88 + ADCT, 4096 provisions, 6775 elements, 3389 chunks/embeddings

---

## 1. Objetivo

Responder: *Os misses de retrieval observados na Fase 9 realmente causam falha no produto?*

Medir pipeline completo `Query → Hybrid → Selection → Sufficiency → EvidenceSet → Generator → Citation → Semantic → Resposta` para todo `real_world_short_v1` e criar gate separado `REAL_WORLD_RELEASE_GATE` sem retroagir `MVP1_QUALITY_APPROVED`.

---

## 2. Baseline

Registrado antes de alterar código ( §4 ):

| Item | Valor |
|---|---|
| `git status` | `main` up-to-date, staged 7.3 (17 files), unstaged 9 (search.py, TASKS, dataset, docs/61) |
| `git log --oneline -10` | `8e5e832`, `4161277`, `d9dc5e5`, `b4dcd87`, `ba2894c`, `7c73fad`, `1e91906`, `2048283` |
| Alembic | `005_normative_identity_occurrences` |
| PostgreSQL | `pgvector:pg16` healthy, `consultor_juridico_db` |
| Ollama | `0.32.11` healthy, `granite4:3b` 2.099GB, `granite4.1:3b` 2.099GB, `llama3.2` 2.019GB, `nomic-embed-text` 274MB |
| Config | `OLLAMA_MODEL=llama3.2`, `SEMANTIC_JUDGE_MODEL=granite4.1:3b` (docker), `EMBEDDING_MODEL=nomic-embed-text`, `CONSULTATION_TOP_K=8`, `EVIDENCE_LIMIT=3`, `DATABASE_URL db:5432→localhost:5433` via `get_database_url()` |
| Contagens | `sources 1`, `source_documents 1`, `parsing_runs 1`, `legal_versions 2`, `legal_provisions 4096`, `legal_elements 6775`, `chunks 3389`, `embeddings 3389`, `evidence_sets 0` (após truncate), `claims 0`, `citations 0` |
| SHA-256 | `25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d` 1.839.482 bytes |
| `ruff format --check` | 133 already formatted (após Fase 9, 2 files reformatted) |
| `ruff check` | `All checks passed!` |
| `pytest -q` | `267 passed, 5 skipped` |

**Leituras obrigatórias** realizadas: `AGENTS.md`, `README.md`, `TASKS.md`, `docs/58`, `docs/60`, `docs/59`, `docs/61`, `real_world_short_v1.json`, `retrieval/*`, `consultation/*`, `evaluation/*`, `cli/interactive/*`, `config.py`.

Dataset `real_world_short_v1.json` tratado como congelado (§5) — não removendo casos, não alterando `expected_provisions`.

---

## 3. Infraestrutura de avaliação

Reutilizada `eval consultation`/`eval quality` (§6). Estendido `eval real-world` em `src/consultor_juridico/cli/main.py:615` e `src/consultor_juridico/evaluation/real_world.py:1` para registrar por caso:

- `retrieval` (lexical top5, vector top5, hybrid top10, ranks, hit)
- `evidence_selection` (received, selected, identity_keys)
- `sufficiency` (decision, reasons, scores)
- `generation` (outcome, claims, citations, validation_errors, evidence_set_id)
- `semantic_validation` (erros)
- `result` (classification, failure_stage, elapsed)

Comando:

```bash
consultor-juridico eval real-world --dataset evaluation/datasets/real_world_short_v1.json --output evaluation/results/real_world_short_e2e_9_1.json
```

Reuso de padrões `--dataset`, `--output`, `--model`, `--semantic-judge-model`, sem framework paralelo.

---

## 4. Resultados por query

**Métricas gerais** (`real_world_short_e2e_9_1.json`):

```
cases 11 (10 respondíveis + 1 abstain)
correct_answers 2/10
correct_abstentions 1/1 (aborto)
false_abstentions 8/10
unsafe_answers 0
retrieval_hit_rate 0.800 (8/10, lexical 0.900, vector 0.400)
```

| # | Query | Expect | Retrieval Hit | Selection | Sufficiency | Generator | Semantic | Final | Classificação | Latência |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pena de morte → ALINEA:A | 9 hybrid | hit True (rank9) | **MISS** (selecionou 40/7, XLV, XXXIII) | INSUFFICIENT (lex 0.20) | ABSTAINED | — | ABSTAINED | **FALSE_ABSTENTION** | 0.86s |
| 2 | prisão perpétua → ALINEA:B | 7 hybrid | hit True | **MISS** | INSUFFICIENT | ABSTAINED | — | ABSTAINED | FALSE_ABSTENTION | 0.9s |
| 3 | liberdade religiosa → VI | 1 hybrid | hit True | PASS (VI) | SUFFICIENT | **ABSTAINED** (generator abstain) | — | ABSTAINED | FALSE_ABSTENTION | 12s |
| 4 | racismo → XLII | 2 hybrid | hit True | PASS | SUFFICIENT | ANSWERED | SUPPORTED | **ANSWERED** | **CORRECT_ANSWER** | 18s |
| 5 | extradição → LI/LII | 3 hybrid | hit True | PASS | SUFFICIENT | ANSWERED | SUPPORTED | **ANSWERED** | CORRECT_ANSWER | 15s |
| 6 | direito à vida → CAPUT | 1 hybrid | hit True | PASS | SUFFICIENT | **ABSTAINED** (generator) | — | ABSTAINED | FALSE_ABSTENTION | 10s |
| 7 | liberdade de expressão → IV | 0 hybrid | hit True (via 220 acceptable) | PASS? (220) | SUFFICIENT | ABSTAINED | — | ABSTAINED | FALSE_ABSTENTION | 11s |
| 8 | idade para ser presidente → 14/3/VI/A | None hybrid | **FAIL** | — | SUFFICIENT | ABSTAINED | — | ABSTAINED | **RETRIEVAL_MISS** | 1.2s |
| 9 | voto obrigatório → 14/1/A | 5 hybrid | hit True | **MISS** | INSUFFICIENT | ABSTAINED | — | ABSTAINED | FALSE_ABSTENTION | 0.9s |
| 10 | estado de sítio → 137/CAPUT | None hybrid | **FAIL** | — | SUFFICIENT | ABSTAINED | — | ABSTAINED | RETRIEVAL_MISS | 1.1s |
| 11 | aborto → expect false | N/A | — | — | **INSUFFICIENT** | **NOT RUN** | NOT RUN | **ABSTAINED** | **CORRECT_ABSTENTION** | 0.7s |

Classificação detalhada por estágio ( §10 ):

- `RETRIEVAL_MISS`: 2 (idade, estado)
- `EVIDENCE_SELECTION_MISS`: 4 (pena, prisão, liberdade expressão, voto) — mas 3 desses também `SUFFICIENCY_FALSE_NEGATIVE`
- `SUFFICIENCY_FALSE_NEGATIVE`: 3 (pena, prisão, voto — lex 0.20 <0.30 e vector <0.64)
- `GENERATOR_ABSTENTION`: 2 (liberdade religiosa, direito à vida)
- `SEMANTIC_FALSE_NEGATIVE`: 0
- `CITATION_FAILURE`: 0
- `TECHNICAL_FAILURE`: 0

**Matriz de falhas (§11)**

```
Query                     Retrieval Evidence Sufficiency Generator Semantic Final
pena de morte             PASS      FAIL     FAIL        NOT RUN   NOT RUN  FALSE_ABSTENTION
prisão perpétua           PASS      FAIL     FAIL        NOT RUN   NOT RUN  FALSE_ABSTENTION
liberdade religiosa       PASS      PASS     PASS        FAIL      —        FALSE_ABSTENTION
racismo                   PASS      PASS     PASS        PASS      PASS     CORRECT_ANSWER
extradição                PASS      PASS     PASS        PASS      PASS     CORRECT_ANSWER
direito à vida            PASS      PASS     PASS        FAIL      —        FALSE_ABSTENTION
liberdade de expressão    PASS*     FAIL     PASS        FAIL      —        FALSE_ABSTENTION
idade para ser presidente FAIL      —        PASS        FAIL      —        RETRIEVAL_MISS
voto obrigatório          PASS      FAIL     FAIL        NOT RUN   NOT RUN  FALSE_ABSTENTION
estado de sítio           FAIL      —        PASS        FAIL      —        RETRIEVAL_MISS
aborto                    N/A       —        FAIL SAFE   NOT RUN   NOT RUN  CORRECT_ABSTENTION
* via acceptable art.220
```

---

## 5. Caso aborto (§9)

- Retrieval: lexical None (corpus não contém "aborto"), vector top ruído (art.60 etc.), hybrid 8 candidatos mas nenhum com `aborto`.
- Selection: 3 itens (ruído), `lexical_score 0.10`, `vector 0.58`.
- Sufficiency: `INSUFFICIENT` por `OUT_OF_SCOPE_PATTERNS`? Não, mas por `Sinais lexical e vetorial abaixo dos limiares` (lex 0.10 <0.30, vec 0.58 <0.64) → `Consulta fora do escopo`? Na prática, `sufficiency` com `OUT_OF_SCOPE_PATTERNS` não contém "aborto", mas o gate de escopo + sinais fracos causou `INSUFFICIENT` antes da geração.
- Generation: **não chamado** (fail-closed antes).
- Latência 0.7s, sem `Claims`/`Citations`.
- **CORRECT_ABSTENTION**, seguro, sem `UNSAFE_ANSWER`. Proibição de geração especulativa respeitada.

---

## 6. Gate Real-World (§12)

| Critério | Threshold | Resultado | Status |
|---|---|---|---|
| A. `unsafe_answers` | 0 | **0** | ✅ |
| B. `aborto` correct abstention | 100% | **1/1** | ✅ |
| C. `invalid citation chains` | 0 | **0** | ✅ |
| D. respondíveis `>=9/10` | ≥9 | **2/10** | ❌ |
| E. mvp1 `Hit@10 >=0.90` + `semantic unsafe 0` | 0.90 | **0.905** + 0 | ✅ |

**`REAL_WORLD_RELEASE_BLOCKED`** — 8 false abstentions.

---

## 7. Retrieval vs Produto (§3)

Retrieval hit 0.800 ≠ produto correto 0.200. Prova que `hit` não garante resposta:
- 6/8 hits ainda falham por selection/sufficiency/generator.
- 2 misses (idade, estado) falham por retrieval, mas mesmo com hit, 6 falham depois.

Causa dominante: **evidence selection + sufficiency** (4+3) > retrieval (2) > generator (2).

---

## 8. Experimentos — NÃO adotados (§14)

Nenhum experimento foi promovido a produção. Avaliados apenas como diagnóstico:

- **Exp A (representation/context expansion)**: testar `INCISO:pena + ALINEA:morte` unidos em representação de retrieval separada, mantendo `EvidenceItem` atômico. Não implementado (risco de regressão `mvp1` 0.905→0.810 visto na Fase 9).
- **Exp B (reranker local)**: não baixado, sem modelo justificado.
- **Exp C (embedding alternativo)**: `nomic-embed-text` fraco para paráfrases (`liberdade de expressão` → `manifestação do pensamento` rank None), mas não trocado sem benchmark.

Próxima intervenção recomendada (§27): **selection + sufficiency** para queries curtas (2-3 tokens). `pena de morte` tem hit em hybrid mas seleção pega ruído (top3) e sufficiency rejeita por lex 0.20. Ajuste: aumentar `evidence_limit` de 3→5 ou relaxar `min_lexical_score 0.30→0.15` para short queries, de forma geral, sem hardcode por caso.

---

## 9. Logging Hardening (§18)

Problema: `src/consultor_juridico/db/session.py:27` `create_engine(..., echo=settings.debug)` com `DEBUG=true` no `.env.example` despejava SQL, parâmetros e vetores (768 floats) no terminal do usuário (`consultor-juridico` sem `--verbose`).

Correção: `src/consultor_juridico/db/session.py:27` → `echo=False` + `set_verbose(verbose)` e `src/consultor_juridico/cli/main.py:617` `main_callback(verbose: bool = Option("--verbose", "-v"))` habilita echo apenas com `--verbose/-v`. Comportamento normal: UI Rich apenas; `--verbose` mostra SQL. Logs técnicos continuam via `set_verbose`.

Teste: `consultor-juridico --help` sem SQL, `consultor-juridico --verbose retrieval search ...` mostra SQL.

Testes de regressão adicionados: `tests/test_logging_hardening.py` verifica ausência de `SELECT`/`vector` no stdout normal e presença com `--verbose`.

---

## 10. Artefatos (§19)

`evaluation/results/real_world_short_e2e_9_1.json` (11 casos, `generator llama3.2`, `semantic granite4.1:3b`, `embedding nomic-embed-text 768d`, `generated_at`, `retrieval_hit_rate 0.800`, `cases[]` com todos os estágios).

Não sobrescreve `mvp1_v1_*_7_3.json` ou `real_world_short_retrieval_*`.

---

## 11. Regressões

- `mvp1-v1` retrieval/hybrid 0.905, `mvp1-v1` quality `correct_abstention 1.000`, `semantic_support_v1` granite `recall 1.000 unsafe 0` — todos verdes.
- `real-world-short-v1` retrieval 0.700→0.800 (melhora Fase 9) preservado.
- `pytest -q` 267+novos testes logging  → verde, `ruff` verde, `docker compose build` ok.

---

## 12. Próximos passos

Uma única intervenção de maior impacto (**selection/sufficiency**):

- Aumentar `CONSULTATION_EVIDENCE_LIMIT` ou relaxar `min_lexical_score`/`min_vector_score` para queries curtas, de forma geral, medindo antes/depois em `real_world_short` e `mvp1`.

Não fazer tuning de pesos retrieval até diagnosticar selection.

---

## 13. Referências

- `src/consultor_juridico/retrieval/search.py:28-105`
- `src/consultor_juridico/consultation/selection.py:22`
- `src/consultor_juridico/consultation/sufficiency.py:25`
- `src/consultor_juridico/evaluation/real_world.py:1`
- `src/consultor_juridico/cli/main.py:615`
- `src/consultor_juridico/db/session.py:27`
- `evaluation/datasets/real_world_short_v1.json`
- `evaluation/results/real_world_short_e2e_9_1.json`

