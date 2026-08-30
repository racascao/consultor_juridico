# Changelog

## 0.2.0 — Em desenvolvimento

### Arquitetura

- reset arquitetural iniciado com Clean Architecture e SOLID;
- LangGraph adotado exclusivamente para orquestração tipada do workflow;
- workflow CPU-first com uma única inferência de consulta por pergunta direta;
- clarificação modelada como estado interrompível e retomável do workflow;
- ports e dependency injection preparados para adapters futuros;
- fine-tuning explicitamente fora do plano da v0.2.
- nova baseline de corpus `SourceSnapshot → LegalAct → ActVersion → Provision
  → SearchUnit`;
- snapshots imutáveis, árvore simplificada e versões idempotentes de CF/88 e
  ADCT;
- SearchUnits `DOCUMENT_METADATA`, `ARTICLE` e `CONTEXTUAL_PROVISION`;
- separação explícita entre `search_text` contextual e `citation_text` oficial;
- remoção progressiva do schema e das migrations da v0.1 na branch v0.2.
- PostgreSQL FTS em português, embeddings persistentes de 768 dimensões,
  cosine exato e RRF simples sobre SearchUnits;
- `ConsultationResponder` com contrato discriminado `ANSWER | CLARIFY |
  ABSTAIN`, IDs request-scoped e falha fechada;
- clarificação interativa com novo retrieval, validação determinística de
  citações e CLI conectada exclusivamente ao pipeline v0.2;
- bootstrap idempotente de migrations, corpus e embeddings;
- dataset funcional `basic_direct_v1` e evaluator de retrieval;
- remoção do runtime e dos testes v0.1 substituídos na branch v0.2.

## 0.1.0 — MVP1 congelado

### Adicionado

- corpus oficial CF/88 + ADCT com captura binária, hash e proveniência;
- parsing determinístico, identidade normativa, materialização e retrieval
  híbrido (FTS + pgvector);
- EvidenceSet, citações, locator fidelity, polarity guard e validação semântica;
- EBCG_V2 para respostas controladas por evidência, sem geração jurídica livre;
- CLI de ingestão, parsing, indexação, retrieval, consulta e modo interativo;
- bootstrap inicial automático e idempotente baseado no PostgreSQL;
- provisionamento automático dos modelos Ollama em volume persistente;
- comandos constitucionais públicos em português (`constituicao`) e Quickstart
  reduzido à entrada no container e execução de `consultor-juridico`.

### Segurança e qualidade

- cadeia auditável até a fonte oficial;
- abstenção fail-closed quando a evidência não é suficiente;
- modelo do juiz semântico congelado em `ministral-3:8b`;
- avaliação offline v2: 8/10 respondíveis corretos, 1/1 abstenção correta e
  zero respostas inseguras.

### Validação

- benchmark nativo final `real_world_short_v2` executado: 8/10 casos
  respondíveis corretos (80%), 1/1 abstenção esperada correta e zero respostas
  inseguras;
- EBCG_V2 validado no fluxo completo; artefato final congelado e identificado
  por SHA-256.

### Limitações conhecidas

- `Hit@10=0.900` permanece abaixo do threshold histórico de `0.905`;
- uma falsa abstenção permanece por contexto estrutural em prisão perpétua e
  um `WRONG_TARGET` permanece por retrieval miss em estado de sítio;
- qualifier preservation não foi medido e formal stability não foi executada.
