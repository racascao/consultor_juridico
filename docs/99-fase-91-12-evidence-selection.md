# Fase 91.12 — Evidence Selection Safety Gate

## Escopo

Esta fase investigou exclusivamente a Evidence Selection sobre os candidate
pools já congelados pela Fase 91.11. Não houve novo retrieval, LLM, Ollama,
E2E, alteração de RRF, expansão estrutural, reserve, prompt ou integração de
produção.

## Traço real

O harness `evaluation/evidence_selection_trace_91_12.py` reconstituiu os
`RetrievalCandidate` reais no PostgreSQL a partir do artefato 91.11 e aplicou
`select_evidence_candidates_with_diagnostics` de
`src/consultor_juridico/consultation/selection.py` com o orçamento congelado
de três itens.

Para `rw-estado-sitio`, o CAPUT do art. 137 estava na posição 11 do pool
`STRUCTURAL_RESERVE_1`, com provenance estrutural e score `0,042578...`.
Possuía cobertura lexical integral; não foi descartado por deduplicação, tipo,
container ou origem estrutural. Foi rejeitado como
`REJECTED_AS_REDUNDANT_OR_BY_LIMIT`: os três slots já foram ocupados pela
função de relevância/marginalidade existente.

O CAPUT do art. 138 não pertence ao reserve de tamanho 1; aparece apenas no
reserve 2. O art. 139 segue a mesma condição. O selector não lê
`structural_score`, logo não há penalidade de origem estrutural a corrigir
nesta camada.

## Falhas observadas

Os dois alvos não selecionados no baseline foram:

- `rw-voto-obrigatorio`: CAPUT do art. 14 rejeitado por orçamento/marginalidade
  diante de um inciso lexicalmente mais específico;
- `rw-estado-sitio`: CAPUT do art. 137 rejeitado por orçamento/marginalidade
  diante dos três candidatos já escolhidos.

Em ambos os casos, o diagnóstico é `SELECTION_BUDGET + MARGINAL_GAIN`, não
deduplicação, preferência de tipo ou tratamento incorreto de provenance.

## Decisão

Não há correção segura dentro do escopo desta fase. Alterar pesos, limiares ou
orçamento apenas para fazer os alvos entrarem seria tuning oportunista,
expressamente proibido. Por não existir bug nem invariante violada, não foi
implementada mudança no selector e os controles sintéticos de uma correção
proposta não se aplicam.

`rw-aborto` permaneceu `INSUFFICIENT`. A seleção final de evidências
estruturais não foi integrada, e o caminho de Structural Retrieval continua
inconclusivo.

## Resultado

`EVIDENCE_SELECTION_FIX=INCONCLUSIVE`.

O artefato auditável está em
`evaluation/results/model_benchmark_91_12/evidence_selection_gate.json`.
