# Fase 8 — Relatório de Conclusão: CLI Interativa

> **Status:** Concluída — `2026-08-21`
> **Referência TASKS.md:** `TASKS.md:117-128` — todos os 9 itens marcados `[x]`
> **Documento técnico base:** `docs/59-fase-8-cli-interativa.md`
> **Gate global do MVP1:** permanece `MVP1_QUALITY_BLOCKED` (herdado da Fase 7.2)

---

## 1. Resumo executivo

A Fase 8 encerrou a lacuna de usabilidade do MVP 1 sem violar nenhuma das
regras obrigatórias do projeto (`AGENTS.md:7-17`): transformou o
`consultor-juridico` — até então CLI-first puramente orientado a subcomandos —
em uma aplicação utilizável por usuário não técnico via **menu interativo Rich**,
mantendo compatibilidade total com automação (`non-TTY → help`), sem
introduzir frontend, API HTTP, ou nova infraestrutura.

Entregas centrais:

- `consultor-juridico` sem argumentos abre menu em TTY e imprime `help` em `non-TTY`
- `SystemReadiness` + `run_bootstrap` idempotente (DB, models, ingest, parse, index)
- 5 telas interativas (`consulta`, `pesquisa`, `estado`, `diagnóstico`, `sobre`)
- `Ctrl+C`/`EOFError` com saída limpa, sem traceback
- Aliases `ingest constituicao` e `parse constituicao` (PT-BR)
- `Dockerfile` sem `ENTRYPOINT` fixo, `CMD ["consultor-juridico"]`
- 33 testes unitários em `tests/test_interactive.py` (259 passed, 5 skipped no suite completo)
- Validação `docker compose build` + `run --rm app` + `bash` documentada e reproduzida

Nenhum invariante jurídico foi relaxado: a CLI continua sem regras de negócio,
o documento bruto (`SourceDocument.raw_bytes`) permanece autoridade e o LLM
nunca é fonte de verdade — toda resposta segue `Evidence Builder → Validator →
Citation Validator` com cadeia `claim → evidence → legal_element → legal_version
→ source_document → official_source`.

---

## 2. Objetivo

Conforme `docs/59-fase-8-cli-interativa.md:3-20`:

> Transformar o `consultor-juridico` CLI-first em aplicação utilizável por
> usuário não técnico, sem introduzir frontend, API HTTP ou nova infraestrutura.
> O binário deve abrir menu interativo quando executado em TTY, manter
> subcomandos existentes para automação e orientar a primeira execução até o
> corpus estar pronto para consulta fundamentada.

Requisitos de comportamento:

```text
consultor-juridico                     → menu interativo (TTY) ou help (non-TTY)
consultor-juridico ingest constituicao → alias PT-BR de ingest constitution
consultor-juridico parse constituicao  → alias PT-BR de parse constitution
Ctrl+C / EOF                           → saída limpa, sem traceback
docker compose run --rm app bash       → shell com CLI disponível
docker compose run --rm app            → consultor-juridico (via CMD)
```

---

## 3. Escopo entregue — checklist TASKS.md

| # | Item `TASKS.md:118-128` | Evidência | Status |
|---|---|---|---|
| 1 | Menu Rich em TTY / help em non-TTY (`main_callback`) | `src/consultor_juridico/cli/main.py:617-637` | ✅ |
| 2 | `SystemReadiness` sem efeitos colaterais (DB, Alembic, Ollama, modelos, índice) | `src/consultor_juridico/cli/interactive/readiness.py:20-165` | ✅ |
| 3 | `run_bootstrap` idempotente com `BootstrapEvent` (db, models, ingest, parse, index) | `src/consultor_juridico/cli/interactive/bootstrap.py:18-214` | ✅ |
| 4 | `Dockerfile` sem `ENTRYPOINT` fixo, `CMD ["consultor-juridico"]` | `Dockerfile:31-33` | ✅ |
| 5 | Telas: consulta (`run_consultation` + `hybrid_search`), pesquisa, estado, diagnóstico, sobre, sair | `src/consultor_juridico/cli/interactive/app.py:127-553` | ✅ |
| 6 | `Ctrl+C` / `EOFError` com saída limpa | `src/consultor_juridico/cli/interactive/app.py:109-117,548-553` | ✅ |
| 7 | Aliases `ingest constituicao` e `parse constituicao` | `src/consultor_juridico/cli/main.py:105-106,153-154` | ✅ |
| 8 | `tests/test_interactive.py` com 33 casos | `tests/test_interactive.py:1-776` | ✅ |
| 9 | Validação `docker compose build` / `run --rm app bash` / `consultor-juridico` + doc | `docs/59-fase-8-cli-interativa.md:153-181` | ✅ |

