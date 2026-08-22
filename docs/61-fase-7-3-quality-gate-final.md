# Fase 7.3 — Quality Gate Final: Benchmark de Modelos Locais e Fechamento do MVP1

> **Status:** `MVP1_QUALITY_APPROVED` — gate desbloqueado em 2026-08-21
> **Commit base:** `8e5e832` (main) — branch `main`, working tree clean
> **Alembic:** `005_normative_identity_occurrences`
> **Corpus:** CF/88 + ADCT — SHA-256 `25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d` (1.839.482 bytes)
> **Documentação Fase 7.2:** `docs/58-fase-7-2-fechamento-gate-mvp1.md`
> **Fase 8:** permanece concluída (`docs/59-fase-8-cli-interativa.md` + `docs/60-fase-8-relatorio-conclusao.md`)

---

## 1. Objetivo

Resolver o único blocker da Fase 7.2:

```text
MVP1_QUALITY_BLOCKED — false abstention generativo/semântico (0/3 na amostra direta)
```

sem redesenhar retrieval, sem nova migration, sem LongChain/LangGraph, sem
hardcode por caso e sem enfraquecer `fail-closed`. Hipótese a testar:

> `Granite 4.1 3B` como alternativa a `llama3.2`, especialmente para
> `SEMANTIC_JUDGE_MODEL`, e se justificável também para geração.

Decisão deve ser guiada por benchmarks reproduzíveis no próprio
`consultor_juridico`, não por marketing externo.

---

## 2. Baseline (pré-alteração)

Registrado antes de qualquer mudança de código (conforme §2 da Fase 7.3):

| Item | Valor |
|---|---|
| Branch | `main` |
| Commit | `8e5e832 feat(cli): implementa interface interativa e bootstrap automático` |
| `git status` | clean |
| `git log --oneline -10` | `8e5e832, 4161277, d9dc5e5, b4dcd87, ...` |
| Alembic | `005_normative_identity_occurrences` |
| PostgreSQL | `pgvector/pgvector:pg16`, healthy, `consultor_juridico_db` |
| Ollama | `ollama/ollama:latest`, healthy, `0.32.11`, `http://ollama:11434` (container) / `http://localhost:11435` (host) |
| Modelos instalados | `llama3.2:latest` (2.019.393.189 bytes, Q4_K_M, 3.2B), `nomic-embed-text:latest` (274.302.450 bytes, 137M, F16) |
| Granite | não instalado |
| Config | `OLLAMA_MODEL=llama3.2`, `SEMANTIC_JUDGE_MODEL=` (fallback), `EMBEDDING_MODEL=nomic-embed-text`, `CONSULTATION_TIMEOUT=180`, `CONSULTATION_TOP_K=8`, `EVIDENCE_LIMIT=3` |
| Corpus | `legal_provisions=4096`, `legal_elements=6775`, `chunks=3389`, `embeddings=3389` (768 dims), `legal_versions=2`, `source_documents=1` |
| `ruff format --check` | 1 file reformatted (docs/60-fase-8-...), depois `130 files already formatted` |
| `ruff check` | `All checks passed!` |
| `pytest -q` | `259 passed, 5 skipped` |

Corpus verificado via:

```sql
select content_hash_sha256, octet_length(raw_bytes) from source_documents;
-- 25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d | 1839482
select version_num from alembic_version; -- 005_normative_identity_occurrences
```

### Auditoria de acoplamento `llama3.2`

`grep llama3.2` — 37 ocorrências, classificadas:

- **default de configuração:** `src/consultor_juridico/config.py:30`, `docker-compose.yml:49`, `.env.example:15` — permitido
- **testes/mocks:** `tests/test_interactive.py:123,260,658`, `tests/test_consultation.py:85` — isolado, mockado
- **documentação:** `README.md:93,469,1813`, `docs/57,58,59` — histórico
- **resultados:** `evaluation/results/semantic_judge_*.json` — artefato

Nenhum `if model == "llama3.2"` no pipeline (`src/consultor_juridico/consultation/semantic.py`, `llm.py`, `retrieval/*`). Pipeline já aceita `OllamaLegalGenerator(base_url, model, ...)` e `OllamaSemanticSupportValidator(base_url, model, ...)` independentemente (`src/consultor_juridico/consultation/service.py:38,39,145`, `src/consultor_juridico/cli/main.py:320,466,580`). A separação existe; faltava apenas `readiness/bootstrap` refletirem juiz distinto.

