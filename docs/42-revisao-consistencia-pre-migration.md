# Revisão de consistência pré-migration 004

## 1. Objetivo e inconsistências revisadas

Este checkpoint torna mecânica a futura implementação de
`004_frozen_parsing_model`. Ele não reabre a arquitetura da Fase 4A.1 e não
implementa DDL ou parser.

O schema físico foi confirmado em `003_ingestion_raw_storage`. As tabelas
`legal_versions` e `legal_elements` estão vazias. Foram corrigidas estas
ambiguidades residuais:

1. `LegalVersion.source_document_id` e `parsing_run_id` formavam dois caminhos
   sem nomes e regras físicas totalmente especificados;
2. ParsingRun era chamado de execução, embora a unique e o retry indiquem um
   processamento lógico com várias tentativas possíveis;
3. a descrição transacional não separava claramente TX1, TX2 e TX3;
4. `ITEM=inciso`, `LETTER=alínea`, `SUBITEM=item` era semanticamente perigoso;
5. CAPUT explícito não tinha proveniência sintética completamente definida;
6. nullability, conteúdo de elementos estruturais, root, nomes de constraints e
   índices ainda exigiam decisões durante a migration;
7. o downgrade precisava de precondition operacional exata.

## 2. Decisões finais

- manter `LegalVersion.source_document_id NOT NULL` e sua FK direta;
- adicionar `LegalVersion.parsing_run_id NOT NULL`;
- alinhar os dois caminhos por uma única FK composta para ParsingRun;
- representar ParsingRun como processamento lógico, não tentativa individual;
- permitir retry `FAILED → RUNNING` na mesma linha;
- não criar `ParsingAttempt` nem triggers;
- preservar exatamente uma versão CF88 e uma ADCT por run concluído como
  invariante do serviço, não como cardinalidade fixa no schema;
- usar taxonomia jurídica `INCISO`, `ALINEA`, `ITEM`;
- manter CAPUT explícito e sintético, com texto somente no CAPUT;
- exigir textos não vazios para todo LegalElement persistido;
- garantir no máximo uma raiz e uma versão ativa por índices parciais;
- recusar downgrade quando houver qualquer dado derivado da camada de parsing.

## 3. Relações, autoridade e cardinalidades

```text
SourceDocument 1 ── N ParsingRun
ParsingRun      1 ── N LegalVersion
LegalAct        1 ── N LegalVersion
LegalVersion    1 ── N LegalElement
LegalElement    0..1 ── N LegalElement
```

Autoridade de cada relação:

- `ParsingRun.source_document_id`: captura processada pelo algoritmo;
- `LegalVersion.parsing_run_id`: processamento lógico que materializou a versão;
- `LegalVersion.source_document_id`: proveniência documental direta usada pela
  cadeia de auditoria existente;
- `LegalElement.legal_version_id`: versão e, transitivamente, run produtor.

A redundância em LegalVersion é intencional e fisicamente consistente:

```text
parsing_runs:
  UNIQUE(id, source_document_id)

legal_versions:
  FOREIGN KEY (parsing_run_id, source_document_id)
  REFERENCES parsing_runs(id, source_document_id)
```

A FK simples já existente
`legal_versions.source_document_id → source_documents.id` permanece. Assim, os
dois caminhos chegam obrigatoriamente ao mesmo SourceDocument.

`UNIQUE(parsing_run_id, legal_act_id)` garante no máximo uma versão de cada ato
por run. “Run constitucional COMPLETED possui exatamente CF88 + ADCT” permanece
invariante transacional da aplicação. Codificar quantidade dois no banco
acoplaria ParsingRun ao corpus atual e exigiria trigger ou assertion externa.

## 4. Semântica e máquina de estados de ParsingRun

ParsingRun representa o **processamento lógico** definido por:

```text
(source_document_id, parser_name, parser_version)
```

Não representa cada tentativa física. Logs são a observabilidade de tentativas;
`metadata.retry_count` e `metadata.last_failure` guardam somente o resumo lógico.

Transições permitidas:

```text
novo      → RUNNING
RUNNING   → COMPLETED
RUNNING   → FAILED
FAILED    → RUNNING
```

Transições proibidas:

```text
COMPLETED → RUNNING
COMPLETED → FAILED
FAILED    → COMPLETED
```

O banco valida valores e coerência status/timestamp. O serviço executa a máquina
temporal por updates condicionais, por exemplo `WHERE status='FAILED'` no retry.
Não haverá trigger PostgreSQL.

