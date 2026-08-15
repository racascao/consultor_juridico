# Modelo Relacional e Vetorial — Consultor Jurídico (MVP 1)

## 1. Objetivo

Este documento especifica a modelagem conceitual e lógica do banco de dados relacional e vetorial do **Consultor Jurídico (MVP 1)**.

O objetivo do modelo é garantir a rastreabilidade estrita da informação jurídica a partir da fonte oficial (Portal do Planalto), preservando a cadeia documental auditável, a estrutura hierárquica da norma constitucional, a busca híbrida (lexical + semântica) e o congelamento (*snapshot*) do conjunto de evidências fornecido ao LLM.

---

## 2. Princípios de Modelagem

1. **Imutabilidade da Fonte Primária**: O documento bruto obtido da fonte oficial nunca é alterado ou sobrescrito.
2. **Cadeia de Rastreabilidade Auditável por FKs**:
   $$\text{Claim} \xrightarrow{\text{FK}} \text{Citation} \xrightarrow{\text{FK}} \text{EvidenceItem} \xrightarrow{\text{FK}} \text{Chunk} \xrightarrow{\text{FK}} \text{LegalElement} \xrightarrow{\text{FK}} \text{LegalVersion} \xrightarrow{\text{FK}} \text{SourceDocument} \xrightarrow{\text{FK}} \text{Source}$$
   A navegabilidade é garantida por restrições físicas de Chave Estrangeira (*Foreign Keys*), e não apenas de forma conceitual.
3. **Desacoplamento de Provedor de Embedding**: O banco de dados suporta múltiplos embeddings para o mesmo `Chunk`, sem congelar o modelo vetorial em nível de arquitetura e impedindo misturas silenciosas de vetores de modelos distintos.
4. **Desacoplamento de Estratégia de Chunking**: O modelo relacional permite diferentes granularidades de chunking sem perder o vínculo estrito com os `LegalElement` originais.
5. **Snapshot de Evidências (*Imutabilidade Histórica*)**: O texto efetivamente fornecido ao LLM é congelado em `EvidenceItem`, garantindo que atualizações posteriores na base jurídica não alterem o histórico de auditoria de consultas passadas.
6. **Integridade Referencial Estrita**: Chaves estrangeiras, restrições exclusivas e restrições de verificação (*CHECK constraints*) impedem estados inconsistentes ou dados órfãos.

---

## 3. Diagrama ER ASCII

