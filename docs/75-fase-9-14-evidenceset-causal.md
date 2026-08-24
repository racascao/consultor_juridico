# Fase 9.14 — EvidenceSet Snapshotting e experimento causal A/B

## Baseline

O commit de referência é `4f13fca` (Fase 9.12). PostgreSQL/Ollama estão
saudáveis; o corpus e os defaults não foram alterados. A Fase 9.13 identificou
regressão E2E de 6/10 para 1/10, mas não possuía snapshots históricos.

## Snapshot diagnóstico

Foi criado `evaluation/snapshot_evidenceset_9_14.py`. O script executa retrieval
uma vez por caso, não grava no banco e exporta candidatos e selecionados com
texto, contexto pai, ranks/scores, IDs e provenance. A estratégia A é obtida
explicitamente do algoritmo anterior preservado no histórico; B usa o código
atual da Fase 9.12.

Resultado do snapshot dos cinco casos regressivos:

| Caso | A selecionados | B selecionados | Alteração principal |
|---|---:|---:|---|
| liberdade religiosa | 10 | 3 | B mantém a evidência determinante e remove ruído |
| racismo | 2 | 2 | conjunto equivalente |
| extradição | 4 | 3 | B remove uma ocorrência auxiliar |
| direito à vida | 10 | 3 | B mantém o caput e remove ruído |
| estado de sítio | 10 | 3 | B mantém candidatos principais e remove ruído |

Snapshots: `evaluation/results/evidenceset_9_14_AB.json`.

## Experimento downstream

O diagnóstico reduzido executou 18 repetições (3 casos × 2 estratégias × 3).
Em todas as 18 execuções o generator produziu claims e a attribution terminou
sem abstention. Todas foram rejeitadas pelo Polarity Guard antes do Semantic
Validator: A e B tiveram `FINAL_ANSWER_RATE = 0/9`, `POLARITY_PASS_RATE = 0/9`
e flip rate zero. Portanto A e B não diferiram no downstream observado.

O resultado não confirma diluição, undercoverage ou sensibilidade à ordem. A
causa observada é `DOWNSTREAM_VALIDATION_INTERACTION`: o guard rejeita claims
geradas sobre os snapshots. O Semantic Validator não foi executado após a
rejeição, logo não há base para classificar semantic false negative. A
validação de citações no harness foi apenas sintática contra os IDs congelados;
ela não substitui a validação persistida completa.

## Decisão

O experimento reduzido foi concluído, mas não reproduziu diferença A/B. A
única próxima intervenção recomendada é investigar o falso bloqueio do
Polarity Guard para claims materialmente corretas, usando fixtures e traces
dos casos regressivos. Não alterar o guard nesta fase.
