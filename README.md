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

O pipeline documental implementado até a Fase 4C é:

```text
Raw SourceDocument
      ↓
Integrity + Decoder
      ↓
DOM
      ↓
DocumentBlock
      ↓
CF/ADCT Segmentation
      ↓
In-memory Legal Structure Parser
      ↓
Structural Pre-Materialization Audit
      ↓
Materialization Gate
      ↓
Transactional PostgreSQL Materialization
```

O parser produz árvores imutáveis e auditáveis em memória, reconcilia cada
ocorrência normativa com `LegalProvision` e somente materializa após aprovação
do gate estrutural.

A Fase 4B.3.2 corrigiu deterministicamente os 62 blocos numerados antes perdidos
(alíneas com whitespace variante, incisos sem hífen/alfanuméricos e `SEÇÃO V-A`).
O `SCHEMA_MODEL_GAP` foi resolvido pelo modelo identidade/ocorrência: redações
históricas compartilham identidade normativa sem perder texto, ordem ou
proveniência. A reauditoria da captura real encerrou com zero blockers.

A Fase 4C adaptou o parser, reconciliou `identity_key`, atualizou a auditoria e
materializou CF/88 + ADCT atomicamente. A segunda execução retorna
`ALREADY_PARSED`, sem duplicar versões, provisions ou occurrences.

A Migration `005_normative_identity_occurrences` implementou a integridade física
de mesmo ato: `LegalElement.legal_act_id` é uma redundância controlada, protegida
por FKs compostas para `LegalVersion` e `LegalProvision`. O banco associa cada
ocorrência normativa à identidade do mesmo ato e tipo.

```text
LegalAct
├── LegalProvision identity tree
└── LegalVersion
    └── LegalElement occurrence tree
        └── references LegalProvision
```

O Alembic usa `VARCHAR(64)` em `alembic_version.version_num` desde a Migration
005, pois seu revision ID possui 34 caracteres. A ampliação é monotônica e
permanece após downgrade para 004.

## Modelagem do banco de dados

O banco é o núcleo de rastreabilidade do sistema. A modelagem separa deliberadamente captura documental, processamento técnico, estrutura jurídica, indexação, evidência e resposta, evitando que uma única entidade acumule responsabilidades incompatíveis.

![Modelo ERD](docs/consultor_juridico_erd.png)

A cadeia principal de custódia é:

Source
  ↓
SourceDocument
  ↓
ParsingRun
      ↓
LegalVersion
      ↓
LegalElement occurrence
      ↓
LegalProvision identity
  ↓
Chunk
  ↓
EvidenceItem
  ↓
Citation
  ↓
Claim

### Fonte e captura física

Source representa a origem oficial. SourceDocument representa uma captura física obtida dessa fonte. O HTML é armazenado em raw_bytes (BYTEA) sem canonicalização, e content_hash_sha256 é calculado sobre exatamente os mesmos bytes persistidos. Assim, a captura permanece auditável e pode ser comprovada criptograficamente.

A unicidade por (source_id, content_hash_sha256) é uma proteção adicional de idempotência. ETag e Last-Modified permanecem como metadados da aquisição HTTP e servem ao conditional GET; o SHA-256 tem uma função diferente: provar a integridade dos bytes armazenados.

### ParsingRun: captura não é parsing

ParsingRun separa o documento físico do processo técnico que o interpreta. Sua identidade lógica é (source_document_id, parser_name, parser_version).

Isso permite saber qual parser processou uma captura, em qual versão e com qual resultado (RUNNING, COMPLETED ou FAILED). A separação também impede confundir uma mudança do parser com uma mudança real da fonte oficial.

### LegalAct e LegalVersion

LegalAct representa a identidade abstrata de uma norma. CF/88 e ADCT são tratados como atos jurídicos distintos, embora sejam obtidos da mesma captura física.

LegalVersion representa a versão jurídica derivada de uma captura por uma determinada ParsingRun.

O schema mantém source_document_id e parsing_run_id de forma intencional. Uma FK composta garante que uma LegalVersion não possa apontar para um SourceDocument diferente daquele processado pelo seu ParsingRun.

A unicidade (parsing_run_id, legal_act_id) impede duplicação do mesmo ato dentro do mesmo processamento. Um índice único parcial garante no máximo uma versão ativa para consulta por LegalAct.