```text
  ┌──────────────┐          ┌──────────────────┐          ┌──────────────────┐
  │    Source    │ 1      N │  SourceDocument  │ 1      N │   LegalVersion   │
  ├──────────────┤──────────┼──────────────────┤──────────┼──────────────────┤
  │ PK id        │          │ PK id            │          │ PK id            │
  │    name      │          │ FK source_id     │          │ FK legal_act_id  │
  │    base_url  │          │    url_source    │          │ FK source_doc_id │
  └──────────────┘          │    raw_bytes     │          │    version_label │
                            │    hash_sha256   │          └────────┬─────────┘
                            └──────────────────┘                   │
                                                                   │ 1
                                                                   │
                            ┌──────────────────┐                   │
                            │     LegalAct     │                   │
                            ├──────────────────┤                   │
                            │ PK id            │                   │
                            │    short_name    │                   │
                            └────────┬─────────┘                   │
                                     │ 1                           │
                                     └─────────────────────────────┤
                                                                   │ N
                                                                   ▼
┌──────────────────┐ 1    N ┌──────────────────┐ N      N ┌──────────────────┐
│   LegalElement   │◄───────┤ ChunkLegalElem   ├─────────►│      Chunk       │
│ (Hierarchical)   │        ├──────────────────┤          ├──────────────────┤
├──────────────────┤        │ FK legal_elem_id │          │ PK id            │
│ PK id (UUID)     │        │ FK chunk_id      │          │ FK legal_vers_id │
│ FK legal_vers_id │        └──────────────────┘          │    chunk_text    │
│ FK parent_id     │                                      │    tsv_content   │
│    element_type  │                                      └────────┬─────────┘
│    number_label  │                                               │
│    path (aux)    │                                               │ 1
└──────────────────┘                                               │
                                                                   │ N
                                                          ┌────────┴─────────┐
                                                          │    Embedding     │
                                                          ├──────────────────┤
                                                          │ PK id            │
                                                          │ FK chunk_id      │
                                                          │    provider_name │
                                                          │    model_name    │
                                                          │    model_version │
                                                          │    dimensions    │
                                                          │    vector        │
                                                          └──────────────────┘


 ┌──────────────────┐ 1    N ┌──────────────────┐ N      1 ┌──────────────────┐
 │   EvidenceSet    ├───────►│   EvidenceItem   ├─────────►│      Chunk       │
 ├──────────────────┤        ├──────────────────┤          └──────────────────┘
 │ PK id            │        │ PK id            │
 │    query_text    │        │ FK evid_set_id   │ 1       1 ┌──────────────────┐
 │    retriev_strat │        │ FK chunk_id      ├──────────►│   LegalElement   │
 │    valid_status  │        │ FK legal_elem_id │          └──────────────────┘
 │    created_at    │        │    text_snapshot │
 └──────────────────┘        │    citation_label│
                             └────────┬─────────┘
                                      │ 1
                                      │
                                      │ N (M:N via Citation)
                             ┌────────┴─────────┐
                             │     Citation     │
                             ├──────────────────┤
                             │ PK id            │
                             │ FK claim_id      │
                             │ FK evid_item_id  │
                             └────────┬─────────┘
                                      │ N
                                      │
                                      │ 1
                             ┌────────┴─────────┐
                             │      Claim       │
                             ├──────────────────┤
                             │ PK id            │
                             │    text          │
                             └──────────────────┘
```

---

## 4. Entidades, Atributos, PKs, FKs e Cardinalidades

### 4.1. `Source`
- **Finalidade**: Cadastra a autoridade/fonte oficial do documento (ex.: Portal do Planalto).
- **PK**: `id` (`UUID`)
- **Atributos**: `name` (`VARCHAR(100)`), `base_url` (`TEXT`), `description` (`TEXT`), `created_at` (`TIMESTAMPTZ`)
- **FKs**: Nenhuma.
- **Cardinalidade**: `1 Source` $\rightarrow$ `N SourceDocument`

### 4.2. `SourceDocument`
- **Finalidade**: Armazena o documento bruto (HTML integral) exatamente como baixado da fonte oficial, sem alterações, junto com seu hash SHA-256 para imutabilidade e auditoria.
- **PK**: `id` (`UUID`)
- **FKs**: `source_id` $\rightarrow$ `Source.id` (`ON DELETE RESTRICT`) — *Impede a remoção de fontes que possuam documentos associados.*
- **Atributos**: `url_source` (`TEXT`), `raw_bytes` (`BYTEA`), `content_hash_sha256` (`VARCHAR(64)`), `fetched_at` (`TIMESTAMPTZ`), `http_headers` (`JSONB`), `metadata` (`JSONB`)
- **Cardinalidade**: `N SourceDocument` $\rightarrow$ `1 Source`, `1 SourceDocument` $\rightarrow$ `N LegalVersion`

### 4.3. `LegalAct`
- **Finalidade**: Identifica a norma jurídica em abstrato (ex.: "Constituição da República Federativa do Brasil de 1988", "Ato das Disposições Constitucionais Transitórias - ADCT").
- **PK**: `id` (`UUID`)
- **FKs**: Nenhuma.
- **Atributos**: `title` (`VARCHAR(255)`), `short_name` (`VARCHAR(50)`), `act_type` (`VARCHAR(50)`), `official_number` (`VARCHAR(50)`), `enactment_date` (`DATE`), `created_at` (`TIMESTAMPTZ`)
- **Cardinalidade**: `1 LegalAct` $\rightarrow$ `N LegalVersion`