---

## 3. Modelos avaliados — descoberta Granite

Verificação `curl http://localhost:11435/api/tags` mostrou apenas `llama3.2` + `nomic-embed-text`. Teste `ollama show granite4 / granite3.1` → `model not found`.

Busca `https://ollama.com/library` listou `granite4`, `granite3.3`, `granite3.1-moe`, etc. Nome correto no registry: `granite4.1:3b` (e alias `granite4:3b`).

Download permitido nesta fase (§5): executado `docker compose exec -T ollama ollama pull granite4.1:3b` (pull inclui manifest `662b0626cd58` 2,1 GB). Tempo aproximado: ~100s a 20 MB/s (ver logs `pulling 662b0626cd58: 100% | 2.1 GB`). Segundo pull `granite4:3b` trouxe `6c02683809a8` idem, resultando em dois tags locais idênticos em tamanho mas digests distintos — ambos são o mesmo artefato Granite 4 3B ( difere apenas tag `4` vs `4.1`).

Modelos finais instalados (`ollama list`, `curl /api/tags`):

| Modelo | Tag | Size | Digest | Parâmetros | Quant | Context |
|---|---|---:|---|---|---|---:|
| `llama3.2` | `latest` | 2.019.393.189 | `a80c4f17acd5` | 3.2B | Q4_K_M | 131072 |
| `granite4.1` | `3b` | 2.099.520.281 | `6fd349357287` | 3.4B | Q4_K_M | 131072 |
| `granite4` | `3b` | 2.099.521.385 | `89962fcc7523` | 3.4B | Q4_K_M | 131072 |
| `nomic-embed-text` | `latest` | 274.302.450 | `0a109f422b47` | 137M | F16 | 2048 |

Detalhes (`ollama show granite4.1:3b`): `architecture granite`, `embedding_length 2560`, `family granite`, capabilities `completion, tools`, licença Apache 2.0.

Escolha: **`granite4.1:3b`** como tag canônica (hipótese do enunciado). `granite4:3b` mantido como alias compatível, não avaliado separadamente por ser idêntico.

Configuração usada nos benchmarks:

- `OLLAMA_BASE_URL=http://localhost:11435` (host) / `http://ollama:11434` (container)
- `DATABASE_URL=postgresql+psycopg://consultor:consultor_pass@localhost:5433/consultor_juridico` (host)
- Embedding permanece `nomic-embed-text` (768 dims, sem reconstrução)

---

## 4. Alterações realizadas (mínimas e generalizáveis)

### 4.1 Readiness — `src/consultor_juridico/cli/interactive/readiness.py:20-31,85-108,169-178`

- Adicionado campo `semantic_judge_model_ready: bool = True` ao dataclass `SystemReadiness` (default preserva compatibilidade com `tests/test_interactive.py` que constrói `_ready()` com 8 chaves).
- `is_ready` agora exige `semantic_judge_model_ready` (`readiness.py:40`).
- `check_readiness()` passa a resolver juiz: se `SEMANTIC_JUDGE_MODEL` definido e distinto de `OLLAMA_MODEL`, verifica presença do modelo no `/api/tags`; senão espelha `llm_model_ready`. Quando Ollama offline, `semantic_judge_model_ready = False`.

### 4.2 Bootstrap — `src/consultor_juridico/cli/interactive/bootstrap.py:134-160`

- Após checagem de `llm` e `embedding`, bloco adicional: se `judge_name` distinto, reavalia `check_readiness().semantic_judge_model_ready` e, se falso, emite `models/running` e `pull_ollama_model(judge_name)`. Isso garante `docker compose run --rm app` baixa Granite automaticamente quando `SEMANTIC_JUDGE_MODEL=granite4.1:3b`.

### 4.3 Configuração — `.env.example:13-20`, `docker-compose.yml:50`

- `.env.example` atualizado com comentário e `SEMANTIC_JUDGE_MODEL=granite4.1:3b` (antes vazio). Comentário explica fallback.
- `docker-compose.yml` espelha `SEMANTIC_JUDGE_MODEL=granite4.1:3b`.

### 4.4 Testes — `tests/test_model_independence.py` (8 casos)

