# Relatório de Auditoria do Schema — Fase 2B

## 1. Resumo

Este documento apresenta o diagnóstico de auditoria da **Fase 2B (SQLAlchemy + Alembic + PostgreSQL)** em comparação com a especificação de referência congelada em [`docs/21-modelo-relacional.md`](file:///home/racascao/Workspace/Python/consultor_juridico/docs/21-modelo-relacional.md).

A auditoria cobriu as 12 entidades do modelo, as migrações do Alembic, a integridade de chaves estrangeiras, restrições e índices no banco de dados PostgreSQL containerizado, o suporte a vetores no `pgvector`, a hierarquia normativa e a suíte de testes.

**Status Geral**: O schema físico gerado pela migração `001_initial_schema` reflete com alta fidelidade a arquitetura aprovada. O ciclo de vida da migração (`upgrade head` $\rightarrow$ `downgrade base` $\rightarrow$ `upgrade head`) foi testado e é 100% reproduzível. Foram identificadas **3 divergências menores/inconsistências de nomenclatura** e **2 riscos de integridade** que exigem aprovação antes de correções ou avanço para a Fase 3.

---

## 2. Itens Conformes

1. **Entidades Documentais e Imutabilidade (`Source` e `SourceDocument`)**:
   - `Source`: PK `id` UUID, `name`, `base_url`, `description`, `created_at`.
   - `SourceDocument`: PK `id` UUID, FK `source_id` com `ON DELETE RESTRICT` (impede a exclusão de fontes com documentos ativos), `url_source`, `raw_content` imutável, `content_hash_sha256` com restrição de unicidade `UNIQUE`, `fetched_at`, `http_headers` JSONB e `metadata` JSONB.
2. **Entidades Jurídicas e Separação de Vigência (`LegalAct`, `LegalVersion`, `LegalElement`)**:
   - `LegalAct`: PK `id` UUID, `title`, `short_name` UNIQUE, `act_type`, `official_number`, `enactment_date`.
   - `LegalVersion`: PK `id` UUID, FK `legal_act_id` (`RESTRICT`), FK `source_document_id` (`RESTRICT`), `version_label`, `is_active_for_query`.
   - `LegalElement`: PK `id` UUID (identidade semântica primária), FK `legal_version_id` (`CASCADE`), FK `parent_id` (`CASCADE`), `element_type`, `number_label`, `raw_text`, `normalized_text`, `is_revoked`, `path` (atributo auxiliar de navegação). Restrição de verificação `CHECK (parent_id <> id)` ativada fisicamente no PostgreSQL.
3. **Indexação e Múltiplos Embeddings (`Chunk`, `ChunkLegalElement`, `Embedding`)**:
   - `Chunk`: PK `id` UUID, FK `legal_version_id` (`CASCADE`), `chunk_text`, `token_count`, `strategy_name`, `tsv_content` (`TSVECTOR` com índice GIN `ix_chunks_tsv_content`).
   - `ChunkLegalElement`: Tabela de junção N:N com PK composta `(chunk_id, legal_element_id)`, FKs com `ON DELETE CASCADE` e atributo `is_primary`.
   - `Embedding`: PK `id` UUID, FK `chunk_id` (`CASCADE`), `provider_name`, `model_name`, `model_version`, `dimensions`, `vector` (tipo `VECTOR` do `pgvector`). Suporta múltiplos vetores de modelos/provedores distintos para o mesmo chunk. Restrição `CheckConstraint("dimensions > 0")`.
4. **Conjunto de Evidências e Snapshot Imutável (`EvidenceSet`, `EvidenceItem`)**:
   - `EvidenceSet`: PK `id` UUID, `query_text`, `retrieval_strategy`, `validation_status`, `total_items`, `metadata` JSONB, `created_at`.
   - `EvidenceItem`: PK `id` UUID, FK `evidence_set_id` (`CASCADE`), FK `chunk_id` (`RESTRICT`), FK `legal_element_id` (`RESTRICT`), `evidence_code`, `citation_label`, `text_snapshot` (cópia imutável do texto fornecido ao LLM), `is_validated`, `validation_metadata`. Restrição `UNIQUE (evidence_set_id, evidence_code)`.
5. **Afirmações e Citações (`Claim`, `Citation`)**:
   - `Claim`: PK `id` UUID, `claim_code`, `text`, `created_at`.
   - `Citation`: PK `id` UUID, FK `claim_id` (`CASCADE`), FK `evidence_item_id` (`RESTRICT`), FK `evidence_set_id` (`CASCADE`), `is_valid`, `validation_notes`. Suporta a cardinalidade M:N entre *Claims* e *EvidenceItems*.

---

## 3. Divergências Identificadas

### 3.1. Divergência no Nome da Constraint de Unicidade em `Embedding`
- **Modelo SQLAlchemy (`models/embedding.py`)**: Define a constraint com o nome explícito `uq_embedding_chunk_model`.
- **Migration (`001_initial_schema.py`) e Banco PostgreSQL**: O Alembic aplicou o naming convention padrão gerando o nome `uq_embeddings_chunk_id`.
- **Impacto**: O comportamento funcional de unicidade das 4 colunas (`chunk_id`, `provider_name`, `model_name`, `model_version`) está **100% ativo e correto no banco**, mas autogenerates futuros do Alembic podem tentar renomear a constraint devido à divergência de string de nome entre o modelo Python e a migration.

### 3.2. Índices Únicos Redundantes em `SourceDocument` e `LegalAct`
- **Situação**: Em `source_documents` e `legal_acts`, foram declarados simultaneamente uma `UniqueConstraint` e um `create_index(..., unique=True)`.
- **Impacto no PostgreSQL**: O PostgreSQL cria dois índices B-Tree idênticos no banco para a mesma coluna (`uq_source_documents_content_hash_sha256` e `ix_source_documents_content_hash_sha256`). Isso gera overhead desnecessário em inserções sem ganho de performance.

### 3.3. Falsa Impressão da Validação de Dimensões em `Embedding`
- **Situação**: A constraint atual é `CHECK (dimensions > 0)`.
- **Diagnóstico**: Essa restrição valida apenas se o inteiro na coluna `dimensions` é maior que zero. Ela **NÃO** valida se o inteiro `dimensions` corresponde ao tamanho físico real do vetor armazenado no pgvector. Um registro com `dimensions = 768` aceitará um vetor de 1024 posições no pgvector sem que a `CHECK` falhe.

---

## 4. Riscos Arquiteturais Identificados

### 4.1. Risco de Inconsistência Cruzada em `Citation.evidence_set_id`
- **Descrição**: A tabela `Citation` possui `evidence_item_id` (FK para `evidence_items.id`) e `evidence_set_id` (FK para `evidence_sets.id`).
- **Risco**: Como as FKs são independentes, o banco PostgreSQL aceita que uma `Citation` registre `evidence_set_id = Set B` enquanto seu `evidence_item_id` pertence ao `Set A`.
- **Severidade**: Média/Alta para a rastreabilidade estrita da resposta.

### 4.2. Mistura Silenciosa de Embeddings por Falta de Filtro no Nível de Banco
- **Descrição**: A coluna `vector` utiliza o tipo dinâmico `Vector()` sem dimensão fixa no DDL.
- **Risco**: Se a aplicação realizar uma busca semântica `WHERE ... ORDER BY vector <-> query_vector` sem filtrar `provider_name`, `model_name` e `model_version`, o PostgreSQL tentará calcular similaridade vetorial entre vetores de modelos incompatíveis.

---

## 5. Correções Recomendadas

1. **Alinhar Nome da Constraint de Unicidade em `Embedding`**:
   - Ajustar o modelo SQLAlchemy (`models/embedding.py`) para usar o nome gerado `uq_embeddings_chunk_id` ou atualizar a migration para uniformizar o nome da constraint.
2. **Remover Índices Únicos Redundantes**:
   - Manter apenas a `UniqueConstraint` em `SourceDocument(content_hash_sha256)` e `LegalAct(short_name)`, removendo os índices duplicados `ix_source_documents_content_hash_sha256` e `ix_legal_acts_short_name`.
3. **Reforçar Integridade Cruzada entre `Citation` e `EvidenceItem`**:
   - Adicionar restrição única composta em `EvidenceItem`: `UNIQUE (id, evidence_set_id)`.
   - Substituir a FK simples de `Citation` por uma FK composta:
     `FOREIGN KEY (evidence_item_id, evidence_set_id) REFERENCES evidence_items(id, evidence_set_id) ON DELETE RESTRICT ON UPDATE CASCADE`.
   - Isso garantirá fisicamente no PostgreSQL que uma `Citation` só possa citar evidências que pertençam ao mesmo `EvidenceSet`.
4. **Validação Física da Dimensão Vetorial (Opcional/Recomendado)**:
   - Alterar a constraint de verificação em `embeddings` para:
     `CHECK (vector IS NULL OR dimensions = vector_dims(vector))`.

---

## 6. Decisões que Precisam de Aprovação

1. **Aprovação do Ajuste de Nomenclatura e Remoção de Índices Redundantes**:
   Aprovar a consolidação dos nomes de constraints e eliminação dos índices únicos duplicados.
2. **Aprovação da Restrição Composta de Pertencimento em `Citation`**:
   Aprovar a adição da FK composta `(evidence_item_id, evidence_set_id)` para blindar a integridade entre *Citações* e *Conjuntos de Evidências*.

---

## 7. Conclusão (Pré-Correções)

A implementação da **Fase 2B** é sólida, reproduzível e atende com rigor aos requisitos conceituais aprovados na Fase 2A. As divergências e riscos apontados foram devidamente mapeados e **nenhum código foi modificado** nesta etapa de auditoria.

Aguardamos a revisão deste relatório e a autorização das pequenas correções recomendadas antes de prosseguir com os trabalhos da **Fase 3**.

---

## 8. Reauditoria Após Correções

### 8.1. Correções Realizadas

**Migration `002_schema_corrections`** criada em
[`versions/002_schema_corrections.py`](file:///home/racascao/Workspace/Python/consultor_juridico/src/consultor_juridico/db/migrations/versions/002_schema_corrections.py).

| # | Correção | Status |
|---|----------|--------|
| 1 | Renomear `uq_embeddings_chunk_id` → `uq_embeddings_chunk_provider_model_version` | ✅ Aplicado |
| 2 | Remover índice único redundante `ix_source_documents_content_hash_sha256` | ✅ Aplicado |
| 3 | Remover índice único redundante `ix_legal_acts_short_name` | ✅ Aplicado |
| 4 | Adicionar `CHECK (vector IS NULL OR dimensions = vector_dims(vector))` em `embeddings` | ✅ Aplicado |
| 5 | Adicionar `UNIQUE (id, evidence_set_id)` em `evidence_items` | ✅ Aplicado |
| 6 | Substituir FK simples de `citations.evidence_item_id` por FK composta `(evidence_item_id, evidence_set_id) → evidence_items(id, evidence_set_id) ON DELETE RESTRICT` | ✅ Aplicado |

**Modelos SQLAlchemy atualizados:**
- [`models/embedding.py`](file:///home/racascao/Workspace/Python/consultor_juridico/src/consultor_juridico/models/embedding.py): novos nomes de constraints e `ck_embeddings_vector_dimensions_match`.
- [`models/evidence.py`](file:///home/racascao/Workspace/Python/consultor_juridico/src/consultor_juridico/models/evidence.py): `UniqueConstraint(id, evidence_set_id)`.
- [`models/claim.py`](file:///home/racascao/Workspace/Python/consultor_juridico/src/consultor_juridico/models/claim.py): `ForeignKeyConstraint` composta em `Citation`.
- [`models/source.py`](file:///home/racascao/Workspace/Python/consultor_juridico/src/consultor_juridico/models/source.py): removido `index=True` redundante.
- [`models/legal.py`](file:///home/racascao/Workspace/Python/consultor_juridico/src/consultor_juridico/models/legal.py): removido `index=True` redundante.

### 8.2. Testes Realizados

**Novos testes adicionados em [`tests/test_db.py`](file:///home/racascao/Workspace/Python/consultor_juridico/tests/test_db.py):**

| Teste | Verifica | Resultado |
|-------|----------|-----------|
| `test_alembic_migration_and_rollback` | Ciclo `downgrade base → upgrade head` reproduzível; verifica versão `002_schema_corrections` | ✅ |
| `test_multiple_embeddings_per_chunk` | Múltiplos embeddings de modelos distintos aceitos para o mesmo Chunk | ✅ |
| `test_unique_embedding_per_chunk_provider_model_version` | Duplicata de `(chunk, provider, model, version)` rejeitada por `uq_embeddings_chunk_provider_model_version` | ✅ |
| `test_different_provider_same_model_allowed` | Mesmo nome de modelo com provedores diferentes é aceito (permitido por design) | ✅ |
| `test_embedding_vector_dimensions_mismatch_rejected` | `dimensions=768` com vetor de 3 posições rejeitado por `ck_embeddings_vector_dimensions_match` | ✅ |
| `test_citation_cross_evidence_set_rejected` | `Citation` cruzando `EvidenceSet A` e `EvidenceSet B` rejeitada por FK composta | ✅ |

**Resultado total:** `20 passed, 0 warnings in 1.08s`

### 8.3. Validação no Docker

```bash
docker compose build app
docker compose run --rm app db migrate
# Migrations executadas com sucesso!
docker compose run --rm app db status
# Versão Alembic: 002_schema_corrections
# Tabelas ativas (13): alembic_version, sources, source_documents,
#   legal_acts, legal_versions, legal_elements, chunks, chunk_legal_elements,
#   evidence_items, evidence_sets, claims, citations, embeddings
```

### 8.4. Decisão Documentada: Mistura de Embeddings

Conforme explicitado nas correções, **não foi implementado nenhum mecanismo de banco para impedir mistura de modelos distintos em buscas vetoriais**. Essa validação é responsabilidade exclusiva do `SemanticRetriever` (fase posterior), que deve filtrar explicitamente por `(provider_name, model_name, model_version)` antes de executar qualquer busca vetorial por similaridade.

### 8.5. Estado Final

- Migration head: `002_schema_corrections`
- Schema: completamente conforme ao modelo aprovado em `docs/21-modelo-relacional.md`
- Integridade referencial da cadeia `Claim → Citation → EvidenceItem → EvidenceSet → Chunk → LegalElement → LegalVersion → SourceDocument → Source`: **100% garantida fisicamente no PostgreSQL**
- Testes: 20/20 passando, 0 warnings
- Lint: 0 erros (`ruff check .`)
- **A Fase 2B está tecnicamente fechada.**