### 4.4. `LegalVersion`
- **Finalidade**: Representa uma captura estrutural/versão específica de um `LegalAct` associada a um `SourceDocument`. Permite desacoplar a captura física da norma de seu estado de vigência jurídica.
- **PK**: `id` (`UUID`)
- **FKs**: 
  - `legal_act_id` $\rightarrow$ `LegalAct.id` (`ON DELETE RESTRICT`)
  - `source_document_id` $\rightarrow$ `SourceDocument.id` (`ON DELETE RESTRICT`)
- **Atributos**: `version_label` (`VARCHAR(100)`), `parsed_at` (`TIMESTAMPTZ`), `is_active_for_query` (`BOOLEAN`), `metadata` (`JSONB`)
- **Cardinalidade**: `N LegalVersion` $\rightarrow$ `1 LegalAct`, `N LegalVersion` $\rightarrow$ `1 SourceDocument`, `1 LegalVersion` $\rightarrow$ `N LegalElement`, `1 LegalVersion` $\rightarrow$ `N Chunk`

### 4.5. `LegalElement`
- **Finalidade**: Representa cada nó individual da árvore hierárquica do texto normativo (Título, Capítulo, Seção, Artigo, Parágrafo, Inciso, Alínea, Item).
- **PK**: `id` (`UUID`) — **Identidade semântica primária da entidade jurídica.**
- **FKs**: 
  - `legal_version_id` $\rightarrow$ `LegalVersion.id` (`ON DELETE CASCADE`)
  - `parent_id` $\rightarrow$ `LegalElement.id` (`ON DELETE CASCADE`, auto-referencial)
- **Atributos**: `element_type` (`VARCHAR(50)`), `number_label` (`VARCHAR(100)`), `ordinal` (`INTEGER`), `raw_text` (`TEXT`), `normalized_text` (`TEXT`), `is_revoked` (`BOOLEAN`), `path` (`VARCHAR(500)`), `created_at` (`TIMESTAMPTZ`)
- **Observação Crítica sobre `path`**: O campo `path` é um atributo auxiliar denormalizado para otimização de consultas e navegação. A identidade jurídica é dada exclusivamente pela PK (`id` UUID).
- **Cardinalidade**: `N LegalElement` $\rightarrow$ `1 LegalVersion`, `1 LegalElement (pai)` $\rightarrow$ `N LegalElement (filhos)`

### 4.6. `Chunk`
- **Finalidade**: Unidade de texto delimitada para fins de indexação e busca (lexical e semântica). Não é travada em "Artigo = Chunk".
- **PK**: `id` (`UUID`)
- **FKs**: `legal_version_id` $\rightarrow$ `LegalVersion.id` (`ON DELETE CASCADE`)
- **Atributos**: `chunk_text` (`TEXT`), `token_count` (`INTEGER`), `strategy_name` (`VARCHAR(100)`), `tsv_content` (`TSVECTOR`), `created_at` (`TIMESTAMPTZ`)
- **Cardinalidade**: `N Chunk` $\rightarrow$ `1 LegalVersion`, `N Chunk` $\leftrightarrow$ `N LegalElement` (através de `ChunkLegalElement`)

### 4.7. `ChunkLegalElement` (Tabela de Junção)
- **Finalidade**: Mapeia a relação N:N entre `Chunk` e `LegalElement`, permitindo saber exatamente quais dispositivos jurídicos compõem cada chunk e qual elemento é o principal.
- **PK**: `(chunk_id, legal_element_id)`
- **FKs**:
  - `chunk_id` $\rightarrow$ `Chunk.id` (`ON DELETE CASCADE`)
  - `legal_element_id` $\rightarrow$ `LegalElement.id` (`ON DELETE CASCADE`)
- **Atributos**: `is_primary` (`BOOLEAN`)

### 4.8. `Embedding`
- **Finalidade**: Vetor de embeddings gerado para um `Chunk` por um provedor e modelo configuráveis. Permite armazenar múltiplos vetores de modelos distintos para o mesmo chunk.
- **PK**: `id` (`UUID`)
- **FKs**: `chunk_id` $\rightarrow$ `Chunk.id` (`ON DELETE CASCADE`)
- **Atributos**: 
  - `provider_name` (`VARCHAR(100)`) — Ex: `"ollama"`, `"sentence-transformers"`
  - `model_name` (`VARCHAR(100)`) — Ex: `"nomic-embed-text"`, `"bge-m3"`
  - `model_version` (`VARCHAR(50)`) — Ex: `"v1.5"`, `"latest"`
  - `dimensions` (`INTEGER`) — Ex: `768`, `1024`
  - `vector` (`VECTOR`) — Coluna vetorial pgvector
  - `created_at` (`TIMESTAMPTZ`)