---

## 4. Arquitetura

### 4.1 Callback principal

```text
Typer app
  └─ @app.callback(invoke_without_command=True)          src/consultor_juridico/cli/main.py:617
       ├─ is_tty || force_interactive? → run_interactive_cli()
       └─ else → print_help + Exit(0)
```

Detecção usa `sys.stdin.isatty() and sys.stdout.isatty()` ou
`ctx.obj={"force_interactive": True}` (usado por `CliRunner` nos testes).
`non-TTY` nunca entra no loop — comportamento exigido para CI/automação.

### 4.2 Pacote `cli/interactive/`

```
src/consultor_juridico/cli/interactive/
├── readiness.py   # diagnóstico puro, sem efeitos colaterais
├── bootstrap.py   # orquestração idempotente com eventos
└── app.py         # UI Rich, telas e loop principal
```

**`readiness.py:20-42`** — `SystemReadiness` (frozen dataclass) com 8 flags e
propriedade `is_ready` (conjunção). `check_readiness():45-165` verifica
sequencialmente sem mutar estado:

1. `db_service.check_db_status()` → `connected`, `tables`, `alembic_version` → `schema_ready`
2. `httpx.get /api/tags` (timeout 2s) → `ollama_connected`, `llm_model_ready`, `embedding_model_ready`
3. `SessionLocal` → `source_ready` (SourceDocument >0), `parsing_ready` (ParsingRun COMPLETED + 2 LegalVersions ativas), `index_ready` (chunks == embeddings para versões ativas)

Exceções são capturadas e resultam em `False` fail-closed.

**`bootstrap.py:18-214`** — `BootstrapEvent(step, state, message)` e
`run_bootstrap() -> Generator[BootstrapEvent]`. Ordem fixa com early-abort:

```
all.is_ready? → success
database_connected? else db/failed
ollama_connected?  else ollama/failed
schema_ready?  → db/running → run_migrations()
llm_model_ready?      → models/running → pull_ollama_model()
embedding_model_ready?→ models/running → pull_ollama_model()
source_ready?  → ingest/running → run_planalto_ingestion()
parsing_ready? → parse/running  → materialize_constitution()
index_ready?   → index/running  → build_search_index()
→ all/success
```

`pull_ollama_model():27-35` consome `httpx.stream POST /api/pull` com
`timeout=600s`. Falhas em qualquer etapa emitem `failed` e encerram o
gerador — o caller exibe painel vermelho e retorna `sys.exit(1)`.

**`app.py`** — UI 100% Rich (Panel, Table, Prompt, Console.status):

- `show_banner():45-63` — cabeçalho com versão
- `handle_bootstrap():66-124` — spinner textual, painéis de falha, `KeyboardInterrupt` → saída parcial com instrução de reexecução
- Loop `run_interactive_cli():497-553` — menu `1-5,0`, `Prompt.ask` com `choices`, `KeyboardInterrupt`/`EOFError` → `Saindo... Obrigado por usar o Consultor Jurídico!`

---

## 5. Mudanças de código

### 5.1 Dockerfile — `Dockerfile:31-33`

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

Justificativa: `ENTRYPOINT` fixo impedia `bash` como override sem `--entrypoint`.
Sem ele, `docker compose run --rm app bash` funciona e `docker compose run --rm app`
executa `consultor-juridico` por padrão. `.venv` permanece isolado via
`uv sync --frozen` (`Dockerfile:22,29`).

### 5.2 Aliases PT-BR — `src/consultor_juridico/cli/main.py:105-106,153-154`

```python
@ingest_app.command(name="constitution")
@ingest_app.command(name="constituicao")
def ingest_constitution(): ...


@parse_app.command(name="constitution")
@parse_app.command(name="constituicao")
def parse_constitution_command(): ...
```

