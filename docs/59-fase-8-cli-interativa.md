# Fase 8 — CLI Interativa

## 1. Objetivo

Transformar o `consultor-juridico` CLI-first em uma aplicação utilizável por
usuário não técnico, sem introduzir frontend, API HTTP ou nova infraestrutura.
O binário deve abrir um menu interativo quando executado em TTY, manter os
subcomandos existentes para automação e orientar a primeira execução até o
corpus estar pronto para consulta fundamentada.

Requisitos do escopo:

```text
consultor-juridico                    → menu interativo (TTY) ou help (non-TTY)
consultor-juridico ingest constituicao→ alias PT-BR de ingest constitution
consultor-juridico parse constituicao → alias PT-BR de parse constitution
Ctrl+C / EOF                          → saída limpa, sem traceback
docker compose run --rm app bash      → shell com CLI disponível
docker compose run --rm app           → consulta-juridico (via CMD)
```

## 2. Arquitetura

```text
Typer app
  └─ @app.callback(invoke_without_command=True)
       ├─ is_tty || force_interactive? → run_interactive_cli()
       └─ else → print_help + Exit
```

Novo pacote `src/consultor_juridico/cli/interactive/`:

- `readiness.py`: diagnóstico sem efeitos colaterais. Checa PostgreSQL +
  Alembic, `/api/tags` do Ollama, presença de `llama3.2` e
  `nomic-embed-text`, e consistência do índice (chunks == embeddings para as
  duas LegalVersions ativas). Retorna `SystemReadiness` imutável.
- `bootstrap.py`: orquestra preparação idempotente emitindo
  `BootstrapEvent(step, state, message)`. Etapas: `db` (migrations),
  `models` (pull Ollama), `ingest` (Planalto), `parse` (materialização) e
  `index` (chunks + embeddings). Falhas de DB/Ollama abortam cedo com
  mensagem orientada ao usuário.
- `app.py`: UI Rich (banner, menu, telas). Loop principal oferece
  1 consulta, 2 exploração, 3 estado, 4 diagnóstico, 5 sobre, 0 sair.
  Consulta e exploração reutilizam `hybrid_search` e `run_consultation` dos
  serviços de aplicação; a CLI não contém regra de negócio jurídica.

Invariantes preservados:

- a CLI não decide o que é evidência; delega a `Evidence Builder/Validator` e
  `Citation Validator`;
- o documento bruto permanece autoridade; LLM nunca é fonte;
- parsing permanece determinístico e idempotente.

## 3. Mudanças de código

### Dockerfile

Antes:

```dockerfile
ENTRYPOINT ["consultor-juridico"]
CMD ["--help"]
```

Depois:

```dockerfile
# Sem ENTRYPOINT fixo: `docker compose run --rm app bash` abre o shell;
# o comando padrão inicia a CLI (menu interativo em TTY).
CMD ["consultor-juridico"]
```

Isso permite `bash` como override e mantém `consultor-juridico` como default.
O `.venv` interno do container permanece isolado (`uv sync --frozen`).

### CLI principal

- `src/consultor_juridico/cli/main.py:153,155` — aliases `constituicao` para
  `ingest` e `parse` via duplo `@app.command(name=...)`.
- `src/consultor_juridico/cli/main.py:617-637` — `main_callback` com
  `invoke_without_command=True`. Detecta `sys.stdin.isatty() and
  sys.stdout.isatty()` ou `obj={"force_interactive": True}` (usado nos testes
  `CliRunner`). Em TTY chama `run_interactive_cli()`, senão imprime help.

### Telas interativas

- `run_consultation_screen`: valida pergunta vazia, obtém duas LegalVersions
  ativas, executa `run_consultation` com `hybrid_search` limitado por
  `settings.consultation_top_k`, e renderiza `ANSWERED` (painel verde +
  tabelas de claims/citations) ou `ABSTAINED` (painel amarelo).
- `run_exploration_screen`: busca híbrida `limit=5` e exibe até 300 chars por
  chunk com rótulo `CF/88`/`ADCT` e `element_type number_label`.
- `show_base_status_screen`: conta `legal_elements`, `legal_provisions`,
  `chunks` e `embeddings` para as versões ativas; usa
  `materialization_status` para totais.
- `show_diagnostics_screen`: tabela com DB, Alembic, Ollama, modelos,
  captura, materialização e índice, derivada de `check_readiness()` e
  `db_service.check_db_status()`.
- `show_about_screen` e `show_banner`: textos fixos com isenção de
  responsabilidade.

