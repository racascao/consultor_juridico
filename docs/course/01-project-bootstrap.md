# 01. Bootstrap do projeto

## Objetivo

Começar em um diretório vazio e terminar com pacote importável, configuração
tipada, CLI mínima e ferramentas de qualidade.

## Onde estamos

```text
diretório vazio
```

## O que construiremos

```text
pyproject.toml → .venv + uv.lock → src package → CLI Typer → pytest/Ruff
```

## Arquivos desta etapa

Criados:

```text
pyproject.toml
.gitignore
src/consultor_juridico/__init__.py
src/consultor_juridico/config.py
src/consultor_juridico/cli/__init__.py
src/consultor_juridico/cli/main.py
tests/test_config.py
```

## Projeto e dependências

Crie `pyproject.toml`. Este arquivo completo é suficiente para o primeiro
checkpoint; dependências de banco e HTTP já entram agora para manter um único
lock ao longo do curso.

```toml
[project]
name = "consultor-juridico"
version = "0.2.0.dev0"
requires-python = ">=3.13"
dependencies = [
  "typer>=0.12.0", "rich>=13.7.0",
  "pydantic>=2.7.0", "pydantic-settings>=2.2.0",
  "sqlalchemy>=2.0.30", "alembic>=1.13.0",
  "psycopg[binary]>=3.1.18", "httpx>=0.27.0",
  "beautifulsoup4>=4.12.3",
]

[project.scripts]
consultor_juridico = "consultor_juridico.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/consultor_juridico"]

[dependency-groups]
dev = ["pytest>=8.2.0", "ruff>=0.4.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 88
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

O layout `src` impede que testes importem acidentalmente o diretório de
trabalho em vez do pacote instalado. Hatchling empacota apenas o package atual.

## Package, settings e CLI

Em `src/consultor_juridico/__init__.py`:

```python
__version__ = "0.2.0.dev0"
```

Crie `src/consultor_juridico/config.py` com Pydantic Settings. Este recorte
didático introduz as variáveis usadas nos próximos capítulos:

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = Field(
        default="postgresql+psycopg://consultor:consultor_pass@db:5432/consultor_juridico_v02",
        alias="DATABASE_URL",
    )
    ollama_base_url: str = Field(default="http://ollama:11434", alias="OLLAMA_BASE_URL")


settings = Settings()
```

Crie `src/consultor_juridico/cli/main.py`:

```python
import typer
from rich.console import Console
from consultor_juridico import __version__

app = typer.Typer(name="consultor_juridico", add_completion=False)
console = Console()


@app.command()
def version() -> None:
    """Exibe a versão do pacote."""
    console.print(f"Consultor Jurídico {__version__}")
```

O entry point do `pyproject.toml` aponta diretamente para `app`; não crie um
segundo executable com hífen.

## Testes

Em `tests/test_config.py`, proteja aliases e defaults:

```python
from consultor_juridico.config import Settings


def test_settings_accept_environment_aliases(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    configured = Settings(_env_file=None)
    assert configured.ollama_base_url == "http://ollama:11434"
```

## Executando

```bash
uv sync
uv run consultor_juridico version
uv run pytest tests/test_config.py -q
uv run ruff format --check .
uv run ruff check .
```

Resultado esperado: a CLI imprime `Consultor Jurídico 0.2.0.dev0`, o teste
passa e Ruff não encontra violações.

## Erros comuns

- instalar dependências globalmente em vez de usar a `.venv`;
- omitir `packages` do Hatch e gerar wheel sem `src/consultor_juridico`;
- usar `localhost` como host do banco/Ollama dentro do container.

## Checkpoint

Você pode avançar quando `uv run consultor_juridico version` e os três comandos
de qualidade acima passarem. Ainda não existe banco, corpus ou LLM.

**Próximo:** [infraestrutura](02-infrastructure.md).
