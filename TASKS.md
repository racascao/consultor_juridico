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

- [ ] Chunking jurídico
- [ ] Full-text search
- [ ] Escolha e registro do modelo de embeddings
- [ ] Persistência e índice vetorial
- [ ] Busca lexical, semântica e híbrida
- [ ] RRF e reranking

## Fase 6 — Evidence/RAG/Citation Validation

- [ ] Evidence Builder
- [ ] Evidence Validator
- [ ] Consultation Service
- [ ] Provider Ollama
- [ ] Geração fundamentada
- [ ] Claims e citations
- [ ] Citation Validator
- [ ] Resposta por insuficiência de evidência

## Fase 7 — Avaliação e aceite

- [ ] Dataset de avaliação
- [ ] Métricas de retrieval e citações
- [ ] Fidelidade e alucinação
- [ ] Benchmark e baseline
- [ ] Testes ponta a ponta
- [ ] Docker limpo
- [ ] Documentação e ADRs finais
- [ ] MVP 1 concluído