- **Cardinalidade**: `1 Chunk` $\rightarrow$ `N Embedding` (Suporta múltiplos vetores para o mesmo chunk).

### 4.9. `EvidenceSet`
- **Finalidade**: Preserva a informação necessária para reconstruir a origem da seleção e validação das evidências montadas para uma consulta específica.
- **PK**: `id` (`UUID`)
- **Atributos**: 
  - `query_text` (`TEXT`) — Pergunta original formulada pelo usuário
  - `retrieval_strategy` (`VARCHAR(100)`) — Ex: `"hybrid_rrf_v1"`
  - `validation_status` (`VARCHAR(50)`) — Ex: `"VALIDATED"`, `"PARTIAL"`, `"FAILED"`
  - `created_at` (`TIMESTAMPTZ`)
  - `total_items` (`INTEGER`)
  - `metadata` (`JSONB`)
- **Observação**: Não é necessário persistir o histórico completo da conversa no MVP 1; o `EvidenceSet` guarda o snapshot de recuperação e validação da consulta individual.
- **Cardinalidade**: `1 EvidenceSet` $\rightarrow$ `N EvidenceItem`

### 4.10. `EvidenceItem`
- **Finalidade**: Representa o *snapshot* imutável do texto de uma evidência efetivamente enviada ao LLM no momento da geração, vinculando-a obrigatoriamente ao seu `EvidenceSet`, `Chunk` e `LegalElement` de origem.
- **PK**: `id` (`UUID`)
- **FKs**:
  - `evidence_set_id` $\rightarrow$ `EvidenceSet.id` (`ON DELETE CASCADE`) — **NOT NULL**
  - `chunk_id` $\rightarrow$ `Chunk.id` (`ON DELETE RESTRICT`) — **NOT NULL**
  - `legal_element_id` $\rightarrow$ `LegalElement.id` (`ON DELETE RESTRICT`) — **NOT NULL**
- **Atributos**: `evidence_code` (`VARCHAR(50)`), `citation_label` (`VARCHAR(255)`), `text_snapshot` (`TEXT`), `source_url` (`TEXT`), `is_validated` (`BOOLEAN`), `validation_metadata` (`JSONB`), `created_at` (`TIMESTAMPTZ`)
- **Cardinalidade**: `N EvidenceItem` $\rightarrow$ `1 EvidenceSet`, `N EvidenceItem` $\rightarrow$ `1 Chunk`, `N EvidenceItem` $\rightarrow$ `1 LegalElement`

### 4.11. `Claim` (Especificação Conceitual Futura)
- **Finalidade**: Afirmação factual isolada gerada pelo LLM na resposta estruturada.
- **PK**: `id` (`UUID`)
- **Atributos**: `claim_code` (`VARCHAR(50)`), `text` (`TEXT`), `created_at` (`TIMESTAMPTZ`)
- **Cardinalidade**: `1 Claim` $\leftrightarrow$ `N Citation`

### 4.12. `Citation` (Especificação Conceitual Futura)
- **Finalidade**: Tabela de junção e validação que estabelece o relacionamento M:N entre `Claim` e `EvidenceItem`. Permite que uma *Claim* cite múltiplas evidências e que uma mesma evidência fundamente múltiplas *Claims*.
- **PK**: `id` (`UUID`)
- **FKs**:
  - `claim_id` $\rightarrow$ `Claim.id` (`ON DELETE CASCADE`) — **NOT NULL**
  - `evidence_item_id` $\rightarrow$ `EvidenceItem.id` (`ON DELETE RESTRICT`) — **NOT NULL**