### LegalElement: árvore jurídica versionada

LegalElement materializa a estrutura normativa dentro de uma LegalVersion.

A taxonomia congelada no schema 004 inclui:

DOCUMENT_ROOT, PREAMBLE, TITLE, CHAPTER, SECTION, SUBSECTION, ARTICLE, CAPUT, PARAGRAPH, INCISO, ALINEA, ITEM e NOTE.

parent_id representa a hierarquia. Uma FK composta com legal_version_id impede que um elemento tenha como pai um elemento de outra versão.

document_order representa a ordem global e determinística dos elementos dentro da versão. Hierarquia e ordem são conceitos independentes: parent_id informa quem contém quem; document_order informa em que ordem documental os elementos aparecem.

source_locator registra proveniência factual, como o block_index do HTML de origem. parser_metadata registra decisões técnicas do parser, como estrutura sintética, links preservados ou cobertura de strike.

### Status do texto e papel do conteúdo

O modelo separa duas dimensões.

text_status:

- CURRENT

- HISTORICAL

- REVOKED

- UNRESOLVED

- NOT_APPLICABLE

content_role:

- NORMATIVE

- AMENDMENT_NOTE

- REFERENCE_NOTE

- EDITORIAL_NOTE

Uma redação normativa histórica, por exemplo, pode ser HISTORICAL + NORMATIVE, enquanto uma nota editorial recebe papel não normativo e NOT_APPLICABLE.

A existência de UNRESOLVED é deliberada: quando a fonte não permite determinar com segurança o status, o sistema registra a incerteza em vez de inferir vigência.

### Chunk e relação N com LegalElement

Chunk é a unidade futura de retrieval e pertence a uma LegalVersion.

A tabela ChunkLegalElement implementa uma relação N entre chunks e elementos jurídicos. Isso evita congelar a regra simplista “um artigo = um chunk” e permite que um chunk agregue contexto mantendo rastreabilidade para os dispositivos que o originaram.

### FTS e embeddings

Chunk.tsv_content suporta Full-Text Search do PostgreSQL com índice GIN.

Embedding armazena vetores e identifica explicitamente provider_name, model_name, model_version e dimensions. Assim, múltiplos modelos podem ser comparados para o mesmo chunk sem misturar silenciosamente espaços vetoriais diferentes.

A constraint de dimensão garante coerência entre a dimensão declarada e a dimensão física do vetor.

### EvidenceSet e EvidenceItem

EvidenceSet representa o conjunto fechado de evidências selecionadas para uma consulta. Registra a pergunta, estratégia de retrieval, estado de validação e metadados do processo.

EvidenceItem liga uma evidência ao Chunk e ao LegalElement e guarda text_snapshot, isto é, a cópia exata do texto que foi entregue ao LLM.

Esse snapshot é essencial para reprodutibilidade: mesmo que legislação, parser ou índice evoluam, continua sendo possível saber qual texto fundamentou uma resposta passada.

### Claim e Citation

Claim representa uma afirmação produzida pela camada de geração.

Citation liga essa afirmação a um EvidenceItem.

A integridade entre Citation, EvidenceItem e EvidenceSet é protegida por FK composta. O banco rejeita uma citação que declare pertencer ao conjunto B enquanto referencia uma evidência pertencente ao conjunto A.

Isso faz com que parte importante da validação de citações seja garantida fisicamente pelo PostgreSQL.

### Cadeia de custódia

O objetivo final do modelo é permitir a navegação:

Claim
  ↓
Citation
  ↓
EvidenceItem
  ↓
Chunk
  ↓
LegalElement
  ↓
LegalVersion
  ↓
SourceDocument
  ↓
Source

Assim, o LLM nunca é a fonte de verdade. Cada afirmação fundamentada poderá ser rastreada até o fragmento jurídico, a captura física e a fonte oficial.

### Por que há tantas constraints físicas?

O projeto prefere colocar no banco as invariantes que são simples, estáveis e relacionais. Entre elas:

documento não pode apontar para fonte inexistente;

LegalVersion e ParsingRun devem referenciar a mesma captura;

pai e filho devem pertencer à mesma LegalVersion;

