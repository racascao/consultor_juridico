# TASKS — MVP 1

## Fase 0 — Fundação

- [x] Estrutura do repositório, `src/` e `tests/`
- [x] `pyproject.toml`, uv, Ruff e ambiente `.venv`
- [x] Configuração inicial e CLI raiz

## Fase 1 — Docker

- [x] Dockerfile e Docker Compose
- [x] PostgreSQL + pgvector
- [x] Ollama
- [x] Volumes, healthchecks e startup

## Fase 2A — Modelagem

- [x] Modelo relacional e vetorial
- [x] Cadeia de rastreabilidade jurídica
- [x] Evidence Set, Evidence Item, Claim e Citation
- [x] Suporte a múltiplos embeddings por Chunk

## Fase 2B — SQLAlchemy/Alembic

- [x] Modelos SQLAlchemy
- [x] Alembic
- [x] `001_initial_schema`
- [x] `002_schema_corrections`
- [x] Auditoria de constraints, FKs e migrations
- [x] Validação de upgrade e rollback

## Fase 3 — Ingestão e Raw Storage

- [x] URL oficial da CF/88 e ADCT
- [x] Adapter Planalto
- [x] Downloader HTTP
- [x] Timeouts, redirects, retries e backoff
- [x] SHA-256 sobre bytes canônicos
- [x] Raw storage em `BYTEA`
- [x] Idempotência por `(source_id, content_hash_sha256)`
- [x] Metadados HTTP
- [x] CLI `ingest constitution` e `ingest status`
- [x] Testes unitários
- [x] Validação de integração real com o Planalto (`200 → 304`)

## Fase 4 — Parsing estrutural

- [x] Migration `004_frozen_parsing_model` e integridade do schema de parsing
- [x] Fase 4B.1 — Decoder e DOM íntegro
- [x] Fase 4B.2 — Segmentação CF/ADCT e blocos documentais
- [x] Fase 4B.3 — Parser jurídico estrutural em memória
- [x] Fase 4B.3.1 — Auditoria estrutural pré-materialização
- [x] Fase 4B.3.2 — Correção dos blockers estruturais e revalidação
- [x] Gate reauditado: `BLOCKED_FOR_MATERIALIZATION` (`SCHEMA_MODEL_GAP`)
- [x] Fase 4B.3.3 — Modelagem de identidade normativa e redações históricas
- [x] Decisão proposta: `LegalProvision` identifica; `LegalElement` é ocorrência
- [x] Fase 4B.3.3.1 — Consistência física pré-Migration 005
- [x] `LegalElement.legal_act_id` e FKs compostas congelados
- [x] Migration 005 — `005_normative_identity_occurrences`
- [x] Fase 4B.3.4 — adaptação do parser e reauditoria
- [x] Gate 4B.4: `APPROVED_FOR_MATERIALIZATION`
- [x] Inspeção estrutural do HTML real
- [x] Parser determinístico em memória
- [x] Preâmbulo, títulos, capítulos e seções em memória
- [x] Artigos, parágrafos, incisos, alíneas e itens em memória
- [x] ADCT em árvore independente em memória
- [x] Normalização conservadora e golden fixtures
- [x] Fase 4B.4 / Fase 4C — Materialização transacional
- [x] Identidade normativa e ocorrências versionadas
- [x] Idempotência e rollback transacional validados

## Fase 5 — Indexação/Retrieval

- [x] Chunking jurídico `legal_occurrence_current_v1`
- [x] Full-text search PostgreSQL em português
- [x] Modelo local `ollama/nomic-embed-text` registrado
- [x] Persistência pgvector com 768 dimensões
- [x] Busca lexical, semântica e híbrida
- [x] RRF auditável e filtros jurídicos
- [x] CLI e avaliação básica de retrieval
- [ ] HNSW e reranking adicional após benchmark

## Fase 6 — Evidence/RAG/Citation Validation

- [x] Evidence Builder
- [x] Evidence Validator
- [x] Consultation Service
- [x] Provider Ollama
- [x] Geração fundamentada
- [x] Claims e citations
- [x] Citation Validator
- [x] Resposta por insuficiência de evidência

