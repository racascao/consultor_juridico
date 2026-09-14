# 13. CLI, Bootstrap e Packaging

## Objetivo

Transformar os casos de uso em um produto instalável, com bootstrap idempotente,
readiness, interface Rich e uso scriptável.

## Onde estamos e incremento

```text
serviços testáveis → composition root → Typer/Rich → imagem executável
```

## Arquivos desta etapa

- `services/bootstrap.py` e `db_service.py`;
- `cli/main.py`, `display.py` e `cli/interactive/{app,bootstrap,readiness}.py`;
- `Dockerfile`, `docker-compose.yml`, `pyproject.toml`;
- `tests/test_mvp2_packaging_cli.py`.

## Comando oficial

```toml
[project.scripts]
consultor_juridico = "consultor_juridico.cli.main:app"
```

O `PATH=/app/.venv/bin:$PATH` no Dockerfile permite executar o script sem
`uv run`. Não crie o nome legado `consultor-juridico`.

## Bootstrap

`BootstrapReadiness` registra migrations, corpus e modelo. `ready` só é
verdadeiro quando todas as dimensões estão prontas. O orquestrador recebe checks
e operações por injeção:

```python
class BootstrapOrchestrator:
    def run(self) -> Iterator[BootstrapEvent]:
        state = self._readiness()
        if not state.migrations_ready:
            yield BootstrapEvent("migrations", RUNNING, "Aplicando migrations")
            self._migrate()
        state = self._readiness()
        if not state.corpus_ready:
            yield BootstrapEvent("corpus", RUNNING, "Preparando corpus")
            self._prepare_corpus()
        state = self._readiness()
        if not state.model_ready:
            yield BootstrapEvent("model", RUNNING, "Preparando modelo")
            self._prepare_model()
        if not self._readiness().ready:
            raise BootstrapFailure("BOOTSTRAP_NOT_READY")
```

Este recorte didático omite eventos `READY`, mas mantém a rechecagem após cada
passo. A fonte de verdade é PostgreSQL/Ollama, não um arquivo no container.

`check_readiness` compara Alembic head, corpus auditável, SearchUnits e modelo
com digest exato. `_prepare_corpus` adquire apenas se necessário e materializa
idempotentemente. `_prepare_model` pode executar pull no Ollama do Compose.

## Typer e Rich

`cli/main.py` registra `bootstrap`, `status`, `tutorial`, `consult` e grupos
avançados. Sem subcomando, abre o menu apenas em TTY; em pipe/non-TTY, encerra
com instrução de ajuda.

```python
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if not sys.stdin.isatty():
        console.print("Use consultor_juridico --help em execução scriptável.")
        raise typer.Exit(2)
    run_interactive_cli(console=console, readiness=check_readiness, consult=...)
```

O menu oferece regra jurídica, situação concreta, status, tutorial e saída.
`run_with_query_feedback` mostra spinner somente para `LEGAL_RULE` em TTY.
Isso não altera `stream=false`.

## Composition root da consulta

`_run_consult` abre session, cria
`PostgresRelaxedOrCoverageFullTextSearchRetriever`,
`SqlAlchemyGoldEvidenceRepository`, cliente HTTP e `OllamaSelectedAnswerer`,
então chama `RunRagQuery`. A CLI apresenta `RagResult`; regras não devem morar
na camada de display.

## Container one-shot

Configure:

```yaml
app:
  command: ["consultor_juridico", "bootstrap"]
```

```bash
docker compose up --build
# app exited with code 0 é sucesso; db e ollama continuam ativos
docker compose run --rm app consultor_juridico
```

## Testes

Use `CliRunner`, mocks de readiness/operações e console capturado. Cubra help,
nome oficial, non-TTY, status, tutorial, bootstrap vazio/pronto/parcial/falha,
duas execuções, header e ausência de spinner em non-TTY.

```bash
uv run pytest tests/test_mvp2_packaging_cli.py -q
docker compose run --rm app consultor_juridico --help
docker compose run --rm app consultor_juridico status
```

## Checkpoint

Primeiro bootstrap prepara, segundo apenas confirma; falha nunca abre CLI como
READY; o executable funciona na imagem e o container one-shot termina em zero.

**Anterior:** [Query Modes](12-query-modes.md).  
**Próximo:** [avaliação](14-evaluation.md).
