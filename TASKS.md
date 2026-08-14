# TASKS — MVP 1

## Fase 0 — Fundação

- [ ] Criar repositório
- [ ] Criar `pyproject.toml`
- [ ] Configurar uv
- [ ] Configurar Ruff
- [ ] Criar `.env.example`
- [ ] Criar `.gitignore`
- [ ] Criar estrutura `src/`
- [ ] Criar estrutura `tests/`

## Fase 1 — Docker

- [ ] Criar Dockerfile
- [ ] Criar docker-compose.yml
- [ ] Configurar app
- [ ] Configurar PostgreSQL
- [ ] Configurar pgvector
- [ ] Configurar Ollama
- [ ] Configurar volumes
- [ ] Configurar healthcheck
- [ ] Validar build
- [ ] Validar startup

## Fase 2 — Banco

- [ ] SQLAlchemy
- [ ] Alembic
- [ ] Source
- [ ] Document
- [ ] LegalAct
- [ ] LegalVersion
- [ ] LegalElement
- [ ] Chunk
- [ ] Embedding
- [ ] LegalRelationship
- [ ] Migration inicial
- [ ] Validar migration limpa
- [ ] Validar rollback

## Fase 3 — CLI

- [ ] Comando raiz
- [ ] `db migrate`
- [ ] `db status`
- [ ] `ingest constitution`
- [ ] `ingest status`
- [ ] `document list`
- [ ] `document show`
- [ ] `search`
- [ ] `consult`
- [ ] `embedding`
- [ ] `evaluate`
- [ ] `version`

## Fase 4 — Domínio jurídico

- [ ] Tipos de elementos
- [ ] Árvore jurídica
- [ ] Identificação
- [ ] Versionamento
- [ ] Testes

## Fase 5 — Ingestão

- [ ] Confirmar URL oficial
- [ ] Adapter Planalto
- [ ] Downloader
- [ ] Timeout
- [ ] Retry
- [ ] Hash
- [ ] Raw storage
- [ ] Idempotência
- [ ] Metadados
- [ ] Testes

## Fase 6 — Parsing

- [ ] Inspecionar HTML real
- [ ] Parser
- [ ] Preâmbulo
- [ ] Títulos
- [ ] Capítulos
- [ ] Seções
- [ ] Artigos
- [ ] Parágrafos
- [ ] Incisos
- [ ] Alíneas
- [ ] ADCT
- [ ] Normalizador
- [ ] Fixtures

## Fase 7 — Indexação

- [ ] Chunking jurídico
- [ ] Full-text search
- [ ] Escolher embeddings
- [ ] Registrar ADR
- [ ] Provider de embeddings
- [ ] Persistir embeddings
- [ ] Índice vetorial
- [ ] Busca semântica
- [ ] Busca híbrida
- [ ] Reranking

## Fase 8 — RAG

- [ ] ConsultationService
- [ ] Evidence Set
- [ ] Prompt
- [ ] Provider Ollama
- [ ] Geração
- [ ] Citações
- [ ] Resposta sem evidência
- [ ] Teste ponta a ponta

## Fase 9 — Avaliação

- [ ] Dataset inicial
- [ ] 50–100 perguntas
- [ ] Classificação
- [ ] Fontes esperadas
- [ ] Recall@K
- [ ] Precision@K
- [ ] MRR
- [ ] Source Recall
- [ ] Avaliação de citações
- [ ] Fidelidade
- [ ] Alucinação
- [ ] Baseline

## Fase 10 — Aceite

- [ ] Testes
- [ ] Lint
- [ ] Benchmark
- [ ] Docker limpo
- [ ] Ingestão completa
- [ ] Consultas
- [ ] Citações
- [ ] Documentação
- [ ] ADRs
- [ ] MVP 1 concluído
