# Fase 9.17 — Boundary Polarity → Semantic Validation

O Polarity Guard passou a produzir `reason_code` determinístico sem alterar os
três estados públicos. `NO_POLARITY_RELATION` identifica ausência de relação
comparável; `EXCEPTION_SCOPE_AMBIGUITY` identifica exceção material omitida.

Foram analisadas as 12 execuções congeladas de `direito à vida` e `estado de
sítio`. As 6 execuções sem relação foram encaminhadas ao Semantic Validator:
6/6 foram avaliadas sem erro técnico e houve 0 unsafe acceptance. As 6 com
ambiguidade de exceção permaneceram bloqueadas. O experimento não executou
retrieval, selection ou generator.

Política integrada: `CONTRADICTED` rejeita; `CONSISTENT` segue ao Semantic;
`UNRESOLVED` só segue com `NO_POLARITY_RELATION`; demais causas permanecem
fail-closed. Isso não transforma `UNRESOLVED` em `SUPPORTED`.

`BOUNDARY_ROUTING_GATE: APPROVED`. Hit@10 MVP1: 0,905; real-world: 0,900.
Controles de inversão e exceção permaneceram protegidos. Nenhuma migration,
ingestão ou alteração de corpus foi executada.
