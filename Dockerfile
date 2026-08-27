FROM python:3.13-slim

WORKDIR /app

# Configurações de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Instalação de utilitários básicos
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalação do uv dentro do container
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copia arquivos de dependência e configuração
COPY pyproject.toml uv.lock README.md alembic.ini ./

# Cria o .venv interno do container e instala dependências
RUN uv sync --frozen --no-install-project

# Copia o código-fonte
COPY src/ ./src/
COPY evaluation/ ./evaluation/
COPY --chmod=755 docker/app-entrypoint.sh /usr/local/bin/app-entrypoint.sh

# Instala a aplicação no ambiente do container
RUN uv sync --frozen

ENTRYPOINT ["app-entrypoint.sh"]

# O entrypoint prepara o MVP1 antes de entregar o comando solicitado.
CMD ["consultor-juridico"]