- **Atributos**: `is_valid` (`BOOLEAN`), `validation_notes` (`TEXT`), `created_at` (`TIMESTAMPTZ`)
- **Cardinalidade**: `N Citation` $\rightarrow$ `1 Claim`, `N Citation` $\rightarrow$ `1 EvidenceItem`

---

## 5. Constraints de Integridade Referencial e Validação

O modelo aplica restrições físicas de banco de dados para evitar estados inconsistentes ou corrupção de dados:

1. **Garantia de Documento Inexistente / Fonte Órfã**:
   - `SourceDocument.source_id` é `NOT NULL` com `ON DELETE RESTRICT`. Impede registros de documentos com fontes inexistentes.
2. **Unicidade de Hash na Fonte (`SourceDocument`)**:
   - `CONSTRAINT uq_source_documents_source_hash UNIQUE (source_id, content_hash_sha256)`
   - Garante idempotência na mesma fonte e preserva proveniências distintas.
3. **Integridade Estrutural de `LegalElement`**:
   - `CONSTRAINT chk_legal_element_no_self_parent CHECK (parent_id <> id)` (impede que um elemento seja pai de si mesmo).
4. **Isolamento de Embeddings por Provedor/Modelo/Versão**:
   - `CONSTRAINT uq_embedding_chunk_model UNIQUE (chunk_id, provider_name, model_name, model_version)`
   - Impede vetores duplicados para o mesmo chunk sob a mesma versão de modelo.
5. **Validacão de Dimensão do Vetor de Embedding**:
   - `CONSTRAINT chk_embedding_dimensions CHECK (dimensions = vector_dims(vector))`
   - Garantia de que a dimensão declarada coincide com a dimensão física do vetor `pgvector`.
6. **Integridade Referencial de Evidências (`EvidenceItem`)**:
   - `evidence_set_id`, `chunk_id` e `legal_element_id` possuem restrição `NOT NULL`.
   - Impede `EvidenceItem` sem `EvidenceSet` ou sem vínculo com `Chunk` e `LegalElement`.
7. **Integridade de Citação e Pertencimento a `EvidenceSet`**:
   - `Citation` refere-se a `EvidenceItem` e `Claim`.
   - Restrição de validação para garantir que uma `Citation` só possa vincular um `Claim` a um `EvidenceItem` pertencente ao `EvidenceSet` ativo daquela consulta.

---

## 6. Estratégia de Índices

1. **Índices Primários e Únicos (B-Tree)**:
   - Chaves Primárias (`UUID`) em todas as tabelas.
   - `uq_source_documents_source_hash` ON `SourceDocument(source_id, content_hash_sha256)` UNIQUE
   - `idx_legal_act_short_name` ON `LegalAct(short_name)` UNIQUE

2. **Índices de Chaves Estrangeiras e Hierarquia (B-Tree)**:
   - `idx_legal_element_parent` ON `LegalElement(parent_id)`
   - `idx_legal_element_version` ON `LegalElement(legal_version_id)`
   - `idx_legal_element_path` ON `LegalElement(path)`
   - `idx_chunk_legal_version` ON `Chunk(legal_version_id)`
   - `idx_embedding_chunk` ON `Embedding(chunk_id)`
   - `idx_embedding_provider_model` ON `Embedding(provider_name, model_name, model_version)`

3. **Índice de Busca Lexical FTS (GIN)**:
   - `idx_chunk_tsv_content` ON `Chunk USING GIN(tsv_content)`
   - Consultas FTS via `to_tsquery('portuguese', ...)`.

4. **Estratégia Vetorial Inicial (`pgvector` / HNSW)**:
   - `idx_embedding_vector_hnsw` ON `Embedding USING hnsw (vector vector_cosine_ops)` WITH `(m = 16, ef_construction = 64)`
   - **Registro Arquitetural**: O índice HNSW é uma **estratégia inicial de indexação**, e NÃO uma decisão irreversível. A real necessidade, ganho de performance e parâmetros do índice vetorial serão avaliados e validados posteriormente por benchmark na Fase 7.

---

## 7. Detalhamento de `LegalElement.path` vs. Identidade Jurídica

