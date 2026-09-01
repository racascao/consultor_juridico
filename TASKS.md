# TASKS — Consultor Jurídico

## MVP2 — Fase 0: Fundação e Corpus

- [x] Aprovar a Lei nº 9.784/1999 como ato piloto.
- [x] Isolar fisicamente o PostgreSQL v0.2 do banco legado.
- [x] Registrar a governança futura do HOLDOUT.
- [x] Investigar e documentar a fonte oficial.
- [x] Implementar baseline Alembic e schema mínimo v0.2.
- [x] Implementar aquisição condicional e snapshots imutáveis.
- [x] Implementar parser determinístico, cobertura fail-closed e fixtures.
- [x] Implementar projeção, materialização, reprojeção e auditoria.
- [x] Validar automaticamente o corpus real e a proveniência mecânica.
- [x] Concluir a validação manual de proveniência das cinco amostras.

Estado: concluída e aceita após validação manual de proveniência.

## MVP2 — Fase 1: Retrieval isolado

- [x] Criar, validar e congelar o DEV lexical com 40 casos.
- [x] Implementar o baseline PostgreSQL FTS com ActVersion explícita.
- [x] Executar uma única medição e congelar seu artefato.
- [x] Classificar genericamente as 40 falhas observadas.
- [x] Validar o strict com controle positivo 3/3.
- [x] Implementar e medir uma única vez a variante RELAXED_OR.
- [x] Classificar os oito misses restantes como diluição de ranking.
- [x] Diagnosticar os oito misses com lexemas PostgreSQL e cobertura lexical.
- [x] Implementar e medir uma única vez `RELAXED_OR_COVERAGE`.
- [ ] Revisar o baseline com o usuário antes de escolher outra hipótese.

Estado: strict `Hit@10=0,000`/`MRR=0,000`; RELAXED_OR
`Hit@10=0,800`/`MRR=0,549`; RELAXED_OR_COVERAGE
`Hit@10=0,875`/`MRR=0,661`. Coverage recuperou três misses, não perdeu hits
top-10 e teve uma regressão de rank 5 para 6. Runtime, dataset e projeção estão
congelados após a medição; a Fase 1 aguarda revisão humana.

As etapas posteriores ainda não foram especificadas formalmente. A tag
`v0.1.0` permanece congelada, e a primeira tentativa do MVP2 está preservada
somente no histórico Git.
