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

O produto é local e executado por CLI. Não há frontend, API web, busca vetorial,
embeddings ou acesso web durante a consulta. A URL oficial é proveniência.

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
[arquitetura completa](docs/ARCHITECTURE_MVP2.md).

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
- nenhum runtime web fetch, vetor, embedding ou RRF.

## Requisitos

- Python 3.13 ou superior e `uv`;
- Docker com Docker Compose;
- PostgreSQL 16 via Compose;
- Ollama via Compose, publicado no host em `localhost:11435`.

Ollama nativo no host em `localhost:11434` não é suportado. O download do
modelo é manual e seu armazenamento usa volume Docker.

## Instalação e ambiente

```bash
cp .env.example .env
uv sync --frozen
docker compose up -d db
docker compose --profile llm up -d ollama
docker compose exec ollama ollama pull gemma4:12b
```

```bash
.venv/bin/consultor-juridico --help
docker compose build app
docker compose run --rm app consultor-juridico --help
```

## Execução

```bash
.venv/bin/consultor-juridico db migrate
.venv/bin/consultor-juridico db status
.venv/bin/consultor-juridico corpus --help
.venv/bin/consultor-juridico retrieval --help
.venv/bin/consultor-juridico rag status
```

Uma consulta normativa exige o hash explícito da versão materializada:

```bash
.venv/bin/consultor-juridico ask \
  "Qual é o prazo para a Administração decidir o recurso?" \
  --version-hash <VERSION_HASH> \
  --mode legal-rule \
  --base-url http://localhost:11435
```

Use `--trace` para ranks, evidências, citações e identidades congeladas. Os
grupos da CLI expõem ajuda para aquisição, materialização, auditoria e avaliação.

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

- [Arquitetura do MVP2](docs/ARCHITECTURE_MVP2.md)
- [Experimentos e decisões](docs/EXPERIMENTS_MVP2.md)
- [Estado canônico](docs/STATE.md)
- [Índice documental](docs/README.md)

## MVP1

O MVP1 é preservado pela tag imutável `v0.1.0` apenas como referência histórica.
As lições relevantes estão em `EXPERIMENTS_MVP2.md`; esta branch representa o
MVP2.

## Próxima evolução

Uma eventual `POST_HOLDOUT_METHOD_PHASE` ou MVP3 deverá começar com novo
baseline, hipóteses gerais e datasets DEV independentes. O Blind HOLDOUT v1 não
pode ser reutilizado para desenvolvimento ou tuning.