## Fase 7 — Avaliação e aceite

- [x] Dataset de avaliação `mvp1-v1` (30 casos)
- [x] Métricas de retrieval e citações
- [x] Avaliação inicial de fidelidade, grounding e abstenção
- [x] Benchmark e comparação lexical/vector/hybrid
- [x] Testes adversariais determinísticos
- [x] Documentação da avaliação
- [x] Gate: `MVP1_QUALITY_APPROVED` (Fase 7.3)
- [x] 7.0 — baseline e diagnóstico
- [x] 7.1 — hardening de abstenção, evidence selection e suporte semântico
- [x] 7.2 — retrieval final e validação semântica comparativa
- [x] 7.3 — benchmark de modelos locais, juiz Granite e fechamento do gate
  - `llama3.2` baseline: Hit@10 0,905, unsafe 0, recall SUPPORTED 0,750, amostra 0/3
  - Granite 4.1 3B: `granite4.1:3b` (2,1 GB, Q4_K_M) + `granite4:3b` disponível; juiz granite recall 1,000, accuracy 0,800, unsafe 0, false abstention potencial 0
  - Matriz A/B/C/D: A 0/3, B 3/3 (llama+granite), C 3/3 (granite+granite), D 1/3
  - Configuração vencedora B: `OLLAMA_MODEL=llama3.2` + `SEMANTIC_JUDGE_MODEL=granite4.1:3b`
  - Amostra de regressão 7.2 reexecutada: 3/3 respondidas, 0 unsafe
  - Consultas fora do corpus 9/9 abstidas corretamente
  - Sem prompt tuning, sem alteração de retrieval, sem migration
- [x] Unsafe answers = 0 nos nove casos de abstenção do dataset
- [x] Unsafe claims delivered = 0 nos testes adversariais
- [x] Hybrid Hit@10 >= 0,90 (atual: 0,905)
  - promoção contextual de CAPUT, sem hardcode por caso
  - segurança de abstenção preservada
- [x] Gate generativo/semântico — **APROVADO**
  - `granite4.1:3b` como juiz semântico: SUPPORTED recall 1,000, unsafe 0
  - latência juiz: média ~11,4s, p50 ~11,1s, p95 ~13,9s
  - consultation B: decisão 1,000, 3/3 respondidas, 0 unsafe, ~44s/caso
- [x] MVP 1 concluído — `MVP1_QUALITY_APPROVED`

## Fase 8 — CLI Interativa

- [x] Menu Rich em TTY / help em non-TTY (`main_callback`)
- [x] `SystemReadiness` sem efeitos colaterais (DB, Alembic, Ollama, modelos, índice)
- [x] `run_bootstrap` idempotente com `BootstrapEvent` (db, models, ingest, parse, index)
- [x] `Dockerfile` sem `ENTRYPOINT` fixo, `CMD ["consultor-juridico"]`
- [x] Telas: consulta (`run_consultation` + `hybrid_search`), pesquisa, estado, diagnóstico, sobre, sair
- [x] `Ctrl+C` / `EOFError` com saída limpa
- [x] Aliases `ingest constituicao` e `parse constituicao`
- [x] `tests/test_interactive.py` com 33 casos (readiness, bootstrap, interação, aliases)
- [x] Validação `docker compose build` / `run --rm app bash` / `consultor-juridico`
- [x] `docs/59-fase-8-cli-interativa.md`

## Fase 9 — Hardening de Release / Retrieval Real-World

- [x] Diagnóstico "pena de morte" art. 5º XLVII (lex 8, vec 181, hybrid None, selection None)
- [x] Teste de consultas curtas reais (aborto, liberdade religiosa, racismo, prisão perpétua, extradição, direito à vida, liberdade de expressão, idade presidente, voto obrigatório, estado de sítio)
- [x] Dataset adicional `real-world-short-v1` (11 casos, 10 respondíveis) criado e versionado
- [x] Medição retrieval antes: hybrid Hit@10 0,700 (lex 0,900, vec 0,400)
- [x] Correção geral `src/consultor_juridico/retrieval/search.py:34-44,88-105` — boost de frase (`phraseto_tsquery` *0.5 + `websearch_to_tsquery`) e boost lexical para consultas curtas (<=3 tokens, +0.025)
  - sem hardcode por caso/artigo, sem sinônimos manuais, sem alteração de chunking
