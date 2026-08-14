# Consultor Jurídico

Mecanismo de consulta jurídica baseado em legislação oficial, versionada, rastreável e com respostas fundamentadas em fontes primárias.

## MVP 1

Corpus:

- Constituição Federal de 1988;
- ADCT;
- fonte oficial do Planalto.

Interface:

- CLI;
- sem Frontend;
- sem API HTTP.

## Arquitetura

```text
Usuário
  |
  v
CLI
  |
  v
Application Services
  |
  +--> Ingestion
  +--> Legal Domain
  +--> Retrieval
  +--> LLM
  |
  +--> PostgreSQL + pgvector
  |
  +--> Ollama
```

## Stack

- Python 3.13+
- uv
- Typer
- Rich
- Pydantic Settings
- SQLAlchemy
- PostgreSQL
- pgvector
- Alembic
- httpx
- BeautifulSoup
- lxml
- pytest
- Ruff
- Ollama
- Docker Compose

## Documentação

Consulte `AGENTS.md`, `TASKS.md` e a pasta `docs/`.