document_order não pode se repetir na mesma versão;

só pode existir uma versão ativa por LegalAct;

só pode existir um DOCUMENT_ROOT por versão;

taxonomias e combinações role/status são verificadas;

dimensão declarada do embedding deve corresponder ao vetor;

Citation e EvidenceItem devem pertencer ao mesmo EvidenceSet.

Regras que exigem interpretação temporal ou contextual permanecem na aplicação em vez de serem escondidas em triggers.

## Roadmap

O desenvolvimento do projeto segue uma estratégia incremental, com checkpoints de arquitetura, implementação, testes e auditoria antes do avanço para a próxima etapa.

### Fundação e infraestrutura

- [x] **Fase 0 — Fundação do projeto**
  - [x] Estrutura `src/` e `tests/`
  - [x] `pyproject.toml`
  - [x] `uv.lock`
  - [x] Ambiente isolado em `.venv`
  - [x] CLI com Typer + Rich
  - [x] Configuração com Pydantic Settings
  - [x] Ruff
  - [x] Pytest
  - [x] Política de zero dependências Python globais

- [x] **Fase 1 — Docker e infraestrutura local**
  - [x] Dockerfile
  - [x] Docker Compose
  - [x] PostgreSQL 16
  - [x] pgvector
  - [x] Ollama
  - [x] Healthchecks
  - [x] Volumes persistentes
  - [x] Execução da CLI em container

### Modelo de dados e rastreabilidade

- [x] **Fase 2A — Modelagem relacional**
  - [x] `Source`
  - [x] `SourceDocument`
  - [x] `LegalAct`
  - [x] `LegalVersion`
  - [x] `LegalElement`
  - [x] `Chunk`
  - [x] `Embedding`
  - [x] `EvidenceSet`
  - [x] `EvidenceItem`
  - [x] `Claim`
  - [x] `Citation`
  - [x] Cadeia de rastreabilidade jurídica

- [x] **Fase 2B — SQLAlchemy, Alembic e PostgreSQL**
  - [x] Modelos ORM
  - [x] Migration `001_initial_schema`
  - [x] Migration `002_schema_corrections`
  - [x] Integridade de chaves estrangeiras
  - [x] FTS com PostgreSQL
  - [x] suporte a `pgvector`
  - [x] Integridade `Citation → EvidenceItem → EvidenceSet`
  - [x] Auditoria do schema
  - [x] Testes de upgrade/downgrade
  - [x] Validação em Docker

### Ingestão da fonte oficial

- [x] **Fase 3 — Ingestão e Raw Storage**
  - [x] Adapter do Portal do Planalto
  - [x] Download HTTP com `httpx`
  - [x] User-Agent configurável
  - [x] Timeouts, retries e backoff
  - [x] Preservação byte a byte em `BYTEA`
  - [x] SHA-256 da captura
  - [x] Migration `003_ingestion_raw_storage`
  - [x] `ETag`
  - [x] `Last-Modified`
  - [x] Conditional GET
  - [x] Fluxo real `200 CREATED → 304 ALREADY_KNOWN`
  - [x] Idempotência
  - [x] Teste real contra o Planalto
  - [x] CF/88 + ADCT preservados como uma única captura física
  - [x] Separação entre captura documental e versão jurídica

### Parsing constitucional

- [x] **Fase 4A — Investigação estrutural do HTML**
  - [x] Análise da captura real
  - [x] Identificação de encoding `Windows-1252`
  - [x] Inventário estrutural do DOM
  - [x] Análise de CF/88 e ADCT
  - [x] Identificação de redações históricas
  - [x] Identificação de conteúdo riscado
  - [x] Análise de notas e referências
  - [x] Definição inicial das golden fixtures

- [x] **Fase 4A.1 — Congelamento do modelo de parsing**
  - [x] CF/88 e ADCT como `LegalAct` distintos
  - [x] CAPUT explícito
  - [x] `document_order`
  - [x] `text_status`
  - [x] `content_role`
  - [x] `ParsingRun`
  - [x] Estratégia de reparse
  - [x] Estratégia transacional
  - [x] Proveniência do parsing

