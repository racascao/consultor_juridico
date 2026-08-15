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

- [ ] Inspeção estrutural do HTML real
- [ ] Parser determinístico
- [ ] Preâmbulo, títulos, capítulos e seções
- [ ] Artigos, parágrafos, incisos, alíneas e itens
- [ ] ADCT
- [ ] Normalização e fixtures
- [ ] Versionamento jurídico

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