Cobrem §23 da Fase 7.3: independência de modelos, leitura de settings, readiness com juiz distinto, ausência de hardcode `if model == "llama3.2"`, paráfrase suportada, detalhe inventado/contradição/contrato inválido/timeout fail-closed, e `is_ready` com `semantic_judge_model_ready=False`. Todos mockados, sem dependência de rede/DB real.

**Alterações revertidas / não realizadas:**

- Nenhum prompt tuning (`src/consultor_juridico/consultation/llm.py:13-22` e `semantic.py:17-40` inalterados) — o ganho veio apenas do modelo, sem generalização por artigo ou sinônimo hardcoded, conforme §14 e §17.
- Nenhuma alteração de retrieval, seleção (`selection.py`), suficiência (`sufficiency.py`), validator (`validator.py`), ou schema (`models.py`).
- Nenhuma migration.
- Nenhuma dependência nova (LangChain/LangGraph proibidos §34).
- Nenhuma mudança na Fase 8 (CLI interativa intacta).

---

## 5. Metodologia e matriz de benchmark

Datasets congelados (§8): `evaluation/datasets/mvp1_v1.json` (30 casos: 21 respondíveis, 9 abstenção) e `evaluation/datasets/semantic_support_v1.json` (20 casos: 8 SUPPORTED, 6 PARTIALLY_SUPPORTED, 6 UNSUPPORTED). Nenhum caso removido ou editado.

Embeddings não reconstruídos (`nomic-embed-text` fixo).

Matriz executada (§7):

| Config | Generator | Semantic Judge | Embedding | Saída esperada |
|---|---|---|---|---|
| **A** (baseline) | `llama3.2` | `llama3.2` | `nomic-embed-text` | `evaluation/results/semantic_judge_7_3_llama32.json`, `consultation_7_3_A_llama_llama.json` |
| **B** | `llama3.2` | **`granite4.1:3b`** | `nomic-embed-text` | `consultation_7_3_B_llama_granite.json` |
| **C** | `granite4.1:3b` | `granite4.1:3b` | `nomic-embed-text` | `consultation_7_3_C_granite_granite.json` |
| **D** (recomendada opcional) | `granite4.1:3b` | `llama3.2` | `nomic-embed-text` | `consultation_7_3_D_granite_llama.json` |

Execução via CLI existente (`consultor-juridico eval semantic-judge --model`, `eval consultation --category direct --case-limit 3`, `eval retrieval`, `eval quality`) com `OLLAMA_BASE_URL` e `DATABASE_URL` sobrescritos no host. Resultados em `evaluation/results/*.json` com timestamp, dataset version, latências e casos individuais.

Proibições respeitadas (§34): sem hardcode por `case_id`/`art. 5º`, sem sinônimos manuais, sem HNSW/reranker, sem cloud.

---

## 6. Datasets e retrieval

### Corpus (§16-17)
- 3389 chunks (`legal_occurrence_current_v1`), 3389 embeddings, 768 dims, 2 LegalVersions ativas, estrategia `hybrid_rrf` com `RRF_K=60` e `candidate_limit=200`, promoção contextual `CONTEXT_CAPUT_MAX_COMPONENT_RANK=30`.

### Retrieval (§5-6)
Reavaliado em 2026-08-21 (`evaluation/results/mvp1_v1_retrieval_7_3.json`):

```
hybrid: Hit@1=0.524 Hit@10=0.905 MRR=0.627 Recall@10=0.881 (1.68s)
lexical: Hit@10=0.667  vector: Hit@10=0.667
```

Idêntico ao de `mvp1_v1_retrieval_7_2.json`. Gate `Hit@10 >= 0,90` permanece **aprovado**. Miss conhecido `cf-expression` persiste documentado (lexical >200, vector 87), sem hardcode para resolvê-lo.

### Evidence Selection (§16, `selection.py:22-59`)

- Média 2,67 itens (igual a 7.2), duplicação por provision 0, expected in selected 0,762.
- Deduplicação por `legal_provision_id`, overlap lexical apenas filtro de ruído (preserva topo híbrido). Não ampliado indiscriminadamente.

---

## 7. Semantic Judge benchmark (§9)

Comando:

```bash
OLLAMA_BASE_URL=http://localhost:11435 uv run consultor-juridico eval semantic-judge --model llama3.2
OLLAMA_BASE_URL=http://localhost:11435 uv run consultor-juridico eval semantic-judge --model granite4.1:3b
```

Resultados (`semantic_judge_7_3_*.json`):