- [x] **Fase 4A.2 — Revisão de consistência pré-migration**
  - [x] Cardinalidades finais
  - [x] FKs compostas
  - [x] Máquina de estados de `ParsingRun`
  - [x] Fronteiras transacionais TX1/TX2/TX3
  - [x] Taxonomia jurídica `INCISO / ALINEA / ITEM`
  - [x] Semântica de ARTICLE/CAPUT
  - [x] Política de downgrade

- [x] **Migration 004 — Frozen Parsing Model**
  - [x] Tabela `parsing_runs`
  - [x] Alterações em `legal_versions`
  - [x] Alterações em `legal_elements`
  - [x] `document_order`
  - [x] `text_status`
  - [x] `content_role`
  - [x] `source_locator`
  - [x] `parser_metadata`
  - [x] Integridade pai-filho na mesma `LegalVersion`
  - [x] Índice de versão ativa
  - [x] Ciclo `003 → 004 → 003 → 004`
  - [x] Validação Docker

- [x] **Fase 4B.1 — Decoder e DOM íntegro**
  - [x] Validação SHA-256 antes do decoding
  - [x] Decoding estrito `Windows-1252`
  - [x] BeautifulSoup + `html.parser`
  - [x] Preservação do conteúdo após `</html>` prematuro
  - [x] Métricas estruturais do DOM
  - [x] Teste de regressão da captura real
  - [x] Determinismo do pipeline

- [x] **Fase 4B.2 — Segmentação CF/ADCT e blocos documentais**
  - [x] `DocumentBlock`
  - [x] `block_index` determinístico
  - [x] Preservação de anchors e links
  - [x] Marcação factual de `<strike>`
  - [x] Segmentação em:
    - [x] `leading`
    - [x] CF/88
    - [x] transição
    - [x] ADCT
    - [x] `trailing`
  - [x] Rejeição da falsa ocorrência de ADCT no menu
  - [x] Preservação do Art. 250 na CF
  - [x] Preservação do Art. 138 no ADCT
  - [x] Fingerprint diagnóstico da projeção
  - [x] Integração real somente leitura

- [x] **Fase 4B.3 — Parser jurídico estrutural em memória**
  - [x] Golden fixtures estruturais
  - [x] `DOCUMENT_ROOT`
  - [x] `PREAMBLE`
  - [x] `TITLE`
  - [x] `CHAPTER`
  - [x] `SECTION`
  - [x] `SUBSECTION`
  - [x] `ARTICLE`
  - [x] `CAPUT`
  - [x] `PARAGRAPH`
  - [x] `INCISO`
  - [x] `ALINEA`
  - [x] `ITEM`
  - [x] `NOTE`
  - [x] `text_status`
  - [x] `content_role`
  - [x] Proveniência por bloco
  - [x] Auditoria de cobertura documental

- [x] **Fase 4B.3.1 — Auditoria estrutural pré-materialização**
  - [x] Auditoria de ARTICLE/CAPUT, ordem, hierarquia e proveniência
  - [x] Auditoria de histórico, revogação, strike, notas e cobertura
  - [x] Diagnóstico dos 66 blocos não classificados
  - [x] Findings tipados e fingerprint determinístico
  - [x] Gate para 4B.4: `BLOCKED_FOR_MATERIALIZATION`

- [x] **Fase 4B.3.2 — Correção dos blockers estruturais e revalidação**
  - [x] Reconhecimento dos padrões numerados perdidos
  - [x] Diagnóstico de strike ancestral
  - [x] Reauditoria determinística
  - [x] Gate 4B.4: `BLOCKED_FOR_MATERIALIZATION` (`SCHEMA_MODEL_GAP`)

- [x] **Fase 4B.3.3 — Modelagem de identidade normativa e redações históricas**
  - [x] Separação `LegalProvision` (identidade) / `LegalElement` (ocorrência)
  - [x] Especificação da Migration 005
  - [x] Gate 4B.4 permanece bloqueado

- [x] **Fase 4B.3.3.1 — Consistência física pré-Migration 005**
  - [x] `LegalElement.legal_act_id` como redundância controlada
  - [x] FKs compostas de versão/ato e provision/ato/tipo
  - [x] Gate 4B.4 bloqueado até Migration 005 + Fase 4B.3.4

