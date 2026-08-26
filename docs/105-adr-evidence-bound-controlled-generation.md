# ADR 105 — Evidence-Bound Controlled Generation no MVP1

## Contexto

O segundo E2E (`3/10`, `unsafe=0`) mostrou que a geração livre acrescenta
claims auxiliares, locators incorretos ou abstenções, mesmo quando o EvidenceSet
já contém uma evidência autorizada. Atomic, VCSA e expansões estruturais foram
testados, mas não possuem integração aprovada.

## Decisão

Adotar EBCG-v1: uma única Core Claim reproduz exatamente o snapshot de `EV001`,
o primeiro código definido pela seleção existente. O LLM não gera claims
jurídicas; permanece somente como veto semântico fail-closed.

## Consequências

- A autoria jurídica passa do modelo para o EvidenceItem auditável.
- Attribution, Locator, Citation e Polarity continuam obrigatórios.
- Não há novo ranking, seleção, schema, guard ou componente experimental.
- Consultas que dependam de composição de múltiplas evidências podem abster-se.

## Alternativas rejeitadas

- novo prompt tuning: já não eliminou as claims laterais de forma confiável;
- Atomic: exige classificadores não aprovados de `core_answer` e dependência;
- VCSA: composição pai-filho não está aprovada para produção;
- nova seleção/ranking: explicitamente fora do escopo desta decisão.