### O que representa o `path`?
O atributo `path` é uma string denormalizada contendo o caminho hierárquico dos identificadores/rótulos dos nós desde a raiz até o nó atual (ex.: `/tit-2/cap-1/art-5/inc-57`).

### Finalidade:
O `path` serve **exclusivamente como auxílio de performance** para permitir:
1. Filtros rápidos de descendência por prefixo (ex.: `WHERE path LIKE '/tit-2/cap-1/%'`).
2. Ordenação visual da árvore normativa sem exigir CTEs recursivas em consultas simples de leitura.

### Distinção Crucial entre `path` e Identidade:
- **`path` NÃO é a identidade jurídica da entidade**. O `path` pode mudar caso a estrutura hierárquica seja reorganizada ou re-parseada.
- **A PK (`id` UUID) é a única identidade persistente e semântica** da entidade jurídica no banco de dados.
- Alterações estruturais ou de re-parsing não devem quebrar a identidade da entidade jurídica quando isso for juridicamente aplicável.
- **A aplicação NÃO deve depender exclusivamente de `path`** para regras de negócio, vinculos de citações ou resoluções de entidade.

---

## 8. Desacoplamento e Regras de Embeddings

O modelo permite que um mesmo `Chunk` possua múltiplos vetores de embeddings em `Embedding` (ex: um gerado por `nomic-embed-text` e outro por `bge-m3` para testes de benchmark):

```text
Chunk (id: chunk-001)
  ├── Embedding (provider: "ollama", model: "nomic-embed-text", version: "v1.5", vector: [0.12, ...])
  ├── Embedding (provider: "ollama", model: "bge-m3",           version: "v1.0", vector: [0.05, ...])
  └── Embedding (provider: "local",  model: "custom-legal-emb", version: "v2.0", vector: [-0.3, ...])
```

### Regra de Isolamento de Busca Vetorial:
**Embeddings de modelos ou versões diferentes NÃO podem ser misturados silenciosamente na mesma consulta de busca semântica.**
A engine de retrieval (`SemanticRetriever`) deve obrigatoriamente especificar os parâmetros `provider_name`, `model_name` e `model_version` na cláusula `WHERE` ao executar a busca por similaridade de cosseno.

---

## 9. Reconstrução do Origem em `EvidenceSet`

A entidade `EvidenceSet` preserva todos os parâmetros necessários para reconstruir exatamente como e por que determinado grupo de evidências foi selecionado:
- `query_text`: Pergunta do usuário.
- `retrieval_strategy`: Identificador do pipeline utilizado (ex.: `"hybrid_rrf_v1"`).
- `validation_status`: Resultado da validação pelo `EvidenceValidator`.
- `created_at`: Carimbo de data/hora da consulta.
- `metadata`: Parâmetros do retrieval ($k$, pesos FTS/vetorial, limiares de corte).

Não é necessário persistir o histórico de conversação; o `EvidenceSet` cumpre a função de auditoria isolada da consulta.

---

## 10. Cardinalidade e Relacionamento M:N (`Claim` $\leftrightarrow$ `Citation` $\leftrightarrow$ `EvidenceItem`)

A modelagem de validação de citações suporta o relacionamento M:N real entre afirmações do LLM e evidências do banco:

```text
Claim A: "O réu não será considerado culpado antes do trânsito em julgado e provas ilícitas são inadmissíveis."
 ├── Citation 1 ──────► EvidenceItem 1 (Art. 5º, LVII - presunção de inocência)
 └── Citation 2 ──────► EvidenceItem 2 (Art. 5º, LVI - veda provas ilícitas)

Claim B: "A presunção de inocência impede a execução provisória da pena."
 └── Citation 3 ──────► EvidenceItem 1 (Art. 5º, LVII - presunção de inocência)
```

- **1 Claim pode possuir N Citations** (apontando para N `EvidenceItem`s).
- **1 EvidenceItem pode ser referenciado por N Citations** (fundamentando múltiplos `Claim`s).
- A tabela `Citation` atua como a junção auditável entre o texto do LLM (`Claim`) e o snapshot do banco (`EvidenceItem`).

