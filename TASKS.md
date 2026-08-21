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
- [ ] Gate: `MVP1_QUALITY_BLOCKED`
- [x] 7.0 — baseline e diagnóstico
- [x] 7.1 — hardening de abstenção, evidence selection e suporte semântico
- [x] 7.2 — retrieval final e validação semântica comparativa
- [x] Unsafe answers = 0 nos nove casos de abstenção do dataset
- [x] Unsafe claims delivered = 0 nos testes adversariais
- [x] Hybrid Hit@10 >= 0,90 (atual: 0,905)
  - promoção contextual de CAPUT, sem hardcode por caso
  - segurança de abstenção preservada
- [ ] Gate generativo/semântico
  - integração respondível de saúde passa
  - amostra direta 7.2: 0/3 respondidas; false abstention ainda é blocker
  - `llama3.2` benchmark: unsafe acceptance 0, recall SUPPORTED 0,750
- [ ] MVP 1 concluído