- [x] **Migration 005 — identidade normativa e ocorrências**
  - [x] Tabela `legal_provisions` e árvore de identidades
  - [x] FKs compostas de mesmo ato e tipo
  - [x] Ciclo isolado `004 → 005 → 004 → 005`
  - [x] Alembic `version_num` ampliado monotonicamente para `VARCHAR(64)`

- [x] **Fase 4B.3.4 — adaptação do parser e reauditoria**

- [x] **Fase 4C — parser final, identidade normativa e materialização**
  - [x] `identity_key` determinística e reconciliação de `LegalProvision`
  - [x] Gate real `APPROVED_FOR_MATERIALIZATION` sem blockers
  - [x] Materialização transacional CF/88 + ADCT
  - [x] Rollback e retry validados em PostgreSQL descartável
  - [x] Idempotência `ALREADY_PARSED`

- [x] **Fase 4B.4 — Materialização transacional**
  - [x] `ParsingRun`
  - [x] LegalAct CF/88
  - [x] LegalAct ADCT
  - [x] LegalVersions e LegalElements
  - [x] TX1 / TX2 / TX3
  - [x] Idempotência `ALREADY_PARSED`
  - [x] Retry de ParsingRun FAILED
  - [x] Ativação conjunta CF/ADCT

- [x] **Fase 4B.5 / Fase 4C — Parsing integral e auditoria**
  - [x] Parsing da captura constitucional completa
  - [x] Validação de invariantes
  - [x] Auditoria de cobertura
  - [x] Auditoria de texto histórico/revogado
  - [x] Auditoria de notas editoriais
  - [x] Auditoria CF/ADCT
  - [x] Reprocessamento determinístico

### Indexação e recuperação

- [ ] **Fase 5 — Chunking e Retrieval**
  - [ ] Estratégia de chunking
  - [ ] `Chunk ↔ LegalElement`
  - [ ] FTS PostgreSQL
  - [ ] Modelo de embeddings
  - [ ] Geração local de embeddings
  - [ ] pgvector
  - [ ] Benchmark de índice vetorial
  - [ ] LexicalRetriever
  - [ ] SemanticRetriever
  - [ ] Reciprocal Rank Fusion (RRF)
  - [ ] Reranking
  - [ ] RetrievalCandidate

### Evidências e RAG

- [ ] **Fase 6 — Evidence Engine, LLM e Citation Validation**
  - [ ] `EvidenceBuilder`
  - [ ] `EvidenceValidator`
  - [ ] `EvidenceSet`
  - [ ] `EvidenceItem`
  - [ ] Snapshot das evidências
  - [ ] Integração com Ollama
  - [ ] Saída estruturada do LLM
  - [ ] Claims
  - [ ] Citations
  - [ ] `CitationValidator`
  - [ ] Regeneração controlada
  - [ ] Fallback por evidência insuficiente
  - [ ] Comando CLI `consult`

### Avaliação e aceite

- [ ] **Fase 7 — Avaliação e validação final**
  - [ ] Dataset jurídico de avaliação
  - [ ] Métricas de retrieval
  - [ ] Métricas de grounding
  - [ ] Validação de evidências
  - [ ] Validação de citações
  - [ ] Testes contra perguntas conhecidas
  - [ ] Benchmark de modelos locais
  - [ ] Benchmark de embeddings
  - [ ] Validação CPU-only
  - [ ] Testes em ambiente Docker limpo
  - [ ] Critérios finais de aceite do MVP1

### Evoluções posteriores ao MVP1

- [ ] Leis Ordinárias
- [ ] Leis Complementares
- [ ] Emendas Constitucionais como corpus próprio
- [ ] Decretos
- [ ] Relacionamentos entre normas
- [ ] Histórico legislativo ampliado
- [ ] Expansão do corpus jurídico


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

## Ingestão documental

A Fase 3 captura a CF/88 e o ADCT como um único documento físico oficial, sem
parsing ou decoding textual:

```bash
uv run consultor-juridico ingest constitution
uv run consultor-juridico ingest status
```

Os bytes canônicos são armazenados em PostgreSQL `BYTEA` e identificados por
SHA-256 dentro da fonte. Consulte `docs/30-ingestao-planalto.md` para a política
HTTP, idempotência e execução da integração real opt-in.

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
