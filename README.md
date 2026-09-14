# Consultor Jurídico

Mecanismo CLI-first de consulta jurídica local, baseado em corpus oficial
versionado, evidências rastreáveis e citações validadas.

## Status

```text
MVP2_STATUS: CLOSED
MVP2_FINAL_DECISION: MVP2_ACCEPTED_WITH_KNOWN_LIMITATIONS
```

O runtime `integrated-runtime-mvp2/1` foi medido em uma única campanha Blind
HOLDOUT, sem tuning posterior. A aceitação registra limitações conhecidas; não
declara um sistema jurídico geral ou perfeito.

## O que é

O projeto materializa uma fonte oficial em PostgreSQL, recupera unidades
textuais e responde consultas normativas usando somente as evidências
recuperadas. A resposta possui citações verificadas e trace auditável. O modelo
de linguagem não é tratado como fonte jurídica.

O produto é local e executado por CLI. Não há frontend, API web, busca vetorial
ou embeddings. O bootstrap pode acessar o Planalto para obter o corpus ausente;
uma consulta nunca acessa a web e usa somente o snapshot persistido.

## Escopo atual

- Lei Federal nº 9.784/1999 (`BR-FED-LEI-9784-1999`);
- captura local versionada e preservada por SHA-256;
- PostgreSQL FTS;
- Ollama via Docker Compose;
- modos explícitos `LEGAL_RULE` e `CASE_APPLICATION`.

## Arquitetura resumida

```text
LEGAL_RULE
Pergunta → PostgreSQL FTS → expansão estrutural → Evidence Assembly
         → Gemma4 12B → validação JSON → Citation Validation
         → resposta rastreável

CASE_APPLICATION
Pergunta → CLARIFY determinístico
         → retrieval não executado, answerer não executado, citações vazias
```

O modo é informado pelo caller e nunca inferido automaticamente. Consulte a
[arquitetura completa](docs/reference/architecture.md).

## Principais capacidades

- aquisição, versionamento e materialização idempotente do corpus;
- parser jurídico estrutural e auditoria de cobertura;
- retrieval lexical PostgreSQL com versão explícita;
- expansão de evidência por filhos estruturais diretos;
- geração local vinculada às evidências;
- contrato JSON estrito e Citation Validation determinística;
- rastreabilidade de `SearchUnit` até snapshot e fonte oficial;
- CLI administrativa, consulta e trace diagnóstico;
- boundary seguro para aplicação a casos concretos.

## Limitações conhecidas

- corpus piloto limitado à Lei nº 9.784/1999;
- recall inicial de provisions obrigatórias `26/44`, elevado a `40/44` pelo
  assembly estrutural no Blind HOLDOUT;
- contrato de saída válido em `34/36` casos;
- correção jurídica humana `34/36` e completude `32/36`;
- `CASE_APPLICATION` apenas solicita esclarecimento, sem aplicar fatos;
- nenhum web fetch durante consultas, vetor, embedding ou RRF.

## Requisitos

- Python 3.13 ou superior e `uv`;
- Docker com Docker Compose;
- PostgreSQL 16 via Compose;
- Ollama via Compose, publicado no host em `localhost:11435`.

Ollama nativo no host em `localhost:11434` não é suportado. O modelo é preparado
automaticamente no primeiro bootstrap e armazenado em volume Docker.

## Início rápido

```bash
cp .env.example .env
docker compose up --build
```

O Compose sobe PostgreSQL e Ollama, aplica migrations, baixa a Lei nº 9.784/1999
do Planalto se o snapshot ainda não existir, materializa o corpus/FTS e prepara
`gemma4:12b`. O container `app` encerra com código zero ao concluir; banco e
Ollama permanecem disponíveis. A primeira execução requer internet e pode ser
demorada por causa do download do modelo.

O texto `app exited with code 0` é esperado: `app` é um bootstrap one-shot, não
um servidor. Antes de encerrar, ele mostra um resumo `READY` e o comando para
abrir a interface. PostgreSQL e Ollama continuam executando.

Em outro terminal, execute a aplicação pela imagem:

```bash
docker compose run --rm app consultor_juridico
```

O cabeçalho informa o modelo ativo (`Gemma4:12b`). Consultas de regra jurídica
mostram um indicador Rich enquanto retrieval, assembly, geração e validação são
executados. Esse indicador não é streaming do modelo: o contrato congelado usa
`stream=false` e exibe somente a resposta final validada.

Execução scriptável:

```bash
docker compose run --rm app consultor_juridico --help
docker compose run --rm app consultor_juridico status
docker compose run --rm app consultor_juridico bootstrap
```

Uma consulta normativa usa a versão materializada mais recente do ato, salvo se
`--version-hash` for informado explicitamente:

```bash
docker compose run --rm app consultor_juridico consult \
  "Qual é o prazo para a Administração decidir o recurso?" \
  --mode legal-rule \
  --base-url http://ollama:11434
```

Para uma situação concreta, use `--mode case-application`; esse modo retorna
`CLARIFY` deterministicamente, sem retrieval, LLM ou citações. Use `--trace`
para detalhes técnicos já suportados. Depois do bootstrap, toda consulta usa o
banco e o modelo locais, sem acessar o Planalto.

No host, o desenvolvimento continua disponível com `uv sync --frozen` e
ativação de `.venv` seguida de `consultor_juridico`. Os grupos `db`, `corpus`,
`retrieval`, `rag` e `eval` são operações avançadas.

## Testes e qualidade

```bash
.venv/bin/python -m pytest
.venv/bin/ruff format --check .
.venv/bin/ruff check .
```

Testes PostgreSQL opt-in usam `V02_TEST_DATABASE_URL`. Os testes automáticos não
acessam o Planalto nem executam inferência real.

## Estrutura do projeto

```text
consultor_juridico/
├── src/consultor_juridico/   # domínio, aplicação, infraestrutura e CLI
├── tests/                    # regressões e integração opt-in
├── docs/                     # arquitetura, experimentos, estado e corpus
├── evaluation/               # freezes e artefatos mínimos de auditoria
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── uv.lock
```

## Documentação

O site MkDocs separa o caminho recomendado de construção, a referência do
runtime congelado e a história experimental:

- [Documentação pública](https://racascao.github.io/consultor_juridico/)

- [Curso — construindo o MVP2](docs/course/index.md)
- [Referência de arquitetura](docs/reference/architecture.md)
- [Experimentos e decisões](docs/experiments/index.md)
- [Estado canônico](docs/STATE.md)

Para abrir localmente:

```bash
uv run mkdocs serve
```

Para validar a fotografia documental:

```bash
uv run mkdocs build --strict
```

O diretório `site/` é artifact local e não deve ser versionado. A documentação
é publicada automaticamente no GitHub Pages após cada push para `main`; o
workflow também permite execução manual.

## MVP1

O MVP1 é preservado pela tag imutável `v0.1.0` apenas como referência histórica.
As lições relevantes estão nos [experimentos](docs/experiments/index.md).
A tag `0.2.0` preserva o MVP2; a `main` recebe esta documentação pós-freeze.

## Próxima evolução

Uma eventual `POST_HOLDOUT_METHOD_PHASE` ou MVP3 deverá começar com novo
baseline, hipóteses gerais e datasets DEV independentes. O Blind HOLDOUT v1 não
pode ser reutilizado para desenvolvimento ou tuning.
