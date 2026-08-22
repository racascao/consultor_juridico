# Fase 9 — Hardening de Release / Retrieval Real-World

> **Status:** Em hardening — sem regressão no `mvp1-v1`, melhora em `real-world-short-v1`
> **Datasets:** `mvp1-v1` (30 casos, congelado), `real-world-short-v1` (11 casos, novo)
> **Branch:** `main` — sobre `8e5e832` + Fase 7.3 (`MVP1_QUALITY_APPROVED`)

---

## 1. Objetivo

Fase de hardening, não de expansão funcional. Adicionar diagnóstico "pena de morte"
sem alterar imediatamente o dataset congelado da Fase 7, descobrir onde falha o
art. 5º XLVII em consultas curtas reais, medir retrieval em queries de produção
(`aborto`, `liberdade religiosa`, `racismo`, `prisão perpétua`, `extradição`,
`direito à vida`, `liberdade de expressão`, `idade para ser presidente`,
`voto obrigatório`, `estado de sítio`), criar dataset adicional, corrigir a
estratégia geral de forma reproduzível e reexecutar os datasets antigos para
impedir regressão.

---

## 2. Baseline e método

Corpus: CF/88 + ADCT, `legal_provisions 4096`, `legal_elements 6775`,
`chunks 3389`, `embeddings 3389`, `768 dims`, `nomic-embed-text`,
`SHA-256 25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d`,
`Alembic 005`.

Retrieval baseline (antes da Fase 9, código Fase 7.3):

```
mvp1-v1 hybrid: Hit@10 0.905, Hit@1 0.524, MRR 0.627, Recall 0.881
real-world-short-v1 (11 casos, 10 respondíveis) hybrid: Hit@10 0.700, Hit@1 0.100, MRR 0.252
```

Datasets lidos antes de alterar código: `mvp1_v1.json`, `semantic_support_v1.json`,
`real_world_short_v1.json` (novo, ver §5).

---

## 3. Diagnóstico "pena de morte" — art. 5º XLVII

Identidade esperada correta: `CF88/@root/TITLE:II/CHAPTER:I/ARTICLE:5/INCISO:XLVII/ALINEA:A`
(`de morte, salvo em caso de guerra declarada...`), cujo pai é
`INCISO:XLVII` (`não haverá penas:`). O chunking `legal_occurrence_current_v1`
(`src/consultor_juridico/retrieval/chunking.py:35`) cria um chunk por ocorrência,
logo "pena" está no inciso e "morte" na alínea — nenhum chunk contém ambos.

Medição com `src/consultor_juridico/retrieval/search.py:28,55,85` (OR lexical,
RRF K=60, contextual CAPUT):

| Query | Lexical | Vector | Hybrid (limit 10) | Selection (limit 3) | Chunk relevante |
|---|---|---|---|---|---|
| `pena de morte` → XLVII | lex 8 (0.1) `INCISO:XLVII` | vec 181 | **None** (fora top10) | None | `INCISO:XLVII` = `não haverá penas:`<br>`ALINEA:A` = `de morte, salvo...` |
| `pena de morte` → ALINEA:A | lex 9 (0.1) | vec 181 | rank 16 (fora top10) | None | — |

Lexical encontra ambos em top10 (OR), mas com score 0.1 empatado com
`art.40/PARAGRAPH:7` (`pensão por morte`, score 0.2, duas ocorrências de morte) e
`art.144/PARAGRAPH:5-A` (`polícias penais`), que outrankeiam. Vector com
`search_query: pena de morte` → distância cosseno rank 181 (ruído). RRF
`1/(60+8)+1/(60+181)=0.018` perde para `art.40` com `lex2+vec3=0.032`. Seleção
(limit 3) mantém ruído.

Diagnóstico via `uv run python /tmp/diag_batch.py` e
`evaluation/results/real_world_short_retrieval_before.json` confirma Hit@10 0.700.

Outras queries curtas (mesmo método):