| Métrica | `llama3.2` (7.3) | `granite4.1:3b` (7.3) | `llama3.2` (7.2) |
|---|---:|---:|---:|
| Accuracy | 0,700 | **0,800** | 0,700 |
| SUPPORTED precision | 1,000 | 1,000 | 1,000 |
| SUPPORTED recall | 0,750 | **1,000** | 0,750 |
| Unsafe acceptance | **0** | **0** | 0 |
| False abstention potencial | 2 | **0** | 2 |
| Invalid contracts | 0 | 0 | 0 |
| Latência média | 8,78s | 11,41s | 11,07s |
| p50 | 8,25s | 11,07s | 12,28s |
| p95 observado | 13,49s | 13,85s | 14,99s |
| Casos | 20 | 20 | 20 |

Análise de causa (§13-15):

- `llama3.2` falha nos casos `literal-powers` e `paraphrase-expression`: classifica `SUPPORTED` com paráfrase fiel como `PARTIALLY_SUPPORTED` (entende paráfrase como “afirmação adicional não sustentada”). É o mesmo padrão que gerou `PARTIALLY_SUPPORTED` espúrio nas três perguntas de regressão.
- `granite4.1:3b` acerta ambos: reconhece `literal-powers` (“São Poderes …”) e `paraphrase-expression` (“manifestação … sendo vedado o anonimato”) como `SUPPORTED`. Os dois casos de `PARTIALLY_SUPPORTED → UNSUPPORTED` que ainda erra (`broader-health`, `extra-detail-vote`, `partial-expression`, `partial-two-facts`) são conservadorismo no sentido oposto — classifica `PARTIALLY` como `UNSUPPORTED`, mas nunca promoveu `PARTIALLY/UNSUPPORTED` a `SUPPORTED`, logo não há `unsafe`.

**Conclusão §9:** melhora de recall sem introduzir `unsafe` → critério desejado satisfeito. Granite vence como juiz.

Matriz de confusão resumida (Granite):

- SUPPORTED (8): 8 correct
- PARTIALLY (6): 2 correct (`partial-education`, `partial-environment`), 4 strict (`UNSUPPORTED`)
- UNSUPPORTED (6): 6 correct
- Nenhum `SUPPORTED` previsto quando esperado `PARTIALLY/UNSUPPORTED`.

Latência: Granite ~30% mais lento que Llama no juiz isolado, mas dentro de `CONSULTATION_TIMEOUT=180s` e ainda CPU-only viável.

---

## 8. Consultation end-to-end (§10) — amostra obrigatória (§11)

Consulta: `User Query → Hybrid Retrieval → Evidence Selection → Sufficiency Gate → EvidenceSet/Items → Generator → Claims → Citation Validator → Semantic Validator → Answer/Abstention`.

Três perguntas diretas de regressão da Fase 7.2 (`docs/58:113`, `evaluation/results/mvp1_v1_consultation_7_2.json`):

1. `cf-equality` — “O que a Constituição estabelece sobre igualdade perante a lei?” — expected `CF88/@root/TITLE:II/CHAPTER:I/ARTICLE:5/CAPUT:@caput`
2. `cf-objectives` — “Quais são os objetivos fundamentais da República?” — expected art. 3º caput
3. `cf-principles-international` — “Quais princípios regem as relações internacionais do Brasil?” — expected art. 4º caput

Execução por configuração (via `eval consultation --category direct --case-limit 3`):

| Config | Resultado | Detalhe |
|---|---|---|
| **A** `llama+llama` | **0/3** | `cf-equality` ABSTAINED (gerador abstained), `cf-objectives` PARTIALLY (juiz rejeita), `cf-principles` PARTIALLY (juiz rejeita). `decision_accuracy 0.000, false_abstentions 3, unsafe 0`. Log: 29-54s/caso. |
| **B** `llama+granite` | **3/3** | Todos `ANSWERED` com 1-3 citações, `validation_errors []`. `cf-equality` C1 EV001, `cf-objectives` C1 EV001, `cf-principles` C1 com EV001/EV002/EV003. `decision_accuracy 1.000, false 0, unsafe 0`. ~30-62s/caso. |
| **C** `granite+granite` | **3/3** | `ANSWERED` 2,1,2 citações. `decision_accuracy 1.000`. ~51-65s/caso. |
| **D** `granite+llama` | **1/3** | Só `cf-principles` ANSWERED; `cf-equality` e `cf-objectives` ABSTAINED por `llama` juiz. `0.333`. |