Dois decoradores no mesmo handler; validados via `ingest --help` / `parse --help`
e testes `test_aliases_portuguese_*`.

### 5.3 Main callback — `src/consultor_juridico/cli/main.py:617-637`

```python
@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        is_tty = sys.stdin.isatty() and sys.stdout.isatty()
        force_interactive = isinstance(ctx.obj, dict) and ctx.obj.get(
            "force_interactive"
        )
        if is_tty or force_interactive:
            from consultor_juridico.cli.interactive.app import run_interactive_cli

            run_interactive_cli()
        else:
            console.print(ctx.get_help())
            raise typer.Exit()
```

Lazy import evita ciclo; `force_interactive` permite teste com `CliRunner`
sem PTY real.

---

## 6. Fluxo first-run e readiness

```
usuário executa: consultor-juridico (TTY)
        ↓
check_readiness()
        ↓ is_ready?
   ┌─ sim ─→ Menu Principal
   └─ não ─→ "Primeira execução ou ambiente incompleto detectado."
             run_bootstrap() stream:
               ⠋ Aplicando migrations...  → ✓ Banco atualizado.
               ⠋ Baixando LLM 'llama3.2'... → ✓ Modelo baixado.
               ⠋ Ingestão Planalto...     → ✓ Ingestão concluída.
               ⠋ Parsing CF/ADCT...       → ✓ 4096 dispositivos.
               ⠋ Índice...                → ✓ 3389 chunks/embeddings.
             → "Sistema totalmente preparado!" → Menu
             (falha) → Panel vermelho "Falha na Preparação" → exit 1
```

Cada etapa reavalia `readiness` antes de agir; reexecução é idempotente
(verificações `if not readiness.*_ready`).

Tempo de primeira execução: dominado por downloads Ollama
(`~2 GB llama3.2` + `274 MB nomic-embed-text`).

---

## 7. Telas interativas

| Tela | Função `app.py` | Comportamento |
|---|---|---|
| **Consulta** | `run_consultation_screen():127-251` | Valida pergunta vazia, busca 2 `LegalVersions` ativas, chama `run_consultation` com `hybrid_search(limit=top_k)`, renderiza `ANSWERED` (painel verde + tabelas claims/citations) ou `ABSTAINED` (painel amarelo). Erros técnicos → painel vermelho `Falha Técnica`. Exige `hybrid_search` + `OllamaLegalGenerator` + `OllamaSemanticSupportValidator` — sem regra jurídica na CLI. |
| **Pesquisa** | `run_exploration_screen():253-308` | `Prompt.ask` termo, `hybrid_search(limit=5)`, exibe até 300 chars/chunk com rótulo `CF/88`/`ADCT` + `element_type number_label` em `Panel` cyan. Casos vazio/sem resultados/erro tratados. |
| **Estado** | `show_base_status_screen():311-379` | `materialization_status()` + contagens `chunks`/`embeddings` para versões ativas. Exibe tabela `Resumo da Base Jurídica` com disponibilidade de consulta. |
| **Diagnóstico** | `show_diagnostics_screen():382-470` | `check_readiness()` + `db_service.check_db_status()`. Tabela `Diagnóstico Geral` com DB, schema, Ollama, modelos, captura, materialização, índice. |
| **Sobre** | `show_about_screen():473-494` | Texto fixo com cadeia de rastreabilidade, privacidade local, validação e isenção de responsabilidade. |

`Ctrl+C`/`EOFError` em `handle_bootstrap():109-117` e no loop `app.py:548-553`
encerram com mensagem verde e `sys.exit(0)` — nunca traceback.

---

## 8. Testes e qualidade

### 8.1 Suite

`tests/test_interactive.py:1-776` — **33 testes**, todos mockados (sem I/O real,
sem rede, sem PostgreSQL/Ollama):

- **readiness (4):** `is_ready` conjunção, DB desconectado, modelos+índice ok, exceção de sessão → `source/parsing/index = False`.
- **bootstrap (8):** noop quando ready, falha DB/Ollama, sucesso completo com todas as etapas, `pull_ollama_model` consome stream, falhas isoladas de migration/pull/ingest/parse/index.
- **interação (21):** `non-TTY` mostra help, TTY pronto vai ao menu, `KeyboardInterrupt`/`EOFError` encerram limpo, bootstrap sucesso/falha, consulta `ANSWERED`/`ABSTAINED`/vazia/erro técnico/versões faltando, exploração com resultados/vazia/sem resultados/erro, `status`+`diagnóstico`+`about`, aliases `constituicao` para ingest/parse, `status` com erro de DB.