| Query | Lex | Vec | Hybrid | Obs |
|---|---|---|---|---|
| `aborto` | None (0 hits, corpus não menciona) | vec 100 (ruído) | None | Fora do corpus → deve abstain (expect_answer false) |
| `liberdade religiosa` → VI | 1 | 1 | **1** | OK |
| `racismo` → XLII | 2 | 2 | 2 | OK (top1 é art4 VIII, mas XLII em 2) |
| `prisão perpétua` → ALINEA:B | 1 | None | 7 (hit) | Lexical hit, hybrid 7 ainda hit |
| `extradição` → LI/LII | 1 | 4 | 3 | OK |
| `direito à vida` → CAPUT | 3 | 1 | 1 | OK (lexical OR, mas hit) |
| `liberdade de expressão` → IV | None | None | None | Miss conhecido (paráfrase "manifestação do pensamento") |
| `idade para ser presidente` → 14/3/VI/A | 9 | 8 | None | Lexical 9, vector 8, mas hybrid None (RRF perde) |
| `voto obrigatório` → 14/1/A | 11 | 20 | 5 | Hit |
| `estado de sítio` → 137/CAPUT | 44 | None | None | Lexical 44, phrase "estado de sítio" deveria boostar |

Padrão: consultas curtas com 2-3 tokens significativos sofrem quando vector é
ruidoso (rank >100) ou lexical tem muitos empates (OR amplo). Hybrid com RRF
puro penaliza lexical bom quando vector é ruim.

O dataset congelado **não foi alterado** nesta etapa (§2 da Fase 9).

---

## 4. Dataset adicional — `real-world-short-v1`

Criado `evaluation/datasets/real_world_short_v1.json:1` (11 casos, 10
respondíveis + 1 abstain). Cada caso com `expected_provisions` e, quando
pertinente, `acceptable_provisions` (ex.: pena de morte aceita tanto
`ALINEA:A` quanto `INCISO:XLVII` para Hit, mas Recall mede só o principal).

Casos:

- `rw-pena-morte` → `XLVII/ALINEA:A` (acceptable XLVII)
- `rw-prisao-perpetua` → `XLVII/ALINEA:B`
- `rw-liberdade-religiosa` → `VI`
- `rw-racismo` → `XLII`
- `rw-extradicao` → `LI`/`LII`
- `rw-direito-vida` → `5/CAPUT`
- `rw-liberdade-expressao` → `IV` (acceptable IX, 220)
- `rw-idade-presidente` → `14/3/VI/A`
- `rw-voto-obrigatorio` → `14/1/A` + `14/CAPUT`
- `rw-estado-sitio` → `137/CAPUT` (acceptable 138)
- `rw-aborto` → `expect_answer false` (fora do corpus)

Medição antes da correção (`real_world_short_retrieval_before.json`):

```
lexical: Hit@10 0.900, vector 0.400, hybrid 0.700
```

Misses híbridos: `pena de morte`, `liberdade de expressão`, `estado de sítio`
(e `idade` no limite).

---

## 5. Correção geral — sem hardcode por caso

Duas mudanças em `src/consultor_juridico/retrieval/search.py:28-105`
(generalizáveis, auditáveis, sem menção a art. 5º ou caso):

### 5.1 Lexical com boost de frase

Antes:

```python
tsquery = websearch_to_tsquery("portuguese", lexical_query_text(query))  # OR
score = ts_rank_cd(tsv, tsquery)
```

Depois (`search.py:34-44`):

```python
tsquery = websearch_to_tsquery("portuguese", lexical_query_text(query))
phrase_q = phraseto_tsquery("portuguese", query)
score = ts_rank_cd(tsv, tsquery) + coalesce(ts_rank_cd(tsv, phrase_q),0)*0.5
where = tsv @@ tsquery  # recall por OR, ordenação por score combinado
```

Efeito: `estado de sítio` (frase exata em `137/CAPUT`) ganha +0.5*phrase_score,
subindo de rank 44 → 20 (ainda fora top10, mas melhor). `pena de morte`
(phrase sem chunk com ambos) não é prejudicado (phrase_score 0).

### 5.2 Hybrid com boost lexical para consultas curtas

Antes: RRF puro `1/(60+rank)` sum.

Depois (`search.py:88-105`):

```python
tokens = WORD_RE.findall(query.casefold())  # {3,}
if len(tokens) <= 3 and fused:
    for item in fused:
        base = rrf_score
        if lexical_rank and lexical_rank <= 20:
            bonus = 0.025 * (21 - lexical_rank) / 20  # rank1 +0.025, rank10 +0.012
            base += bonus
    fused = sorted(boosted)
```

Para `pena de morte` (2 tokens): `ALINEA:A` lex 9 → +0.015, RRF 0.0147→0.0297,
ultrapassa ruído `art.40` (lex2+vec3=0.032 → +0.022=0.054? Na prática, ruído também
ganha bonus, mas `ALINEA:A` passa de rank16 → 3, entrando no top10). Para
consultas longas (>3 tokens, como mvp1 "O que a Constituição estabelece sobre..."),
nenhum boost, preserva RRF clássico.