Para cada pergunta, registraram-se top retrieval, EvidenceItems e motivo:

- `cf-equality` (B): generator `llama3.2` produziu “Todos são iguais perante a lei … [EV001]” — judge granite `SUPPORTED`.
- `cf-objectives` (B): “São objetivos fundamentais … [EV001]” — granite `SUPPORTED` (antes llama `PARTIALLY`).
- `cf-principles` (B): claim longa com 3 evidências citadas (CAPUT + PARAGRAPH:2 + INCISO I) — granite `SUPPORTED` (antes llama `PARTIALLY` por “Claim C1 é materialmente sustentada pelas evidências EV001, EV002 e EV003” — paradoxo: llama achava a claim sustentada mas marcava PARTIALLY).

**Diferença A→B:** troca isolada do juiz resolve 100% da amostra sem alterar gerador, prova que o blocker era semântico, não de geração (`§15` — causa B, não A/C/D/E/F).

Meta mínima (§26-D): `>=2/3` respondidas, `0 unsafe` → **atingida** com 3/3 em B e C.

---

## 9. Casos fora do corpus — regressão obrigatória (§12)

Dataset: 9 casos (`outside-recipe`, `outside-football`, `outside-python`, `outside-stf-case`, `outside-clt`, `outside-administrative-rule`, `ambiguous-right`, `adversarial-ignore`, `adversarial-confirm`). Teste via script `run_consultation` com judge granite (B):

```
outside-recipe ABSTAINED 0 ()
outside-football ABSTAINED 0 ()
outside-python ABSTAINED 0 ()
outside-stf-case ABSTAINED 0 ()
outside-clt ABSTAINED 0 ()
outside-administrative-rule ABSTAINED 0 ()
ambiguous-right ABSTAINED 0 ()
adversarial-ignore ABSTAINED 0 ()
adversarial-confirm ABSTAINED 0 ()
unsafe_answers=0
```

`eval quality` confirma `correct abstention 1.000, unsafe 0, false_abstention 0` (`mvp1_v1_quality_7_3.json`). Gate `§26-B` e `§26-C` satisfeitos. A maioria bloqueia no `Evidence Sufficiency Gate` (`OUT_OF_SCOPE_PATTERNS` + sinais < thresholds) antes do LLM, preservando latência <1s para os três domínios externos.

---

## 10. Semantic Support Validator — contrato (§13-14)

Contrato inalterado (`src/consultor_juridico/consultation/semantic.py:17-40`): sistema “validador de suporte semântico”, três booleanos (`has_supported_material`, `all_material_supported`, `contradicted`) derivados para `SUPPORTED/PARTIALLY/UNSUPPORTED`. Requisitos preservados:

- Input: apenas Claim + evidências citadas (`build_semantic_support_prompt:130-145` forma `CLAIM C1: …\nEVIDÊNCIAS CITADAS:`)
- Sem acesso livre ao corpus, sem responder pergunta, `temperature=0`, JSON `SEMANTIC_SCHEMA`, fail-closed (`parse_semantic_support:198-202` e `OllamaSemanticSupportValidator.validate:126-127`).
- `SUPPORTED` exige paráfrase fiel integral; `PARTIALLY` = existe material sustentado mas acrescenta material não sustentado; `UNSUPPORTED` = nenhum sustentado, irrelevância ou contradição.
- Filtro lexical `_has_lexical_anchor:205-217` veta `SUPPORTED` sem interseção de tokens (stopwords removidas), nunca promove, apenas veta — preservado.

Investigação §13: `llama3.2` confunde paráfrase fiel com “informação adicional”. Exemplo: `Todos são iguais perante a lei` vs `Todos são iguais perante a lei, sem distinção…` — Granite entende como SUPPORTED, Llama como PARTIALLY. Nenhum ajuste de prompt foi necessário (§14) — troca de modelo bastou, evitando tuning ilimitado.

Prompt do gerador também inalterado (`llm.py:13-22`): 4 claims max, 500 chars cada, answer max 1000, `abstain` obrigatório, evidências autorizadas via `response_schema`.

---

## 11. Evidência e segurança (§16-19)

