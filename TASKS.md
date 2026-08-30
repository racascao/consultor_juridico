# TASKS — Consultor Jurídico

## MVP2 / v0.2.0

- [x] **MVP2-F1 — Fundação Arquitetural:** domínio framework-independent,
  ports, workflow LangGraph, decisões tipadas, limites e clarificação testados.
- [x] **MVP2-F2 — Core Funcional / implementação:**
  - [x] Gate A — Corpus contextual;
  - [x] Gate B — FTS, embeddings persistentes, cosine exato e RRF;
  - [x] Gate C — Consultation Model tipado e clarificação;
  - [x] Gate D — workflow CPU-first com uma inferência LLM direta;
  - [x] Gate E — Citation Validator e CLI v0.2;
  - [x] Gate F — comandos e dataset preparados para aceitação manual.
- [ ] **MVP2-F2 — aceitação manual:** executar os cinco casos obrigatórios e o
  dataset `basic_direct_v1` com PostgreSQL/Ollama reais. Baseline inicial de
  retrieval reprovada; pools internos e diversidade do top-10 foram corrigidos
  estruturalmente, mas o reteste não mostrou ganho material. A auditoria causal
  das SearchUnits resultou na projeção contextual v2, cuja rematerialização e
  novo benchmark real estão pendentes. O workflow multi-LLM foi removido e o
  reteste real do fluxo simplificado permanece pendente.
- [ ] **MVP2-F3 — Validação e Release:** futura; não iniciar antes da aceitação
  explícita do core funcional.

Gates são checkpoints internos, não novas fases. Bugs, modelos, prompts,
thresholds e reruns permanecem dentro da fase funcional correspondente.

## Histórico

O MVP1 está congelado na tag v0.1.0. Seu runtime, schema e testes substituídos
não permanecem ativos na branch v0.2; decisões e resultados históricos seguem
preservados no Git e nos documentos históricos.
