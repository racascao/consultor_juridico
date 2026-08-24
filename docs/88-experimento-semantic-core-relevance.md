# Experimento 88 — Semantic Core Relevance

## Objetivo e limites

O experimento avaliou, sem integração de produção, a menor capacidade geral para
classificar `Query ↔ Verified/Core Assertion`. Ele não avaliou suporte da
assertion pela evidência, correção jurídica, completude, polaridade, retrieval
ou seleção. Os únicos dados foram os artefatos congelados das fases 12, 86 e 87.

O estado de sítio permaneceu sem core assertion VCSA e, portanto,
`SAFE_ABSTENTION`; nenhum mecanismo recebeu evidência lateral para respondê-lo.

## Estratégias

| Estratégia | Resultado | Observação |
|---|---|---|
| Lexical baseline | FAIL | Seguro contra os controles negativos, mas não reconhece variação semântica, inclusive `prisão perpétua` ↔ `penas de caráter perpétuo`. |
| `nomic-embed-text` | FAIL | Os controles não se separaram: máximo negativo `0,811347` excedeu mínimo positivo `0,757939`. A zona fail-closed tornou todas as 21 decisões `UNRESOLVED`. |
| Judge local `granite4.1:3b` | FAIL | Reconheceu os nove pares reais relevantes, mas aceitou sete dos nove controles negativos como relevantes. |

Os thresholds de embedding foram derivados **somente** dos controles gerais:
`irrelevant ≤ 0,811347`; `relevant ≥ 0,757939`. Como os intervalos se
sobrepõem, nenhum threshold seguro foi congelado. Não houve ajuste em função de
prisão perpétua.

## Controles e dados brutos

O resultado íntegro, incluindo Query, Core Assertion, decisão, motivo, latência,
score e resposta HTTP bruta do judge, está em
`evaluation/results/semantic_core_relevance_88.json`.

O contrato do judge recebeu apenas Query e Core Assertion normativa verificada.
Não recebeu case ID, provision esperada, resposta esperada ou label esperado.
O primeiro desenho de controle foi descartado e toda a matriz foi reiniciada:
dois controles (`PARTIAL_TRUE_ANSWER_TO_BINARY_QUERY` e
`CORRECT_TOPIC_WRONG_NORMATIVE_ROLE`) exigiam que relevância decidisse
completude/correção. Eles foram corretamente reclassificados como relevantes
para a Query, mas dependentes de validadores posteriores. Essa é uma correção
metodológica do harness, não uma mudança no pipeline.

Na matriz final, o judge aceitou indevidamente: `TRUE_BUT_IRRELEVANT`,
`SUPPORTED_BUT_OFF_TARGET`, `WRONG_LEGAL_ACTOR`,
`RELATED_PROVISION_WRONG_ANSWER`, `AUXILIARY_FACT_WITHOUT_CORE_ANSWER`,
`THEMATICALLY_SIMILAR_BUT_WRONG_RELATION` e
`SEMANTICALLY_CLOSE_BUT_IRRELEVANT`. Também rejeitou o controle relevante de
papel normativo oposto. Sua latência média foi `8,997 ms` por decisão; embedding
foi `90,632 ms` e lexical `0,024 ms`.

## Casos reais

- `pena de morte`: VCSA recuperou assertion literal e lexical/judge retornaram
  `RELEVANT`.
- `prisão perpétua`: lexical retornou `IRRELEVANT`; embedding ficou
  `UNRESOLVED`; o judge retornou `RELEVANT` para a assertion literal
  `não haverá penas: de caráter perpétuo`.
- Os sete pares históricos foram preservados pelo judge; lexical teve uma
  regressão e embedding sete, em razão do fail-closed.
- Estado de sítio não foi enviado ao judge nem ao embedding: permaneceu
  `SAFE_ABSTENTION` por ausência de assertion estrutural verificável.

O judge alcançou potencial aritmético de `9/10`, mas isso não é um resultado
adotável: os sete falsos relevantes invalidam o requisito `unsafe = 0` para uma
capacidade que poderia participar do produto.

## Decisão

Nenhuma estratégia é integrada. O experimento confirma que similaridade de
embedding isolada não é evidência suficiente de relevância material e que o
modelo local testado não é um árbitro seguro dessa boundary sozinho. A próxima
intervenção deve ser uma revisão de arquitetura/modelo para separar uma
assertion central verificável de uma decisão de adequação à pergunta, mantendo
os validadores de suporte, citação, polaridade e completude independentes.

Recomendação do worktree:

- SupportSlot, VCSA, Evidence-Bound e Answer Relevance/Core: `KEEP_EXPERIMENTAL`;
- Marginal Selection e Clause Attribution: `KEEP_FOUNDATION`;
- integração de relevance semântico no pipeline: `REWORK`.

Não houve alteração de produção, banco, corpus, retrieval, seleção, prompts de
produção, datasets, embeddings persistidos ou schema.