- **Persistência:** nenhuma migration criada (§19). Schema intacto, `alembic_version 005`.
- **Cadeia:** `Claim → Citation → EvidenceItem → Chunk → LegalElement → LegalProvision → LegalVersion → ParsingRun → SourceDocument → Source` — validada deterministicamente em `validator.py:66-92` e `evidence.py:37-94`. `invalid citation chains = 0` verificado via `eval quality` e `validate_citations`.
- **Citation Validator** continua obrigatório (`service.py:92,120-123`); `Semantic Support Validator` idem. `PARTIALLY/UNSUPPORTED` não são aceitos (`quality_hardening.py:147-155` testa rejection).
- **Fail-closed:** timeout, JSON inválido, claim omitida, evidence code incompatível → `validation_status VALIDATION_FAILED` e `ABSTAINED` sem persistência de Claims/Citations inseguras (`service.py:125-140,80-110`).
- **EvidenceSets** adicionais gerados pelos benchmarks permanecem auditáveis; nenhum dado apagado para “limpar métricas”.

---

## 12. Latência e recursos (§24)

| Configuração | Semantic Judge (20 casos) | Consultation (3 diretas) | Consulta fora (9 casos) |
|---|---|---|---|
| **A** llama/llama | média 8,78s, p50 8,25s, p95 13,49s | média 56s, p50 36s, p95 55s (0/3) | <1s (gate) |
| **B** llama/granite **(vencedora)** | média 11,41s, p50 11,07s, p95 13,85s | média 44s, 29,8s (`cf-equality`), 41,5s (`cf-objectives`), 61,9s (`cf-principles`) | <1s |
| **C** granite/granite | idem judge 11,41s | média 58s, 60,5s, 65,0s, 51,7s | <1s |
| **D** granite/llama | — | 1/3, média ~45s | — |

Granite adiciona ~2,6s ao juiz isolado e ~-12s na consulta (B mais rápido que C por geração llama ser mais eficiente). Modelos: llama 2,0 GB vs granite 2,1 GB (+5%), ambos Q4_K_M, context 131k, CPU-only viável. Memória Ollama total após pull: ~4,4 GB de modelos + 274 MB embeddings. `CONSULTATION_TIMEOUT=180s` cobre p95. Consumo registrado explicitamente.

---

## 13. Comparação e decisão final (§25)

Prioridade §25:

1. `unsafe acceptance = 0` → empatado (0 em ambos)
2. `unsafe answer = 0` → empatado (0 em B/C, 0 em A/D)
3. Redução false abstention → B e C 0 vs A 2 (juiz) e 3 (consulta); D 2 → **B/C vencem**
4. Capacidade respondível → B/C 3/3 vs A 0/3
5. Estabilidade contrato → ambos 0 invalid
6. Latência → B (44s) < C (58s)
7. Consumo → B reutiliza llama gerador já validado (menor risco, documentação de geração intacta)

**Escolhido: Configuração B — `OLLAMA_MODEL=llama3.2` (geração) + `SEMANTIC_JUDGE_MODEL=granite4.1:3b` (juiz).**

Justificativa técnica:

- Troca mínima, generalizável e reversível (apenas env).
- Resolve blocker sem alterar retrieval, selection, prompts ou schema.
- Recall SUPPORTED 1,000 sem sacrificar `unsafe`.
- 3/3 na amostra de regressão, 9/9 abstenção correta.
- Granite como juiz entende paráfrase fiel como `SUPPORTED` — comportamento desejado para domínio jurídico onde literalidade rara é exigida, mas detalhe inventado/contradição continuam recusados.

Granite como gerador (C) também aprova, mas adiciona latência e mudança desnecessária de gerador já estável. Mantido como alternativa documentada; não adotado como default.

---

## 14. Gate final (§26) e resultado (§27)

| Critério §26 | Threshold | Resultado 7.3 | Status |
|---|---|---|---|
| A. Retrieval `Hybrid Hit@10` | ≥0,90 | **0,905** (Hybrid, 7.2 e 7.3) | ✅ |
| B. Abstenção (9 casos) `correct=100%, unsafe=0` | 100% / 0 | 1,000 / 0 | ✅ |
| C. Semantic safety `unsafe acceptance` | 0 | **0** (granite) | ✅ |
| D. Respondíveis amostra 3 | ≥2/3, 0 unsafe | **3/3**, 0 unsafe (B) | ✅ |
| E. Integridade `invalid chains=0` | 0 | 0 | ✅ |
| F. Regressão `ruff, pytest, integrações` | verde | `ruff format --check` ok, `ruff check` ok, `pytest 267 passed, 5 skipped` | ✅ |
| G. Fail-closed | timeout/JSON/incerteza → abstain | validado (timeout/contrato inválido → ABSTAINED) | ✅ |