Fixtures `cli_runner`/`cli_app` reutilizadas de `tests/conftest.py`.

### 8.2 Execução

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest -q            # 259 passed, 5 skipped (suite completa)
uv run pytest tests/test_interactive.py -q  # 33 passed
```

Arquivo driver PTY `.tmp_validate_interactive.py` foi formatado para `E501`
conforme `docs/59-fase-8-cli-interativa.md:152`.

---

## 9. Validação em container

Comandos executados e documentados em `docs/59-fase-8-cli-interativa.md:153-168`:

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

Consultas reais exercitam índice materializado; resposta atual `ABSTAINED`
(juiz `llama3.2` conservador) é comportamento **fail-closed esperado**, não
regressão — Hybrid Hit@10 0,905 permanece válido da Fase 7.2. Pesquisa direta
retorna `CF/88 INCISO IV` e `CF/88 CAPUT art. 220` no topo.

---

## 10. Estado materializado (inalterado pela Fase 8)

```
sources             = 1
source_documents    = 1  (1.839.482 bytes, SHA-256 25b6934ef228df40d0f5d35e...)
legal_acts          = 2  (CF/88, ADCT)
legal_versions      = 2  (1 ativa por ato)
legal_provisions    = 4096
legal_elements      = 6775
chunks              = 3389
embeddings          = 3389 (768 dims, nomic-embed-text)
```

Distribuição:

| Ato | LegalVersions | LegalProvisions | LegalElements |
|---|---:|---:|---:|
| CF/88 | 1 | 3.133 | 5.063 |
| ADCT  | 1 | 963 | 1.712 |

Retrieval Fase 7.2 preservado:

| Métrica hybrid | Valor |
|---|---:|
| Hit@1 | 0,524 |
| Hit@3 | 0,714 |
| Hit@10 | **0,905** |
| MRR | 0,627 |
| Recall@10 | 0,881 |

---

## 11. Invariantes e conformidade

| Regra `AGENTS.md` | Como a Fase 8 preserva |
|---|---|
| 1. CLI-first, 2. sem frontend, 3. sem API HTTP | Menu é `Typer`+`Rich` no terminal; nenhum servidor/framework web adicionado |
| 7. CLI não contém regras de negócio | Telas delegam a `hybrid_search` (`src/consultor_juridico/retrieval/`) e `run_consultation` (`src/consultor_juridico/consultation/`); nenhuma decisão de evidência na CLI |
| 8. Fonte primária é autoridade | `SourceDocument.raw_bytes` + SHA-256 intactos; bootstrap reutiliza `run_planalto_ingestion` existente |
| 9. LLM nunca é fonte | Geração sempre grounded em `EvidenceItems`; isolamento mantido |
| 10. Evidências rastreáveis | Citações exibidas com `citation_label` + `source_url` do Planalto |
| 11. Documento bruto nunca sobrescrito | Idempotência por `(source_id, content_hash_sha256)` preservada |
| 12. Parsing determinístico | `materialize_constitution` reutilizado sem alteração |
| 13. Ingestão idempotente | `run_planalto_ingestion` + `304 ALREADY_KNOWN` preservados |

Cadeia de rastreabilidade permanece íntegra:

```text
Claim → Citation → EvidenceItem → Chunk → LegalElement → LegalProvision
      → LegalVersion → ParsingRun → SourceDocument → Source (Planalto)