No retry:

- reutilizar a mesma PK;
- definir `status=RUNNING`;
- redefinir `started_at=now()`;
- definir `finished_at=NULL`;
- incrementar `metadata.retry_count`;
- manter apenas resumo da falha anterior no metadata/log, sem histórico
  relacional de tentativas.

## 5. Fronteiras transacionais

### TX1 — início lógico

Criar o run ou transicionar FAILED para RUNNING, definir timestamps e COMMIT.
Uma unique natural resolve concorrência. COMPLETED retorna `ALREADY_PARSED`;
RUNNING retorna `PARSING_IN_PROGRESS`.

### Parsing em memória

Verificar SHA-256, carregar `raw_bytes`, decodificar, construir as duas árvores e
validar invariantes. Nenhuma LegalVersion ou LegalElement é persistida.

### TX2 — materialização atômica

Em uma única transação:

1. criar/buscar LegalAct CF88 e ADCT;
2. criar LegalVersion CF88 e ADCT inativas;
3. inserir ambas as árvores;
4. validar root, tipos, ordem, cobertura, status e cardinalidade CF+ADCT;
5. desativar as versões anteriores dos dois atos;
6. ativar conjuntamente as duas novas versões;
7. definir ParsingRun `COMPLETED` e `finished_at=now()`;
8. COMMIT.

Para satisfazer o índice de versão ativa, as antigas são desativadas antes de as
novas serem ativadas, dentro da mesma transação. Outros consumidores não veem o
estado intermediário.

### TX3 — falha

Se parsing em memória ou TX2 falhar, TX2 sofre ROLLBACK integral. Em nova
transação, atualizar RUNNING para FAILED, definir `finished_at=now()`, registrar
diagnóstico e COMMIT. Nenhuma versão ou elemento parcial sobrevive.

## 6. Taxonomia jurídica final

```text
DOCUMENT_ROOT
PREAMBLE
TITLE
CHAPTER
SECTION
SUBSECTION
ARTICLE
CAPUT
PARAGRAPH
INCISO
ALINEA
ITEM
NOTE
```

- INCISO corresponde ao numeral romano;
- ALINEA corresponde à letra;
- ITEM corresponde à subdivisão normalmente numérica da alínea;
- não existem `LETTER` ou `SUBITEM`;
- `number_label` preserva o rótulo observado, como `IV`, `a`, `1` ou `116-A`.

Hierarquia mínima:

```text
ARTICLE
├── CAPUT
├── INCISO                 # quando subdivide o caput
│   ├── ALINEA
│   │   └── ITEM
└── PARAGRAPH
    └── INCISO             # quando subdivide o parágrafo
        └── ALINEA
            └── ITEM
```

Compatibilidade pai-tipo completa fica no parser/testes; não será codificada em
um CHECK complexo.

## 7. ARTICLE, CAPUT e proveniência

ARTICLE é o container estrutural e a identidade/localização do artigo:

- `raw_text`: somente o rótulo factual, por exemplo `Art. 116-A.`;
- `normalized_text`: normalização mecânica desse rótulo;
- não duplica o conteúdo do CAPUT, incisos ou parágrafos.

CAPUT contém todo o texto normativo entre o rótulo do artigo e a primeira
subdivisão/nota separada:

- existe exatamente uma vez por ARTICLE;
- artigo simples continua sendo `ARTICLE → CAPUT`;
- não implica uma tag `<caput>` no HTML;
- ARTICLE e CAPUT podem apontar para o mesmo bloco HTML factual;
- `CAPUT.source_locator` aponta para esse bloco real;
- `CAPUT.parser_metadata.synthetic_structure=true` registra que o nó jurídico
  foi sintetizado pelo parser.

`source_locator` contém localização factual. `parser_metadata` contém decisões
técnicas. Nenhuma proveniência inexistente é inventada.

Parágrafos são filhos de ARTICLE, não de CAPUT. Incisos que subdividem o caput
são filhos de ARTICLE; os que subdividem parágrafo são filhos de PARAGRAPH.

## 8. Constraints físicas finais

Todos os nomes abaixo são obrigatórios na futura migration.

### 8.1 `parsing_runs`