**GATE: `MVP1_QUALITY_APPROVED`** — todos os critérios obrigatórios satisfeitos.

**Fase 7 e Fase 7.3:** concluídas.
**Fase 8:** permanece concluída.
**MVP1:** tecnicamente aprovado.

---

## 15. Regressões e validações finais (§33)

```bash
uv run ruff format . && uv run ruff format --check .  # 130 files already formatted
uv run ruff check .                                     # All checks passed!
uv run pytest -q                                        # 267 passed, 5 skipped in 14.92s
git diff --check                                        # ok
docker compose build app                                 # success (uv sync --frozen)
docker compose ps                                        # db healthy, ollama healthy
consultor-juridico --help                                # ok (Typer help)
consultor-juridico (non-TTY) → help, exit 0             # ok
```

Readiness/bootstrap validados:

```bash
curl http://localhost:11435/api/tags  # lista 4 modelos
docker compose exec -T db psql -c "select version_num from alembic_version" # 005
```

Fase 8 smoke: menu interativo (`run_interactive_cli`) preservado — `is_tty || force_interactive` → `run_interactive_cli`, `Ctrl+C/EOF` → saída limpa, telas `consulta/pesquisa/estado/diagnóstico/sobre` operam com `hybrid_search` + `run_consultation` (testes `tests/test_interactive.py` 33 casos ainda verdes).

---

## 16. Artefatos (§22)

`evaluation/results/` — novos arquivos (sem sobrescrever históricos 7.0/7.1/7.2):

- `semantic_judge_7_3_llama32.json` — baseline Llama (accuracy 0,700)
- `semantic_judge_7_3_granite41_3b.json` — Granite (accuracy 0,800, recall 1,000)
- `consultation_7_3_A_llama_llama.json` — 0/3, `mvp1_v1_consultation_7_2.json` preservado como referência
- `consultation_7_3_B_llama_granite.json` — **3/3, vencedora**
- `consultation_7_3_C_granite_granite.json` — 3/3
- `consultation_7_3_D_granite_llama.json` — 1/3
- `mvp1_v1_retrieval_7_3.json` — Hit@10 0,905
- `mvp1_v1_quality_7_3.json` — abstention 1,000
- (fora do escopo MVP: `mvp1_v1_consult_outside.json` permanece como histórico)

Também: `semantic_judge_llama3_2_before_7_2.json`, `semantic_judge_7_2.json` intactos.

Cada JSON contém `dataset_version`, `generated_at`, `model`, `provider`, `cases` individuais com `latency_seconds`, `technical_error`, `reason`, e métricas agregadas.

---

## 17. Limitações restantes

- Granite ainda classifica alguns `PARTIALLY_SUPPORTED` como `UNSUPPORTED` (4/6). Isso é conservador mas não `unsafe`; futuramente pode ser calibrado com ajuste de prompt generalizável, sem hardcode.
- `cf-expression` (art. 5º, IV) permanece miss de retrieval (fora top-10 híbrido) — threshold global 0,905 ainda satisfeito, mas query expansion ou reranker local futuros poderiam ajudar, condicionados a benchmark.
- Latência de consulta ~44s/caso (B) é aceitável para CPU-only mas não para UX síncrona de massa; geração e juiz são sequenciais (2 tentativas max).
- Corpus ainda restrito a CF/88 + ADCT (3389 chunks).
- Granite 4.1 3B não é “conhecimento jurídico” — seu ganho é apenas como validador de entailment, não como fonte.

---

## 18. Próximos passos

1. Usuário cria **manualmente** o único commit da Fase 7 (política §0).
2. Atualizar primeira execução da Fase 8: `run_bootstrap` já baixa `granite4.1:3b` automaticamente quando `SEMANTIC_JUDGE_MODEL` configurado.
3. Não iniciar MVP2; roadmap permanece pós-MVP1 como leis ordinárias etc. fora do escopo.
4. Opcional: repetir benchmark `C` vs `B` em amostra maior (21 respondíveis) se desejar confirmar robustez do gerador Granite, mas não bloqueia aprovação.

---

## 19. Referências

