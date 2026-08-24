# Fase 10.1 — Refinamento do contexto da SEU

## Causa e política

A política anterior incluía todos os filhos normativos do mesmo tipo quando o
pai terminava em dois-pontos e possuía até doze filhos. Essa regra introduziu
simultaneamente proposições independentes — como os ramos obrigatório e
facultativo — na mesma unidade.

A política refinada adota `MINIMUM_SUFFICIENT_STRUCTURAL_CONTEXT`: elemento
determinante mais ancestrais textuais necessários. Siblings são excluídos por
padrão. Proximidade, mesmo pai ou pertença à enumeração não constituem
proveniência de suporte.

## Testes e invariantes

Os testes confirmam pai + filho dependente, alínea dependente, elemento
autossuficiente, exclusão de sibling conflitante, determinismo, snapshot
imutável e proveniência limitada aos elementos efetivamente utilizados.

- source fidelity: PASS;
- no hallucination: PASS;
- deterministic: PASS;
- provenance complete: PASS.

## A/B congelado

| Métrica | Baseline | SEU 10.1 |
|---|---:|---:|
| corretas | 4/10 | 5/10 |
| false abstentions | 6 | 5 |
| abstenção correta | 1/1 | 1/1 |
| unsafe | 0 | 0 |
| polarity rejections | 1 | 1 |
| semantic success | 4 | 5 |

`voto obrigatório` voltou a passar e o ganho de `liberdade de expressão` foi
preservado. A melhoria líquida sobre o baseline foi de um caso, portanto
`LOW_IMPACT`. `racismo` e `estado de sítio` permanecem em attribution;
`direito à vida` permanece bloqueado por falso sinal de exceção; pena de morte,
prisão perpétua e outros casos mantêm blockers upstream.

## Decisão

`SIBLING_POLLUTION: FIXED`, mas `STRUCTURED_EVIDENCE_CONTEXT_GATE: BLOCKED`.
O resultado 5/10 é promissor, porém insuficiente para justificar a integração
definitiva da SEU. A direção é `PROMISING_BUT_INSUFFICIENT` e a produção
permanece sem integração.

Próxima intervenção: mudar a estratégia para tratar os blockers residuais por
estágio, sem nova sequência de microtuning da SEU.