- [x] Medição após: hybrid Hit@10 0,800 (lex 0,900, vec 0,400), Hit@1 0,100→0,300, pena de morte 0→1 (ALINEA:A)
- [x] Reexecução `mvp1-v1` — hybrid Hit@10 0,905 preservado (sem regressão), `mvp1_v1_retrieval_final_9.json`
- [x] Reexecução `semantic_support_v1` — granite recall 1,000, unsafe 0
- [x] Validação `ruff`/`pytest` (267 passed) e `docker compose build`
- [x] `docs/61-fase-9-hardening-retrieval.md`

## Fase 9.1 — Gate End-to-End Real-World e Diagnóstico de Retrieval Semântico

- [x] Baseline Fase 9.1 (git, alembic, PG, ollama, config, SHA, ruff, pytest)
- [x] Infraestrutura `eval real-world` (`src/consultor_juridico/evaluation/real_world.py`, `cli/main.py:615`)
- [x] Pipeline completo `real_world_short_v1` (11 casos): correct_answers 2/10, correct_abstentions 1/1, false 8, unsafe 0, hit 0,800
- [x] Matriz de falhas por estágio: RETRIEVAL_MISS 2, SELECTION_MISS 4, SUFFICIENCY 3, GENERATOR 2
- [x] Caso `aborto` — CORRECT_ABSTENTION, sufficiency INSUFFICIENT antes da geração, sem LLM, 0,7s
- [x] Logging hardening: `db/session.py:27` `echo=False` + `set_verbose`, `cli/main.py:617` `--verbose/-v`
- [x] Artefato `evaluation/results/real_world_short_e2e_9_1.json` (11 casos, detalhe por estágio)
- [x] Gate `REAL_WORLD_RELEASE_BLOCKED` (requer >=9/10, atual 2/10), `MVP1_QUALITY_APPROVED` preservado (0,905)
- [x] Testes `tests/test_logging_hardening.py` (3 casos) — 270 passed
- [x] Validação `ruff`/`pytest`/`docker` e `docs/62-fase-9-1-gate-real-world.md`
- [x] Próxima intervenção recomendada: selection/sufficiency para queries curtas (aumentar `EVIDENCE_LIMIT` ou relaxar thresholds)

## Fase 9.2 — Evidence Selection + Sufficiency Hardening

- [x] Baseline Fase 9.2 (git, alembic, PG, ollama, config, SHA, ruff, pytest, baselines 0.905/0.800)
- [x] Auditoria Selection (`selection.py:23`) e Sufficiency (`sufficiency.py:25`)
- [x] Experimentos limit 3/4/5/8, short-query thresholds 0.15/0.60, rank-aware
- [x] Implementação: `selection.py` normalize acentos + prefixo 6, `effective_limit 10` para ≤3 tokens; `sufficiency.py` thresholds 0.15/0.60 para ≤3 tokens; `search.py` phrase + lexical boost
- [x] Métricas 4 alvo: 0/4→4/4 passam sel+suff; `real-world` e2e 2/10→1/10 (generator ainda bloqueia), `mvp1` 0.905, `aborto` 1/1, 9/9 históricos 1.000
- [x] Gate `EVIDENCE_PIPELINE_GATE: APPROVED` (≥3/4), `REAL_WORLD_RELEASE_BLOCKED` persiste
- [x] `docs/63-fase-9-2-evidence-pipeline-hardening.md`

## Fase 9.3 — Generator Hardening e redução de False Abstention