| Nome | Definição |
|---|---|
| `pk_parsing_runs` | `PRIMARY KEY (id)` |
| `fk_parsing_runs_source_document_id_source_documents` | FK `source_document_id → source_documents.id ON DELETE RESTRICT ON UPDATE NO ACTION` |
| `uq_parsing_runs_source_parser` | `UNIQUE(source_document_id, parser_name, parser_version)` |
| `uq_parsing_runs_id_source_document` | `UNIQUE(id, source_document_id)` |
| `ck_parsing_runs_status` | status em RUNNING, COMPLETED, FAILED |
| `ck_parsing_runs_status_finished_at` | RUNNING exige `finished_at IS NULL`; terminal exige não nulo |

### 8.2 `legal_versions`

Manter:

- `fk_legal_versions_source_document_id_source_documents`, com
  `ON DELETE RESTRICT ON UPDATE NO ACTION`;
- `fk_legal_versions_legal_act_id_legal_acts`.

Adicionar:

| Nome | Definição |
|---|---|
| `fk_legal_versions_parsing_run_source_document` | FK `(parsing_run_id, source_document_id) → parsing_runs(id, source_document_id) ON DELETE RESTRICT ON UPDATE NO ACTION` |
| `uq_legal_versions_parsing_run_legal_act` | `UNIQUE(parsing_run_id, legal_act_id)` |
| `uq_legal_versions_one_active_per_act` | índice único parcial em `legal_act_id WHERE is_active_for_query IS TRUE` |
| `ix_legal_versions_source_document_id` | índice não único em `source_document_id` |

Não criar FK simples adicional de `parsing_run_id`; a composta já garante a
existência do run e a igualdade documental. A unique por run/ato possui
`parsing_run_id` como prefixo e atende buscas por run.

No ORM, `LegalVersion` deve declarar a FK por `ForeignKeyConstraint`, não por
`ForeignKey` isolada em `parsing_run_id`. As relações
`LegalVersion.parsing_run` e `ParsingRun.legal_versions` devem informar
explicitamente as duas colunas da junção. A relação direta
`LegalVersion.source_document` continua usando somente
`source_document_id`; `foreign_keys` e, se necessário, `overlaps` devem ser
declarados para que o SQLAlchemy não escolha uma junção ambígua nem tente
sincronizar o documento por dois caminhos independentes.

DDL conceitual do índice de ativação:

```sql
CREATE UNIQUE INDEX uq_legal_versions_one_active_per_act
ON legal_versions (legal_act_id)
WHERE is_active_for_query IS TRUE;
```

PostgreSQL suporta esse índice. CF88 e ADCT possuem `legal_act_id` diferentes e
podem ser ativados na mesma TX2.

### 8.3 `legal_elements`

| Nome | Definição |
|---|---|
| `uq_legal_elements_version_document_order` | `UNIQUE(legal_version_id, document_order)` |
| `uq_legal_elements_id_legal_version` | `UNIQUE(id, legal_version_id)` |
| `fk_legal_elements_parent_version_composite` | FK `(parent_id, legal_version_id) → legal_elements(id, legal_version_id) ON DELETE CASCADE ON UPDATE NO ACTION` |
| `ck_legal_elements_no_self_parent` | manter `parent_id <> id` |
| `ck_legal_elements_document_order_positive` | `document_order >= 1` |
| `ck_legal_elements_element_type` | enumeração textual da seção 6 |
| `ck_legal_elements_text_status` | CURRENT, HISTORICAL, REVOKED, UNRESOLVED, NOT_APPLICABLE |
| `ck_legal_elements_content_role` | NORMATIVE, AMENDMENT_NOTE, REFERENCE_NOTE, EDITORIAL_NOTE |
| `ck_legal_elements_role_status` | NORMATIVE não aceita NOT_APPLICABLE; demais roles exigem NOT_APPLICABLE |
| `ck_legal_elements_note_role` | NOTE se e somente se role não é NORMATIVE |
| `ck_legal_elements_root_shape` | root exige parent NULL, order 1, NORMATIVE/CURRENT; demais exigem parent não nulo |
| `ck_legal_elements_number_label` | tipos numerados exigem label não vazio; demais permitem NULL |
| `ck_legal_elements_raw_text_nonempty` | `btrim(raw_text) <> ''` |
| `ck_legal_elements_normalized_text_nonempty` | `btrim(normalized_text) <> ''` |
| `ck_legal_elements_source_locator_object` | JSON object com `block_index` numérico |
| `ck_legal_elements_parser_metadata_object` | NULL ou JSON object |
| `uq_legal_elements_one_root_per_version` | índice único parcial por versão onde tipo é DOCUMENT_ROOT |

