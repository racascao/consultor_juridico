# Fase 91.7 — Relational Corpus & Infrastructure Validation Gate

Na retomada, o preflight confirmou PostgreSQL saudável no Compose e Alembic
`005_normative_identity_occurrences`. O corpus contém 1 source, 1 documento,
2 atos, 2 versões ativas, 6.775 elementos, 4.096 provisions, 3.389 chunks e
3.389 embeddings. A primeira tentativa `MANUAL_INFRA_ACTION_REQUIRED` foi
preservada historicamente.

As invariantes parent-child passaram (zero relações cross-act/cross-version).
O alvo da prisão perpétua possui parent direto vigente e normativo; a composição
real é `não haverá penas: de caráter perpétuo;`. O ponto de materialização foi
identificado em `build_evidence_set`, na criação de `EvidenceItem.text_snapshot`,
antes do tuple enviado ao generator; sua integração VCSA permanece inconclusiva.

No estado de sítio, a SECTION real possui três artigos diretos; a resolução
controlada encontrou os caputs de 137, 138 e 139. Com `parent_rrf * 0.85`, os
filhos foram promovidos como candidatos, mas ficaram abaixo do top-10 final
(target rank 11), e a seleção existente não os escolheu. A expansão portanto
não foi promovida.

Os testes focais passaram (11 testes). Ruff e `git diff --check` passaram. A
suíte completa executada no host resultou em 305 passed, 1 failed, 5 skipped e
96 errors, pois os testes host-side apontam para `localhost:5433`, que não é
acessível neste sandbox; os testes dentro do container confirmaram o banco.

Nenhuma integração de produção, ingestão, E2E ou inferência foi realizada.