- [x] Baseline Fase 9.3 (git, alembic, PG, ollama, `llama3.2`→`granite4.1:3b`, SHA, ruff, pytest)
- [x] Auditoria `llm.py:13` SYSTEM_PROMPT e trace 6 casos (pena, prisão, liberdade religiosa, direito vida, liberdade expressão, voto)
- [x] Experimentos: prompt v2 geral (paráfrase/síntese permitidas) e `granite4.1:3b` como generator
- [x] Prompt v2: evidências pré-selecionadas, síntese inciso+alínea permitida, abstain só sem combinação
- [x] `llama` 2/10 → `granite` **8/10** correct_answers (penal: prisão, liberdade religiosa, direito vida, liberdade expressão, voto, extradição, racismo)
- [x] `GENERATOR_GATE: APPROVED` (≥75% dos 4 alvo corrigidos, 3/4), `aborto` 1/1, 9/9 1.000, unsafe 0, `mvp1` 0.905, `REAL_WORLD_RELEASE` 8/10 ainda BLOCKED (2 retrieval: idade, pena)
- [x] Configuração adotada: `OLLAMA_MODEL=granite4.1:3b`, `SEMANTIC_JUDGE_MODEL=granite4.1:3b`, `.env.example`, `docker-compose.yml`, `config.py:30`
- [x] `docs/64-fase-9-3-generator-hardening.md`

## Fase 9.6 — Estabilidade de Evidence Attribution

- [x] Benchmark controlado com cinco execuções por caso e evidências congeladas
- [x] Saídas brutas do gerador e do juiz registradas
- [x] Variância de gerador, juiz e pipeline combinado separadas
- [x] Dois experimentos de prompt executados e avaliados
- [ ] `EVIDENCE_ATTRIBUTION_GATE: APPROVED` — permanece `BLOCKED` (9/15; voto 0/5)
- [x] Nenhuma alteração de produção, retrieval, dataset, thresholds ou schema
- [x] `docs/67-fase-9-6-evidence-attribution.md`

## Fase 9.7 — Attribution determinística pós-geração

- [x] Protótipo determinístico pós-geração implementado sem integração produtiva
- [x] Fixtures sintéticas de atribuição, composição, contexto e fail-closed
- [x] Benchmark real com cinco execuções e evidências congeladas por caso
- [ ] `DETERMINISTIC_ATTRIBUTION_GATE: APPROVED` — permanece `BLOCKED` por unsafe semântico
- [x] Nenhuma alteração de retrieval, selection, sufficiency, embeddings, juiz, thresholds, dataset ou schema
- [x] `docs/69-fase-9-7-attribution-deterministica.md`

## Fase 9.8 — Benchmark de capacidade dos modelos locais

- [x] Baseline registrado
- [x] Bloqueio operacional documentado
- [ ] Executar Granite 3B, Granite 8B e Gemma 12B
- [ ] Fechar `MODEL_CAPABILITY_GATE`

Estado: `BLOCKED` — Granite 8B+8B executado; judge rejeita voto facultativo, mas generator mantém erros e false abstention.

## Fase 9.10 — Polarity & Contradiction Guard determinístico

- [x] Guard isolado determinístico com estados `CONSISTENT`, `CONTRADICTED` e `UNRESOLVED`
- [x] Fixtures de inversão, obrigação, permissão, exceção, contexto e ambiguidade
- [x] Gate isolado: `POLARITY_GUARD_GATE: APPROVED`
- [x] Integração fail-closed após validação de citações e antes do juiz semântico
- [x] Nenhuma alteração de retrieval, modelos, schema ou datasets
- [x] `docs/71-fase-9-10-polarity-contradiction-guard.md`

## Fase 9.11 — Reavaliação End-to-End e Real-World Release Gate

- [x] Retrieval híbrido preservado: Hit@10 `0,905`
- [x] Quality/abstenção: correct abstention `100%`, unsafe `0`
- [x] Semantic Support: unsafe acceptance `0`
- [x] Regressão de polaridade executada sem inversões liberadas
- [x] Real-world executado: `6/10` respostas corretas, `4` false abstentions, `0` unsafe
- [ ] `REAL_WORLD_RELEASE_GATE: APPROVED` — permanece `BLOCKED` (mínimo 9/10)
- [x] `docs/72-fase-9-11-real-world-release-gate.md`