FK composta e NULL: no PostgreSQL, se `parent_id IS NULL`, a FK com MATCH SIMPLE
não exige correspondência. `ck_legal_elements_root_shape` restringe esse caso a
DOCUMENT_ROOT. O índice parcial garante no máximo uma raiz; a aplicação garante
que ela existe antes do commit.

CHECKs conceituais exatos:

```sql
element_type IN (
  'DOCUMENT_ROOT', 'PREAMBLE', 'TITLE', 'CHAPTER', 'SECTION',
  'SUBSECTION', 'ARTICLE', 'CAPUT', 'PARAGRAPH', 'INCISO',
  'ALINEA', 'ITEM', 'NOTE'
)

text_status IN (
  'CURRENT', 'HISTORICAL', 'REVOKED', 'UNRESOLVED', 'NOT_APPLICABLE'
)

content_role IN (
  'NORMATIVE', 'AMENDMENT_NOTE', 'REFERENCE_NOTE', 'EDITORIAL_NOTE'
)

(
  (content_role = 'NORMATIVE' AND text_status <> 'NOT_APPLICABLE') OR
  (content_role <> 'NORMATIVE' AND text_status = 'NOT_APPLICABLE')
)

(
  (element_type = 'NOTE' AND content_role <> 'NORMATIVE') OR
  (element_type <> 'NOTE' AND content_role = 'NORMATIVE')
)

(
  (
    element_type = 'DOCUMENT_ROOT'
    AND parent_id IS NULL
    AND document_order = 1
    AND content_role = 'NORMATIVE'
    AND text_status = 'CURRENT'
  ) OR (
    element_type <> 'DOCUMENT_ROOT'
    AND parent_id IS NOT NULL
  )
)

(
  element_type NOT IN (
    'TITLE', 'CHAPTER', 'SECTION', 'SUBSECTION', 'ARTICLE',
    'PARAGRAPH', 'INCISO', 'ALINEA', 'ITEM'
  ) OR (number_label IS NOT NULL AND btrim(number_label) <> '')
)

jsonb_typeof(source_locator) = 'object'
AND source_locator ? 'block_index'
AND jsonb_typeof(source_locator -> 'block_index') = 'number'

parser_metadata IS NULL OR jsonb_typeof(parser_metadata) = 'object'
```

## 9. Nullability e conteúdo de LegalElement

| Campo | Regra final |
|---|---|
| `id` | UUID NOT NULL, PK |
| `legal_version_id` | UUID NOT NULL |
| `parent_id` | NULL somente em DOCUMENT_ROOT |
| `element_type` | VARCHAR(50) NOT NULL |
| `number_label` | NULL para root, preâmbulo, CAPUT e NOTE; obrigatório nos tipos enumerados no CHECK; outros estruturais podem usar NULL |
| `document_order` | BIGINT NOT NULL, sem default |
| `raw_text` | TEXT NOT NULL e não vazio |
| `normalized_text` | TEXT NOT NULL e não vazio |
| `text_status` | VARCHAR(20) NOT NULL, default `UNRESOLVED` |
| `content_role` | VARCHAR(30) NOT NULL, default `NORMATIVE` |
| `path` | VARCHAR(500) NULL; auxiliar |
| `source_locator` | JSONB NOT NULL, sem default |
| `parser_metadata` | JSONB NULL |
| `created_at` | TIMESTAMPTZ NOT NULL, default `now()` |

Todo elemento possui texto identificável: root usa o nome oficial do ato;
ARTICLE usa seu rótulo; divisões usam marcador/rubrica; CAPUT e subdivisões usam
texto normativo; NOTE usa o texto editorial. Por isso não se armazenam strings
vazias e `normalized_text` deixa de ser nullable.

DOCUMENT_ROOT possui:

- `parent_id=NULL`;
- `document_order=1`;
- `content_role=NORMATIVE`;
- `text_status=CURRENT`;
- `raw_text` com o nome oficial observado/associado ao domínio;
- `normalized_text` com sua normalização mecânica;
- `number_label=NULL`;
- locator apontando para o marcador factual CF ou ADCT.

## 10. Política final de downgrade 004 → 003

### 10.1 Upgrade

