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

## Setup & Isolamento de Ambiente (.venv)

> [!IMPORTANT]
> **Invariante:** O `uv` é a ferramenta de gerenciamento do projeto. Ele gerencia o arquivo `pyproject.toml`, gera o `uv.lock` e instala as dependências no ambiente virtual `.venv` na raiz do projeto. Nenhuma dependência Python é instalada globalmente no sistema operacional do desenvolvedor.

Fluxo conceitual do ambiente:

```text
uv (gerenciador de projeto)
  │
  ▼
pyproject.toml + uv.lock
  │
  ▼
.venv/ (ambiente virtual local do projeto)
  │
  ▼
Dependências isoladas do projeto (Typer, Rich, SQLAlchemy, pytest, ruff, etc.)
```

### 1. Criar e Sincronizar o Ambiente do Projeto

Para configurar e instalar todas as dependências no ambiente virtual `.venv`:

```bash
# Cria o .venv (caso não exista) e sincroniza as dependências declaradas no pyproject.toml / uv.lock
uv sync
```

### 2. Execução de Comandos, Linters e Testes

```bash
# Ativar o ambiente virtual (opcional)
source .venv/bin/activate

# Executar a CLI localmente
uv run consultor-juridico --help

# Executar testes unitários
uv run pytest

# Executar linter
uv run ruff check .
```

## Docker

O ambiente completo do sistema é containerizado via Docker Compose:

```bash
docker compose up --build -d
docker compose ps
docker compose run --rm app version
```

> **Configuração de Portas no Host:**
> - Comunicação interna entre containers: `db:5432` e `ollama:11434`.
> - Mapeamento de portas externas no Host (configuráveis no `docker-compose.yml` para evitar conflito com serviços locais):
>   - PostgreSQL: `5433:5432` (Acesso host: `localhost:5433`)
>   - Ollama: `11435:11434` (Acesso host: `localhost:11435`)

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