## Fase 9.12 — Retrieval + Evidence Selection Hardening final

- [x] Diagnóstico dos quatro blockers residuais de retrieval/seleção
- [x] Classificação curta por tokens substantivos e contexto pai em lote
- [x] Seleção determinística por cobertura, contexto e posição híbrida
- [x] Real-world Hybrid Hit@10: `0,800 → 0,900`; MVP1 Hit@10 preservado: `0,905`
- [x] Testes sintéticos para consulta curta, contexto pai, ruído, deduplicação e determinismo
- [x] `docs/73-fase-9-12-retrieval-selection-hardening.md`

## Fase 9.13 — Diagnóstico da Regressão E2E e Estabilidade do EvidenceSet

- [x] Comparação dos artefatos E2E 9.11 × 9.12
- [x] Identificação dos casos regressivos e primeiro estágio divergente
- [x] Diagnóstico de diluição/ordenação e interação com suficiência
- [ ] Repetições A/B com EvidenceSets históricos completos — inconclusivo por ausência de snapshots
- [x] `docs/74-fase-9-13-diagnostico-regressao-e2e.md`

## Fase 9.14 — EvidenceSet Snapshotting e Experimento Causal A/B

- [x] Instrumentação diagnóstica de snapshot A/B sem persistência
- [x] Snapshots dos cinco casos regressivos exportados
- [x] Repetições downstream reduzidas (3× A e 3× B nos três casos prioritários)
- [ ] Expansão para cinco repetições por caso — não necessária após rejeição uniforme pelo guard
- [x] `docs/75-fase-9-14-evidenceset-causal.md`

## Fase 9.15 — Polarity Guard False-Rejection Hardening

- [x] Diagnóstico das regras que bloquearam as 18 claims congeladas
- [x] Reconhecimento geral de sinais afirmativos normativos
- [x] Remoção de `sem` como falso indicador universal de negação
- [x] Testes positivos, inversões regressivas e casos `UNRESOLVED`
- [x] Reexecução congelada A/B
- [x] Reavaliação única `real_world_short_v1`: `2/10`, `0` unsafe
- [x] `docs/76-fase-9-15-polarity-false-rejection.md`

## Fase 9.16 — Diagnóstico de UNRESOLVED no Polarity Guard

- [x] Análise das 12 ocorrências congeladas
- [x] Separação entre exceção omitida e ausência de polaridade aplicável
- [x] Modelo de três estados mantido
- [x] Métricas MVP1/real-world verificadas
- [x] `docs/77-fase-9-16-polarity-unresolved.md`

## Fase 9.17 — Boundary Polarity → Semantic Validation

- [x] Reason codes determinísticos para `UNRESOLVED`
- [x] Roteamento restrito de `NO_POLARITY_RELATION` ao Semantic Validator
- [x] Ambiguidade de exceção mantida em fail-closed
- [x] `BOUNDARY_ROUTING_GATE: APPROVED`
- [x] `docs/78-fase-9-17-polarity-semantic-boundary.md`

## Fase 9.18 — Reavaliação Real-World pós Boundary Routing

- [x] Avaliação única `real_world_short_v1` sem tuning
- [x] Comparação 9.15 → 9.18
- [x] `4/10` respostas corretas, `1/1` abstenção correta, `0` unsafe
- [x] Release gate permanece bloqueado
- [x] `docs/79-fase-9-18-real-world-reevaluation.md`

## Fase 9.19 — Diagnóstico Focal de Generator Abstention

- [x] EvidenceSets de `racismo` e `direito à vida` congelados e classificados como materialmente suficientes
- [x] Cinco repetições P0 por caso: Generator respondeu 10/10, sem contratos inválidos
- [x] Classificação corrigida: blockers são downstream, não Generator Abstention
- [x] P1 não executado conforme protocolo
- [x] `docs/80-fase-9-19-generator-abstention.md`
