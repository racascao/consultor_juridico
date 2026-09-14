# 02. Infraestrutura

## Objetivo

Executar PostgreSQL, Ollama e a imagem da aplicação em uma rede Compose com
volumes persistentes e readiness verificável.

## Onde estamos

```text
package Python + CLI
```

## O que construiremos

```text
host :5434 → db :5432 ← app → ollama :11434 ← host :11435
```

## Antes de começar

Confirme `uv run consultor_juridico version`. Docker deve responder a
`docker compose version`.

## Arquivos desta etapa

Criados: `Dockerfile`, `docker-compose.yml`, `.env.example`.

## Compose

O recorte abaixo preserva portas, volumes, GPU e dependências reais. No
capítulo 13 trocaremos o comando provisório da app pelo bootstrap.

```yaml
name: consultor_juridico_v02
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: consultor
      POSTGRES_PASSWORD: consultor_pass
      POSTGRES_DB: consultor_juridico_v02
    ports: ["5434:5432"]
    volumes: ["consultor_juridico_v02_pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U consultor -d consultor_juridico_v02"]
      interval: 5s
      timeout: 5s
      retries: 5

  ollama:
    image: ollama/ollama:latest
    gpus: all
    ports: ["${OLLAMA_HOST_PORT:-11435}:11434"]
    volumes: ["consultor_juridico_ollama:/root/.ollama"]
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 5s
      timeout: 5s
      retries: 12

  app:
    build: .
    environment:
      DATABASE_URL: postgresql+psycopg://consultor:consultor_pass@db:5432/consultor_juridico_v02
      OLLAMA_BASE_URL: http://ollama:11434
    depends_on:
      db: {condition: service_healthy}
      ollama: {condition: service_healthy}
    command: ["consultor_juridico", "version"]

volumes:
  consultor_juridico_v02_pgdata:
  consultor_juridico_ollama:
```

Dentro da rede, `db` e `ollama` são DNS dos serviços. `localhost` apontaria
para o próprio container. No host, use apenas as portas publicadas 5434 e 11435;
`localhost:11434` pode pertencer a outra instalação e não é suportado.

## Dockerfile

```dockerfile
FROM python:3.13-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project
COPY src/ ./src/
RUN uv sync --frozen
CMD ["consultor_juridico", "version"]
```

O modelo de 12B exige GPU no ambiente congelado. O volume de Ollama evita novo
download a cada container; o volume PostgreSQL preserva corpus e índice.

## Ambiente

Em `.env.example` registre `OLLAMA_BASE_URL=http://ollama:11434`,
`OLLAMA_HOST_PORT=11435`, credenciais locais e `DATABASE_URL`. Não coloque
segredos de produção nesse arquivo.

## Executando e testando

```bash
docker compose config
docker compose up -d db ollama
docker compose ps
docker compose exec db pg_isready -U consultor -d consultor_juridico_v02
docker compose exec ollama ollama list
docker compose run --rm app consultor_juridico version
```

`ollama list` vazio ainda é sucesso do servidor; o modelo será preparado no
capítulo 13. Nenhuma inferência é feita aqui.

## Checkpoint

Os dois healthchecks devem estar `healthy`, a app deve imprimir a versão e os
volumes devem permanecer após recriar containers.

**Anterior:** [bootstrap](01-project-bootstrap.md).  
**Próximo:** [modelo de dados](03-data-model.md).