Tratamento de interrupção: `KeyboardInterrupt`/`EOFError` no loop e no
bootstrap encerram com `Saindo... Obrigado por usar o Consultor Jurídico!`
sem traceback; bootstrap interrompido avisa que o ambiente ficou
parcialmente preparado.

## 4. First-run e readiness

Na inicialização interativa, `handle_bootstrap()` checa `is_ready`. Se já
está pronto, vai direto ao menu. Caso contrário:

```text
Primeira execução ou ambiente incompleto detectado.
⠋ Aplicando migrations...
✓ Banco atualizado.
⠋ Baixando LLM 'llama3.2'...
✓ Modelo baixado.
...
Sistema totalmente preparado!
```

Cada etapa verifica `readiness` antes de agir; erros são exibidos em
`Panel(title="Falha na Preparação", border_style="red")` e retornam `False`,
levando o callback a `sys.exit(1)`.

## 5. Testes

`tests/test_interactive.py` possui 33 testes unitários (todos mockados, sem
I/O real ou rede):

- readiness: todas as flags, DB desconectado, modelos e índice detectados,
  exceção de sessão;
- bootstrap: noop, falha DB/Ollama, sucesso completo, falhas isoladas de
  migration, pull, ingest, parse, index, consumo do stream Ollama;
- interação: non-TTY mostra help, TTY pronto vai ao menu, `KeyboardInterrupt`
  e `EOFError` encerram limpo, bootstrap sucesso/falha, consulta
  answered/abstained/vazia/erro técnico/versões faltando, exploração com
  resultados/vazia/sem resultados/erro, status + diagnóstico + about,
  aliases `constituicao` para ingest e parse.

Fixtures `cli_runner` e `cli_app` de `tests/conftest.py` são reutilizadas.
Cobertura foi validada com:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest -q  # 259 passed, 5 skipped
```

O arquivo `.tmp_validate_interactive.py` (driver PTY para validação em
container) foi formatado e corrigido para `E501`.

## 6. Validação em container

```bash
docker compose build app
docker compose run --rm app consultor-juridico --help
docker compose run --rm app consultor-juridico ingest --help   # lista constituicao + constitution
docker compose run --rm app consultor-juridico parse --help    # idem
docker compose run --rm app consultor-juridico                  # non-TTY → help, exit 0
docker compose run --rm app bash -c "consultor-juridico --help"
docker compose run --rm app consultor-juridico db status
docker compose run --rm app consultor-juridico ingest status    # 1 captura, 1.839.482 bytes, SHA-256 25b69...
docker compose run --rm app consultor-juridico parse status     # 4096 provisions, 6775 elements
docker compose run --rm app consultor-juridico index status     # 3389 chunks / 3389 embeddings / 768 dims
docker compose run --rm app consultor-juridico retrieval search "manifestação do pensamento" --mode hybrid
docker compose run --rm app consultor-juridico consult "O que a Constituição diz sobre a manifestação do pensamento?"
docker compose run --rm -v "$(pwd)/.tmp_validate_interactive.py:/tmp/validate.py" app python /tmp/validate.py menu
# verifica: Menu Principal, CONSULTOR JURÍDICO, Estado da Base Jurídica, Diagnóstico Técnico, Sobre o Projeto, saída
```

Consultas reais exercitam o índice materializado; a resposta atual é
`ABSTAINED` (juiz `llama3.2` conservador), o que é comportamento fail-closed
esperado e não indica regressão do retrieval (Hybrid Hit@10 0,905 permanece
válido da Fase 7.2). A pesquisa direta retorna `CF/88 INCISO IV` e
`CF/88 CAPUT art. 220` no topo, confirmando o índice.

Aliases validados via `CliRunner` e via `ingest --help` no container:
`constituicao` e `constitution` apontam para o mesmo handler.

## 7. Limitações

- o corpus permanece CF/88 + ADCT, 3389 chunks, embeddings `nomic-embed-text`;
- não há HNSW, reranker ou expansão de query;
- geração e juiz semântico continuam `llama3.2` (`SEMANTIC_JUDGE_MODEL` opcional);
- o menu é em português e não oferece paginação de resultados nem exportação;
- primeira execução baixa modelos (~2 GB LLM + 274 MB embeddings) e pode levar
  minutos.

## 8. Referências

- `src/consultor_juridico/cli/interactive/readiness.py`
- `src/consultor_juridico/cli/interactive/bootstrap.py`
- `src/consultor_juridico/cli/interactive/app.py`
- `src/consultor_juridico/cli/main.py:617`
- `Dockerfile:32-33`
- `tests/test_interactive.py`
- `docs/58-fase-7-2-fechamento-gate-mvp1.md`
