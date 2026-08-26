# TASKS — Consultor Jurídico

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

## Qualidade aceita e limites explícitos

- [x] Reassessment offline: 8/10 casos respondíveis corretos, 1/1 abstenção
  esperada e zero unsafe answers.
- [ ] E2E nativo final contra `real_world_short_v2` ainda não executado.
- [ ] `Hit@10=0.900` não atingiu o threshold histórico `0.905`.
- [ ] Qualifier preservation: `NOT_YET_MEASURED`.
- [ ] Formal stability: `NOT_RUN`.

## Pós-MVP1

- [ ] Resolver contexto parent/ancestor para o caso estrutural de prisão
  perpétua, com validação fail-closed.
- [ ] Investigar retrieval de estado de sítio (arts. 137/138) sem tuning por
  caso.
- [ ] Executar E2E nativo final do dataset v2 e medir estabilidade formal.
- [ ] Medir preservação de qualificadores materiais.
- [ ] Ampliar corpus para legislação infraconstitucional somente após revisão
  de arquitetura e fonte oficial.
- [ ] Avaliar API ou interface web como escopo posterior ao MVP1.

## Referência histórica

As decisões, ADRs, benchmarks e fases anteriores foram preservados em
[docs/README.md](docs/README.md). Este backlog registra apenas o estado útil
após o freeze, não uma cronologia de execução.
