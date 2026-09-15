# Tarefas

## MVP2

```text
STATUS: COMPLETE
FINAL_DECISION: MVP2_ACCEPTED_WITH_KNOWN_LIMITATIONS
```

- [x] Fundação documental e corpus versionado da Lei nº 9.784/1999.
- [x] Parser estrutural, projeção e materialização auditável.
- [x] Retrieval lexical PostgreSQL e expansão estrutural de evidências.
- [x] Avaliação Gold Evidence e seleção do answerer.
- [x] Integração RAG com contrato JSON e Citation Validation.
- [x] Contrato explícito `LEGAL_RULE | CASE_APPLICATION`.
- [x] Integrated DEV, freeze do runtime e Blind HOLDOUT único.
- [x] Revisão humana e decisão final com limitações conhecidas.
- [x] Consolidação e empacotamento documental do MVP2.
- [x] Bootstrap idempotente, packaging e interface interativa Rich.
- [x] Site MkDocs Material com guia incremental de reimplementação, referência
  e experimentos do MVP2.
- [x] Publicação automática do MkDocs no GitHub Pages configurada via GitHub
  Actions.
- [x] Fluxogramas end-to-end resumido e detalhado incorporados à documentação.

## Pós-HOLDOUT / MVP3

- [ ] Definir uma nova fase metodológica somente em task independente.
- [ ] Criar novo baseline e datasets DEV que não reutilizem o HOLDOUT v1.
- [ ] Formular hipóteses gerais antes de alterar o runtime congelado.

O HOLDOUT v1 é permitido apenas para auditoria histórica, comparação documental
e rastreabilidade. É proibido usá-lo para tuning, thresholds, depuração por
caso, prompt iteration ou desenvolvimento.