```

---

## 12. Limitações conhecidas

Herdadas da Fase 7.2 (`docs/58-fase-7-2-fechamento-gate-mvp1.md:7-14`) e
específicas da Fase 8 (`docs/59-fase-8-cli-interativa.md:181-188`):

- Gate global `MVP1_QUALITY_BLOCKED` persiste: `llama3.2` conservador gera
  false abstention em amostra direta (0/3 respondidas, 0 unsafe) — blocker
  generativo/semântico, não da CLI.
- Corpus restrito a CF/88 + ADCT (3389 chunks); sem HNSW, reranker ou
  expansão de query além da promoção contextual de CAPUT.
- Menu em português, sem paginação de resultados nem exportação.
- Primeira execução baixa modelos (~2 GB + 274 MB) e pode levar minutos;
  `httpx.stream` com `timeout=600s` cobre o caso, mas rede lenta pode falhar.
- `consult` interativo usa `hybrid_search` com `settings.consultation_top_k`
  e `evidence_limit`; filtros avançados (por ato/tipo) só na tela de pesquisa.

---

## 13. Critérios de aceite da Fase 8

| Critério | Verificação | Resultado |
|---|---|---|
| `consultor-juridico` sem args em TTY abre menu | `CliRunner` com `isatty=True` + `force_interactive` | ✅ |
| `non-TTY` exibe help e `exit 0` | `test_interactive_non_tty` | ✅ |
| `docker compose run --rm app bash` abre shell | Remoção de `ENTRYPOINT`, `CMD` padrão | ✅ |
| `ingest constituicao` / `parse constituicao` funcionam | `test_aliases_portuguese_*` + `--help` no container | ✅ |
| `Ctrl+C`/`EOF` sem traceback | `test_interactive_keyboard_interrupt_*`, `test_interactive_eof_*` | ✅ |
| Bootstrap idempotente e auditável | `BootstrapEvent` stream + `check_readiness` reavaliado | ✅ |
| 5 telas funcionais | `test_interactive_consultation_*`, `test_interactive_exploration_*`, `test_interactive_status_and_diagnostics` | ✅ |
| Suite verde + lint | `ruff format --check`, `ruff check`, `pytest -q` | ✅ |
| Documentação | `docs/59-fase-8-cli-interativa.md` + este relatório | ✅ |

---

## 14. Referências

- `TASKS.md:117-128` — definição da Fase 8
- `docs/59-fase-8-cli-interativa.md:1-198` — especificação técnica da fase
- `src/consultor_juridico/cli/main.py:617-637` — `main_callback` TTY/non-TTY
- `src/consultor_juridico/cli/main.py:105-106,153-154` — aliases PT-BR
- `src/consultor_juridico/cli/interactive/readiness.py:20-165` — `SystemReadiness` e `check_readiness`
- `src/consultor_juridico/cli/interactive/bootstrap.py:18-214` — `BootstrapEvent`, `pull_ollama_model`, `run_bootstrap`
- `src/consultor_juridico/cli/interactive/app.py:45-553` — banner, bootstrap handler, 5 telas, loop
- `Dockerfile:31-33` — `CMD ["consultor-juridico"]` sem `ENTRYPOINT`
- `tests/test_interactive.py:1-776` — 33 testes unitários
- `docs/58-fase-7-2-fechamento-gate-mvp1.md:1-141` — contexto do gate herdado
- `README.md:97-102,1738-1748` — resumo público da Fase 8

---

## 15. Conclusão e próximos passos

A Fase 8 está **concluída e validada** nos critérios que lhe cabiam: usabilidade
via TTY, idempotência de bootstrap, integridade de `readiness`, aliases,
tratamento de interrupção, e compatibilidade Docker sem quebrar automação.

O blocker que impede a declaração de `MVP 1 concluído` (`TASKS.md:115`) não é
da Fase 8, mas do gate generativo/semântico da Fase 7.2: taxa de false
abstention do `llama3.2` como gerador e juiz. A recomendação registrada em
`docs/58-fase-7-2-fechamento-gate-mvp1.md:139-141` permanece válida — comparar
outro juiz local (Granite 4.1 3B previsto) antes de novo tuning ilimitado.

Próximos passos sugeridos (fora do escopo da Fase 8, requerem decisão humana):

1. Benchmark de `SEMANTIC_JUDGE_MODEL=granite4.1` vs `llama3.2` no
   `semantic-support-v1` e na amostra direta 7.2.
2. Se `false abstention` cair sem introduzir `unsafe acceptance`, reavaliar
   gate `MVP1_QUALITY_BLOCKED`.
3. Só então considerar HNSW/reranking adicionais — condicionados a benchmark,
   conforme `TASKS.md:81`.