Ambas as mudanças são **gerais**: não citam `pena`, `XLVII`, `estado`,
`aborto` ou qualquer `case_id`.

Chunking (`chunking.py:35`) mantido como `legal_occurrence_current_v1`;
não foi alterado para incluir pai, pois causou regressão em `mvp1` (Hit@10
0.905→0.810 em `mvp1_v1_retrieval_after_chunkfix.json` — casos
`cf-amendment` e `false-anonymity`).

Reindexação **não necessária** (mudança só em `search.py`, não em `Chunk`).

---

## 6. Medição após correção

```
real-world-short-v1 hybrid: Hit@10 0.800, Hit@1 0.300, MRR 0.405, Recall 0.650
  lexical: Hit@10 0.900, vector 0.400
  antes: hybrid 0.700 → depois 0.800 (+14%)
  correções: pena de morte 0→1, liberdade de expressão 0→1 (via acceptable 220),
             estado de sítio ainda 0, idade presidente 1→0 (troca)
```

Detalhe `real_world_short_v1_retrieval_final.json`:

- `rw-pena-morte` **1.0** (ALINEA:A rank3, antes 0)
- `rw-idade-presidente` 0.0 (antes 1.0) — trocou, saldo +0 ainda 0.8
- `rw-liberdade-expressao` 0→1 (via `220/CAPUT` aceitável)
- `estado de sítio` permanece 0 (lex 20, ainda fora top10)

Saldo líquido +1 hit.

**mvp1-v1** reexecutado (`mvp1_v1_retrieval_final_9.json`):

```
hybrid: Hit@1 0.524, Hit@3 0.714, Hit@5 0.810, Hit@10 0.905, MRR 0.627, Recall 0.881
lexical 0.667, vector 0.667
```

Idêntico ao baseline `mvp1_v1_retrieval_7_3.json` — **sem regressão**.

---

## 7. Reexecução dos datasets antigos

```bash
OLLAMA_BASE_URL=http://localhost:11435 DATABASE_URL=postgresql+psycopg://consultor:consultor_pass@localhost:5433/consultor_juridico \
  uv run consultor-juridico eval retrieval --dataset evaluation/datasets/mvp1_v1.json
# hybrid Hit@10 0.905

uv run consultor-juridico eval quality --dataset evaluation/datasets/mvp1_v1.json
# correct_abstention 1.000, unsafe 0, false_abstention 0

uv run consultor-juridico eval semantic-judge --model granite4.1:3b
# accuracy 0.800, recall 1.000, unsafe 0 (inalterado)
```

Consultation com `llama3.2` + `granite4.1:3b` nas 3 diretas ainda 3/3.

---

## 8. Validação

```bash
uv run ruff format --check .  # 132 files already formatted
uv run ruff check .           # All checks passed!
uv run pytest -q              # 267 passed, 5 skipped (inclui test_model_independence)
docker compose build app       # Image consultor_juridico-app Built
docker compose ps             # db healthy, ollama healthy
docker compose run --rm app consultor-juridico --help  # ok
```

---

## 9. Referências

- `src/consultor_juridico/retrieval/search.py:28-105`
- `src/consultor_juridico/retrieval/chunking.py:35`
- `evaluation/datasets/real_world_short_v1.json:1`
- `evaluation/results/real_world_short_retrieval_before.json`
- `evaluation/results/real_world_short_v1_retrieval_final.json`
- `evaluation/results/mvp1_v1_retrieval_final_9.json` (0.905)
- `docs/58-fase-7-2-fechamento-gate-mvp1.md`, `docs/60-fase-7-3-quality-gate-final.md`

---

## 10. Limitações e próximos passos

- `liberdade de expressão` ainda depende de acceptable (220) e não de IV;
  embedding `nomic-embed-text` para paráfrase "manifestação do pensamento"
  continua rank None — futuro reranker local ou embedding melhor pode resolver,
  sem hardcode de sinônimo.
- `estado de sítio` lexical 20, ainda fora top10; boost de frase ajudou
  (44→20) mas não suficiente — próximo passo pode ser `phraseto_tsquery`
  com peso maior ou índice GIN trigram, condicionado a benchmark.
- `aborto` corretamente sem provision (expect_answer false) — retrieval não
  deve inventar; sufficiency gate já abstém.
- Próximo hardening: testar `aborto`, `racismo` etc. em pipeline completo
  (selection + sufficiency + generation) para garantir que `aborto` continua
  abstendo e `racismo` responde com `XLII`.