A futura 004 deve abortar antes de DDL se `legal_versions` ou `legal_elements`
contiverem linhas. Não existe backfill aprovado para `parsing_run_id`, status,
ordem ou proveniência. `sources` e `source_documents` podem permanecer
preenchidos e não são tocados.

### 10.2 Precondition do downgrade

Downgrade é permitido somente quando:

```text
parsing_runs = 0
legal_versions = 0
legal_elements = 0
```

Análise separada:

- ParsingRun não possui representação em 003; qualquer linha seria perdida;
- LegalVersion 004 possui vínculo e proveniência de run não representáveis em
  003;
- LegalElement 004 possui ordem, status e proveniência sem conversão fiel para
  `ordinal` e `is_revoked`.

Assim, qualquer uma dessas linhas é dado derivado não conversível e causa erro
explícito. Source e SourceDocument não bloqueiam downgrade. Isso permite, com a
captura real preservada:

```text
003 → 004 → 003 → 004
```

### 10.3 Ordem inversa

Com a precondition satisfeita:

1. remover `uq_legal_elements_one_root_per_version`;
2. remover CHECKs e uniques novos de LegalElement;
3. remover `fk_legal_elements_parent_version_composite`;
4. restaurar `fk_legal_elements_parent_id_legal_elements` simples;
5. recriar `ordinal INTEGER NULL`;
6. recriar `is_revoked BOOLEAN NOT NULL DEFAULT false`;
7. tornar `normalized_text` novamente nullable;
8. remover `document_order`, `text_status`, `content_role`, `source_locator` e
   `parser_metadata`;
9. remover `uq_legal_versions_one_active_per_act` e
   `ix_legal_versions_source_document_id`;
10. remover FK e unique novas de LegalVersion;
11. restaurar default `true` de `is_active_for_query`;
12. remover `parsing_run_id`;
13. remover `parsing_runs` e todas as suas constraints.

O resultado deve coincidir com o catálogo físico de 003, inclusive nomes das
constraints existentes.

## 11. Cenários validados

### A — primeira execução

R1 é único por X/parser/v1. As duas versões usam o mesmo documento pela FK
composta, não colidem no unique por run/ato e podem ficar ativas porque seus atos
são diferentes. Estado válido.

### B — repetição idempotente

A unique `uq_parsing_runs_source_parser` impede R2 para X/parser/v1. O serviço
encontra R1 COMPLETED e retorna `ALREADY_PARSED`. Nenhuma versão nova.

### C — falha antes da materialização

R2 fica FAILED com `finished_at`. Não existe versão, pois parsing ocorreu em
memória. Estado válido e auditável.

### D — falha em TX2

CF e ADCT parciais pertencem à mesma TX2 e sofrem rollback. TX3 marca o run
FAILED. Nenhuma árvore parcial sobrevive.

### E — parser v2

`parser_version` diferente permite novo run. TX2 desativa versões R1 antes de
ativar as novas; o índice parcial nunca observa duas ativas do mesmo ato. R1 e
seus elementos permanecem auditáveis e inativos.

### F — captura futura

SourceDocument Y permite novo run mesmo com parser v2. FK composta mantém cada
versão ligada a Y. Versões anteriores continuam persistidas; somente uma por ato
permanece ativa.

Estados inválidos rejeitados fisicamente: documento divergente entre run e
versão, ato duplicado no run, ordem duplicada, duas versões ativas do mesmo ato,
pai de outra versão, segundo root, tipo/status/role inválidos e texto vazio.

## 12. Especificação final da migration 004

Nome/revisões:

```text
revision = 004_frozen_parsing_model
down_revision = 003_ingestion_raw_storage
```

### 12.1 Nova tabela

`parsing_runs`:

| Coluna | PostgreSQL | Nullable | Default |
|---|---|---:|---|
| `id` | UUID | não | nenhum; gerado pela aplicação |
| `source_document_id` | UUID | não | nenhum |
| `parser_name` | VARCHAR(100) | não | nenhum |
| `parser_version` | VARCHAR(50) | não | nenhum |
| `status` | VARCHAR(20) | não | `'RUNNING'` |
| `started_at` | TIMESTAMPTZ | não | `now()` |
| `finished_at` | TIMESTAMPTZ | sim | nenhum |
| `metadata` | JSONB | sim | nenhum |

Criar constraints com os nomes da seção 8.1. Não criar índices extras: as duas
uniques atendem acesso por chave lógica e alvo composto.

### 12.2 `legal_versions`