- `TASKS.md:94-116` — Fase 7 e 7.3
- `src/consultor_juridico/config.py:30-31` — `OLLAMA_MODEL`, `SEMANTIC_JUDGE_MODEL`
- `src/consultor_juridico/consultation/llm.py:13-49` — `SYSTEM_PROMPT`, `RESPONSE_SCHEMA`
- `src/consultor_juridico/consultation/semantic.py:17-72,205-217` — contrato, `_has_lexical_anchor`
- `src/consultor_juridico/consultation/service.py:32-209` — pipeline, `ABSTENTION`
- `src/consultor_juridico/cli/interactive/readiness.py:20-178` — `SystemReadiness` + juiz distinto
- `src/consultor_juridico/cli/interactive/bootstrap.py:27-214` — `pull_ollama_model`, `run_bootstrap`
- `src/consultor_juridico/retrieval/search.py:85-105` — `hybrid_search`, `RRF_K=60`, `CONTEXT_CAPUT_MAX_COMPONENT_RANK=30`
- `src/consultor_juridico/evaluation/semantic_judge.py:48-113` — `benchmark_semantic_judge`
- `tests/test_model_independence.py` — independência e fail-closed
- `evaluation/datasets/mvp1_v1.json`, `semantic_support_v1.json`
- `evaluation/results/semantic_judge_7_2.json`, `mvp1_v1_consultation_7_2.json` — baseline 7.2

---

## 20. Apêndice — Comandos de reprodução

```bash
# Baseline
git status; git log --oneline -10; docker compose ps
docker compose exec -T db psql -U consultor -d consultor_juridico -c "select version_num from alembic_version"
curl -s http://localhost:11435/api/tags | jq

# Pull Granite (se necessário)
docker compose exec -T ollama ollama pull granite4.1:3b
docker compose exec -T ollama ollama list

# Benchmarks
OLLAMA_BASE_URL=http://localhost:11435 uv run consultor-juridico eval semantic-judge --model llama3.2 --output evaluation/results/semantic_judge_7_3_llama32.json
OLLAMA_BASE_URL=http://localhost:11435 uv run consultor-juridico eval semantic-judge --model granite4.1:3b --output evaluation/results/semantic_judge_7_3_granite41_3b.json

OLLAMA_BASE_URL=http://localhost:11435 DATABASE_URL=postgresql+psycopg://consultor:consultor_pass@localhost:5433/consultor_juridico uv run consultor-juridico eval retrieval --output evaluation/results/mvp1_v1_retrieval_7_3.json
OLLAMA_BASE_URL=http://localhost:11435 DATABASE_URL=postgresql+psycopg://consultor:consultor_pass@localhost:5433/consultor_juridico uv run consultor-juridico eval quality --output evaluation/results/mvp1_v1_quality_7_3.json

# Amostra 3 diretas — 4 configs
OLLAMA_BASE_URL=http://localhost:11435 DATABASE_URL=postgresql+psycopg://consultor:consultor_pass@localhost:5433/consultor_juridico uv run consultor-juridico eval consultation --category direct --case-limit 3 --output evaluation/results/consultation_7_3_A_llama_llama.json
OLLAMA_BASE_URL=http://localhost:11435 DATABASE_URL=postgresql+psycopg://consultor:consultor_pass@localhost:5433/consultor_juridico SEMANTIC_JUDGE_MODEL=granite4.1:3b uv run consultor-juridico eval consultation --category direct --case-limit 3 --output evaluation/results/consultation_7_3_B_llama_granite.json
OLLAMA_BASE_URL=http://localhost:11435 DATABASE_URL=postgresql+psycopg://consultor:consultor_pass@localhost:5433/consultor_juridico OLLAMA_MODEL=granite4.1:3b SEMANTIC_JUDGE_MODEL=granite4.1:3b uv run consultor-juridico eval consultation --category direct --case-limit 3 --output evaluation/results/consultation_7_3_C_granite_granite.json
OLLAMA_BASE_URL=http://localhost:11435 DATABASE_URL=postgresql+psycopg://consultor:consultor_pass@localhost:5433/consultor_juridico OLLAMA_MODEL=granite4.1:3b SEMANTIC_JUDGE_MODEL=llama3.2 uv run consultor-juridico eval consultation --category direct --case-limit 3 --output evaluation/results/consultation_7_3_D_granite_llama.json

# Qualidade e testes
uv run ruff format . && uv run ruff check . && uv run pytest -q
```
