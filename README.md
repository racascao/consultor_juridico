# Consultor Jurídico

Mecanismo CLI-first de consulta jurídica baseado em fontes oficiais,
versionadas e rastreáveis. O MVP2 está sendo reconstruído com escopo reduzido;
nesta etapa existe um corpus funcional e auditável, ainda sem mecanismo de
consulta jurídica.

## Estado do projeto

A tag `v0.1.0` preserva o MVP1 e permanece imutável. A branch `mvp-v0.2`, na
versão `0.2.0.dev0`, implementa a Fase 0 com a Lei nº 9.784/1999 como ato
piloto.

```text
MVP2_STATUS: PHASE_0_READY_FOR_MANUAL_PROVENANCE_CHECK
PILOT_LEGAL_ACT: BR-FED-LEI-9784-1999
PARSER: IMPLEMENTED
CORPUS: MATERIALIZED_AND_AUDITABLE
RETRIEVAL: NOT_IMPLEMENTED
FTS: NOT_IMPLEMENTED
EMBEDDINGS: NOT_IMPLEMENTED
LLM: NOT_IMPLEMENTED
```

O PostgreSQL v0.2 é isolado do legado:

```text
database: consultor_juridico_v02
volume:   consultor_juridico_v02_pgdata
host:     localhost:5434
```

O banco e o volume do MVP1 não são migrados nem reutilizados. O baseline
Alembic ativo da branch v0.2 cria somente as tabelas da fundação documental;
as migrations históricas continuam preservadas pela tag `v0.1.0`.

## Arquitetura da Fase 0

```text
Source
  → SourceSnapshot
  → LegalAct
  → ActVersion
  → Provision
  → SearchUnit
  → SearchUnitProvision
```

- `SourceSnapshot.raw_bytes` preserva exatamente a resposta HTTP, com SHA-256
  calculado sobre esses bytes e proteção de imutabilidade no PostgreSQL.
- A aquisição usa `If-None-Match` e `If-Modified-Since` quando existem
  metadados anteriores. `304` reutiliza a captura sem alterar `acquired_at`;
  uma resposta `200` com o mesmo SHA também é idempotente.
- O contrato validado da fonte é `windows-1252`, sempre com decoding estrito.
- O parser `planalto-lei-structural/1` opera em memória e termina o documento
  estrutural no primeiro `</html>`. A cauda dinâmica posterior permanece intacta
  em `raw_bytes`, mas não entra na árvore jurídica.
- `ARTICLE` é o contêiner estrutural; `CAPUT` guarda seu texto normativo. As
  demais classes observadas são `DOCUMENT_ROOT`, `CHAPTER`, `PARAGRAPH` e
  `INCISO`.
- A materialização valida parser, cobertura e projeção antes de uma única
  transação. Falhas causam rollback integral.
- Não existe versão `active`, `current` ou `latest`. Cada `ActVersion` possui
  identidade natural e `version_hash` derivados explicitamente do snapshot e
  das versões do parser e da projeção.
- A projeção `provision-text/1` é intencionalmente simples:
  `SearchUnit.search_text = Provision.citation_text`, sem enriquecimento.
- Reprojeção é offline: recebe um SHA de snapshot persistido e não possui
  cliente HTTP ou fallback remoto.

Os contratos completos estão em
[`docs/corpus/foundation-corpus-v02.md`](docs/corpus/foundation-corpus-v02.md).
A investigação da fonte está em
[`docs/corpus/lei-9784-investigation.md`](docs/corpus/lei-9784-investigation.md).

## Banco e corpus

Com o PostgreSQL v0.2 ativo:

```bash
docker compose up -d db
uv run consultor-juridico db migrate
uv run consultor-juridico db status
```

Adquirir a fonte oficial sem materializá-la:

```bash
uv run consultor-juridico corpus adquirir
```

Materializar ou reprojetar um snapshot explicitamente, sem HTTP:

```bash
uv run consultor-juridico corpus materializar --snapshot-sha <sha256>
uv run consultor-juridico corpus reprojetar --snapshot-sha <sha256>
```

Listar e auditar versões:

```bash
uv run consultor-juridico corpus versoes
uv run consultor-juridico corpus auditar --version-hash <hash>
```

Rastrear uma unidade textual até a captura oficial:

```bash
uv run consultor-juridico corpus rastrear \
  --version-hash <hash> \
  --unit-key <unit_key>
```

## Desenvolvimento

```bash
uv sync
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
```

Os testes automáticos não acessam o Planalto. A integração PostgreSQL usa um
banco descartável indicado por `V02_TEST_DATABASE_URL`.

## Governança e roadmap

A implementação automática da Fase 0 está pronta, mas sua aceitação depende
da conferência humana de cinco amostras distribuídas no documento. A Fase 1
ainda não foi iniciada.

```text
Fase 0: Fundação e Corpus (validação manual de proveniência pendente)
  → Fase 1: Retrieval isolado
  → Gold Evidence
  → Integração
  → DEV
  → HOLDOUT
  → Teste manual
```

A governança do HOLDOUT está documentada em
[`docs/governance/holdout.md`](docs/governance/holdout.md), mas nenhum dataset
DEV ou HOLDOUT foi criado ou lido nesta fase. Não há alegação atual de
qualidade, acurácia ou prontidão do consultor.
