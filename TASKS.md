# TASKS — Consultor Jurídico

## v0.2 — em desenvolvimento

- [x] Fase 0.2.1 — fundação Clean Architecture, contratos tipados e workflow
  LangGraph com clarificação e limites testados por fakes.
- [ ] Fase 0.2.2 — novo corpus e SearchUnits contextualizadas.
- [ ] Fase 0.2.3 — retrieval lexical + vetorial e avaliação básica.
- [ ] Fase 0.2.4 — Evidence Relevance Judge e detecção de ambiguidade.
- [ ] Fase 0.2.5 — Answer Generator.
- [ ] Fase 0.2.6 — Answer Judge e loops reais de retry.
- [ ] Fase 0.2.7 — clarificação interativa na CLI.
- [ ] Fase 0.2.8 — benchmark natural e hardening.

Princípio de execução: estabilizar retrieval antes de geração. A v0.1.0 abaixo
permanece como referência histórica congelada.

## MVP1 — concluído e congelado

- [x] Fundação, CLI-first, Docker Compose, PostgreSQL + pgvector e Ollama.
- [x] Modelo relacional, migrations 001–005 e integridade de proveniência.
- [x] Ingestão idempotente do Planalto com raw bytes, SHA-256 e Conditional GET.
- [x] Parsing determinístico de CF/88 e ADCT, identidade normativa e
  materialização transacional.
- [x] Chunks jurídicos, PostgreSQL FTS, embeddings locais e retrieval híbrido.
- [x] EvidenceSet/EvidenceItem, citações, locator fidelity, polarity guard e
  validação semântica fail-closed.
- [x] EBCG_V2: geração controlada por evidência, sem Generator LLM livre.
- [x] Dataset `real_world_short_v2`, taxonomia de falhas e reassessment offline.
- [x] Freeze operacional 0.1.0: configuração de juiz semântico alinhada a
  `ministral-3:8b`; experimentos não integrados permanecem congelados.
- [x] Primeiro uso: modelos, migrations, corpus e índice preparados
  automaticamente; estado persistente no PostgreSQL orienta a idempotência.

## Qualidade aceita e limites explícitos

- [x] Reassessment offline: 8/10 casos respondíveis corretos, 1/1 abstenção
  esperada e zero unsafe answers.
- [x] E2E nativo final contra `real_world_short_v2`: 8/10 respondíveis,
  1/1 abstenção esperada e zero unsafe answers.
- [ ] `Hit@10=0.900` não atingiu o threshold histórico `0.905`.
- [ ] Qualifier preservation: `NOT_YET_MEASURED`.
- [ ] Formal stability: `NOT_RUN`.

## Pós-MVP1

- [ ] Resolver contexto parent/ancestor para o caso estrutural de prisão
  perpétua, com validação fail-closed.
- [ ] Investigar retrieval de estado de sítio (arts. 137/138) sem tuning por
  caso.
- [ ] Medir estabilidade formal do pipeline congelado.
- [ ] Medir preservação de qualificadores materiais.
- [ ] Ampliar corpus para legislação infraconstitucional somente após revisão
  de arquitetura e fonte oficial.
- [ ] Avaliar API ou interface web como escopo posterior ao MVP1.

## Referência histórica

As decisões, ADRs, benchmarks e fases anteriores foram preservados em
[docs/README.md](docs/README.md). Este backlog registra apenas o estado útil
após o freeze, não uma cronologia de execução.
