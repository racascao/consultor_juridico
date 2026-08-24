# Fase 10 — Structured Evidence Unit

## Problema e desenho

O fluxo anterior reduzia a estrutura jurídica a `text_snapshot` e, no máximo,
um `parent_context`, perdendo a identidade dos elementos auxiliares. Foi
implementado um builder isolado, em memória, que reconstrói hierarquia,
ancestrais textuais e enumerações curtas a partir de `LegalElement`, mantendo o
Evidence ID original.

A unidade contém snapshot original, contexto original, texto estruturado,
hierarquia, IDs exatos dos elementos-fonte, `identity_key` e SHA-256 do texto
derivado. Não há resumo, paráfrase, inferência jurídica, tabela nova ou
migration.

## Invariantes e testes

Os testes cobrem elemento independente, caput/inciso/alínea, negação ancestral,
enumeração obrigatório/facultativo, exceção, parent context, determinismo,
snapshot imutável e proveniência. Todos os fragmentos do texto estruturado são
copiados de elementos autorizados.

- `SEU_SOURCE_FIDELITY: PASS`
- `SEU_NO_HALLUCINATION: PASS`
- `SEU_DETERMINISTIC: PASS`
- `SEU_PROVENANCE_COMPLETE: PASS`

## Experimento A/B

A estratégia A reutilizou o baseline congelado da Fase 9.18. A estratégia B
executou uma repetição completa sobre os mesmos EvidenceSets, IDs, modelo e
ordem; somente a apresentação textual foi substituída pela SEU. Essa escolha
reduziu o custo em CPU e evitou repetir retrieval/selection.

| Métrica | A | B |
|---|---:|---:|
| corretas | 4/10 | 4/10 |
| false abstentions | 6 | 6 |
| abstenção correta | 1/1 | 1/1 |
| unsafe | 0 | 0 |

`liberdade de expressão` melhorou, mas `voto obrigatório` regrediu. A inclusão
de irmãos enumerativos trouxe simultaneamente os ramos obrigatório e
facultativo, e o Polarity Guard rejeitou a claim de forma segura. `racismo`
continuou falhando em attribution e `direito à vida` continuou bloqueado pela
interpretação de “a salvo” como sinal de exceção. Não houve ganho líquido em
Generator, Attribution, Polarity ou Semantic.

## Decisão

`STRUCTURED_EVIDENCE_GATE: BLOCKED`. A representação é fiel e auditável, mas a
política de contexto ainda não é seletiva o bastante para produção.
`QUALITY_IMPACT: NO_IMPACT`. O limite de capacidade do Granite 3B permanece
inconclusivo porque a representação ainda introduz ambiguidade estrutural.

Próxima intervenção única: refinar deterministicamente a seleção de contexto
estrutural da SEU antes de novo A/B. A SEU não foi conectada ao pipeline de
produção.
