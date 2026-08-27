# Plano de implementação da v0.2

O roadmap segue o princípio **retrieval before generation**.

1. **Fase 0.2.1 — Architecture foundation + LangGraph contracts:** domínio,
   ports, estado, rotas, limites, interrupt/resume e testes com fakes.
2. **Fase 0.2.2 — Novo corpus e SearchUnits contextualizadas:** representação
   recuperável antes de escolher algoritmos de ranking.
3. **Fase 0.2.3 — Retrieval lexical + vector + avaliação básica:** baseline de
   localização e relevância sem geração.
4. **Fase 0.2.4 — Evidence Relevance Judge + ambiguity detection:** julgamento
   pergunta-evidência e clarificação tipada.
5. **Fase 0.2.5 — Answer Generator:** geração estritamente sobre evidência já
   aprovada.
6. **Fase 0.2.6 — Answer Judge + retry loops reais:** avaliação conjunta de
   pergunta, resposta e evidência.
7. **Fase 0.2.7 — CLI interactive clarification:** ligar interrupt/resume à
   interface, sem regras na CLI.
8. **Fase 0.2.8 — Benchmark natural + hardening:** medir uso natural antes de
   qualquer otimização adicional.

Adapters de PostgreSQL e Ollama, prompts definitivos, embeddings e E2E não
fazem parte da Fase 0.2.1.