---

## 11. Navegabilidade da Cadeia de Rastreabilidade via Chaves Estrangeiras

Toda consulta e resposta pode ter sua procedência auditada navegando estritamente pelas Chaves Estrangeiras do banco de dados:

$$\text{Claim} \xrightarrow{\text{Citation.claim\_id}} \text{Citation} \xrightarrow{\text{Citation.evidence\_item\_id}} \text{EvidenceItem} \xrightarrow{\text{EvidenceItem.chunk\_id}} \text{Chunk} \xrightarrow{\text{ChunkLegalElem.legal\_elem\_id}} \text{LegalElement} \xrightarrow{\text{LegalElement.legal\_version\_id}} \text{LegalVersion} \xrightarrow{\text{LegalVersion.source\_document\_id}} \text{SourceDocument} \xrightarrow{\text{SourceDocument.source\_id}} \text{Source}$$

A rastreabilidade é **fisica e relacional**, garantida por FKs do PostgreSQL, e não meramente conceitual.

---

## 12. Decisões Arquiteturais em Aberto (Preservadas)

As seguintes questões permanecem deliberadamente **em aberto** para definição em fases posteriores com base em evidências práticas:

1. **Estratégia Definitiva de Chunking**: A granularidade dos chunks (artigo, parágrafo ou bloco) será decidida após inspeção do HTML real do Planalto na Fase 6.
2. **Modelo de Embedding**: Provedor e modelo específicos serão definidos via benchmark de retrieval na Fase 7.
3. **Estratégia Definitiva de Reranking**: Algoritmo de reordenamento (heurístico estrutural ou cross-encoder) será selecionado após testes.
4. **Modelagem de Alterações Legislativas**: Representação fina de histórico de revogações e emendas constitucionais será detalhada no parsing.
5. **Entidade de Relações Jurídicas (`LegalRelationship`)**: Relações normativas complexas entre artigos serão avaliadas em MVPs futuros.
6. **Estratégia Definitiva de Índice Vetorial**: A escolha entre HNSW, IVFFlat ou busca exata (*Flat*) será validada via benchmark de escala.

---

## 13. Exemplo Prático com a Constituição Federal (CF/88)

### Hierarquia do Art. 5º, inc. LVII da CF/88:

```text
LegalAct (title: "Constituição da República Federativa do Brasil de 1988", short_name: "CF/88")
 └── LegalVersion (version_label: "Compilada Planalto 2026-08-14")
      └── LegalElement (id: uuid-art5-inc57, type: INCISO, number_label: "LVII", path: "/tit-2/cap-1/art-5/inc-57")
```

### Mapeamento de Rastreabilidade e Snapshot:
- **`Chunk`**: Contém o texto normativo indexado.
- **`EvidenceItem`**:
  - `evidence_code`: `"EV-001"`
  - `citation_label`: `"Art. 5º, inc. LVII da CF/88"`
  - `text_snapshot`: `"LVII - ninguém será considerado culpado até o trânsito em julgado de sentença penal condenatória;"`
  - `source_url`: `"http://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm"`
- **`Claim`**: `"A Constituição proíbe a consideração de culpa antes do trânsito em julgado."`
- **`Citation`**: Conecta o `Claim` acima ao `EvidenceItem` `"EV-001"`.

---

## 14. Justificativa das Principais Decisões

1. **PostgreSQL + pgvector**: Banco relacional robusto com extensão vetorial integrada, eliminando infraestrutura duplicada.
2. **Separação de Identidade (`id`) e Caminho (`path`)**: Mantém a robustez semântica dos elementos jurídicos imune a refatorações de parsing ou mudanças estruturais de exibição.
3. **Múltiplos Embeddings por Chunk**: Permite benchmarks comparativos entre modelos vetoriais sem alterar a estrutura de dados relacional.
4. **Conexão M:N entre Claims e Evidências**: Reflete com precisão a prática jurídica de fundamentação em múltiplos dispositivos e uso do mesmo dispositivo para sustentar diferentes premissas.