- adicionar `parsing_run_id UUID NOT NULL`, sem default;
- criar `fk_legal_versions_parsing_run_source_document`;
- criar `uq_legal_versions_parsing_run_legal_act`;
- alterar default de servidor de `is_active_for_query` para `false`;
- criar `uq_legal_versions_one_active_per_act`;
- criar `ix_legal_versions_source_document_id`;
- manter a FK direta de SourceDocument e todos os demais campos.

### 12.3 `legal_elements`

- adicionar `document_order BIGINT NOT NULL`, sem default;
- adicionar `text_status VARCHAR(20) NOT NULL DEFAULT 'UNRESOLVED'`;
- adicionar `content_role VARCHAR(30) NOT NULL DEFAULT 'NORMATIVE'`;
- adicionar `source_locator JSONB NOT NULL`, sem default;
- adicionar `parser_metadata JSONB NULL`;
- alterar `normalized_text` para NOT NULL;
- remover `ordinal`;
- remover `is_revoked`;
- substituir FK pai simples pela composta;
- criar todos os CHECKs, uniques e índice parcial da seção 8.3;
- manter `raw_text NOT NULL`, `path NULL`, timestamps e demais índices
  existentes.

### 12.4 Ordem segura do upgrade

1. executar guard de `legal_versions=0 AND legal_elements=0`;
2. criar `parsing_runs` com todas as colunas e constraints;
3. adicionar `legal_versions.parsing_run_id NOT NULL`;
4. criar a FK composta e unique por run/ato;
5. alterar default de ativação;
6. criar índice parcial de ativação e índice de SourceDocument;
7. adicionar colunas novas de LegalElement;
8. tornar `normalized_text` NOT NULL;
9. remover FK pai simples;
10. criar unique `(id, legal_version_id)`;
11. criar FK pai composta;
12. criar unique de ordem, CHECKs e índice parcial de root;
13. remover `ordinal` e `is_revoked`.

Não tocar em SourceDocument, raw bytes, chunks, evidence ou tabelas posteriores.

### 12.5 Ordem segura do downgrade

Aplicar a precondition e a ordem exata da seção 10.3. O guard deve ocorrer antes
de qualquer DROP/ALTER para que a recusa não deixe DDL parcial.

## 13. Testes previstos para a migration

Todos usarão banco descartável separado, nunca a captura real:

1. upgrade 003 → 004 com SourceDocument permitido e sem dados derivados;
2. introspecção de colunas, defaults, nullability, CHECKs, FKs e índices;
3. downgrade 004 → 003 no mesmo estado;
4. novo upgrade para provar ciclo reversível;
5. downgrade recusado separadamente com ParsingRun, LegalVersion ou LegalElement;
6. SourceDocument inexistente rejeitado em ParsingRun;
7. divergência de SourceDocument entre run e versão rejeitada;
8. segundo LegalAct igual no mesmo run rejeitado;
9. pai de LegalVersion diferente rejeitado e root NULL permitido;
10. document_order duplicado ou menor que 1 rejeitado;
11. segunda versão ativa do mesmo ato rejeitada; CF e ADCT simultâneas permitidas;
12. element_type, text_status e content_role inválidos rejeitados;
13. combinações role/status e NOTE/role incompatíveis rejeitadas;
14. segundo root e root com forma inválida rejeitados;
15. source_locator inválido, texto vazio e label obrigatória ausente rejeitados;
16. retry e transições permitidas/proibidas testados no serviço da Fase 4B;
17. falha em TX2 testada para ausência total de versões/elementos.

## 14. Riscos residuais

- exatamente duas versões e existência da raiz são regras de completude do
  serviço, não constraints de cardinalidade;
- transições históricas de status não são garantidas pelo banco sem triggers;
- JSONB exige validação complementar do contrato no parser;
- o índice ativo exige a ordem correta de updates dentro da TX2;
- `block_index` é reproduzível somente com algoritmo/backend versionados;
- ARTICLE e CAPUT compartilham locator factual, distinguindo-se pelo metadata;
- compatibilidade completa de tipos pai-filho permanece na aplicação para evitar
  CHECK/trigger excessivo.

## 15. Decisões adiadas

Continuam adiados parser, migration, modelos ORM, fixtures físicas, thresholds de
cobertura, chunking, retrieval, evidence, citation, relações legislativas e LLM.
Não foi encontrado conflito novo que justifique ADR nesta etapa.
