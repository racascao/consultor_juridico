# Fase 9.19 — Diagnóstico Focal de Generator Abstention

## Baseline e método

Foram congelados os EvidenceSets efetivamente enviados ao Generator na Fase
9.18. O `racismo` tinha dois itens diretamente normativos (repúdio e crime
inafiançável/imprescritível); `direito à vida` tinha o caput do art. 5º e os
contextos dos arts. 230 e 227. Ambos foram classificados como
`MATERIALLY_SUFFICIENT`.

O Generator `granite4.1:3b` foi executado cinco vezes por caso, com prompt,
ordem, schema e temperatura de produção congelados.

## Resultado P0

| Caso | Respostas | Abstenções | JSON inválido | Primeiro bloqueio downstream |
|---|---:|---:|---:|---|
| racismo | 5/5 | 0/5 | 0 | ATTRIBUTION_FAILURE |
| direito à vida | 5/5 | 0/5 | 0 | POLARITY_UNRESOLVED_FAIL_CLOSED |

Logo, os dois `GENERATOR_ABSTENTION` identificados na avaliação end-to-end
eram classificações do resultado final, não abstenções produzidas pelo
Generator. O Generator respondeu em 10/10 execuções. No caso `racismo`, a
atribuição determinística recusou a claim; em `direito à vida`, uma claim foi
bloqueada pelo guard de exceção.

## Contrafactual P1

Não executado: o protocolo só autoriza P1 se as cinco repetições P0 forem
abstenções; isso não ocorreu em nenhum caso. Portanto não há evidência para
classificar o prompt como conservador.

## Conclusão

A causa não é `PROMPT_OVERCONSERVATIVE`, `MODEL_VARIANCE` ou contrato JSON. O
diagnóstico aponta `EVIDENCE_REPRESENTATION`: o blocker ocorre depois da
geração, na atribuição/validação da cadeia de evidência. Não houve unsafe
acceptance. A próxima intervenção única recomendada é diagnosticar a
atribuição/representação da evidência, sem alterar o prompt de abstention.

Nenhum componente de produção foi alterado nesta fase.
