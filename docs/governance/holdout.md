# Governança do HOLDOUT

## Estado

```text
HOLDOUT_CUSTODIAN: USER
HOLDOUT_CREATED: YES
HOLDOUT_SEALED: YES
HOLDOUT_RUNTIME_FIRST_READ: YES
HOLDOUT_RUNTIME_FIRST_READ_AT: 2026-09-13T19:37:36.652025+00:00
HOLDOUT_RUNTIME_EXECUTED: YES
HOLDOUT_PACKAGE_CONTRACT: READY
HOLDOUT_QUERY_MODE_CONTRACT: READY
RUNTIME_FREEZE: integrated-runtime-mvp2/1
BLIND_HOLDOUT_FIRST_MEASUREMENT: COMPLETE
HOLDOUT_TUNING: NO
HUMAN_REVIEW_HOLDOUT: COMPLETE
MVP2_FINAL_DECISION: MVP2_ACCEPTED_WITH_KNOWN_LIMITATIONS
NEXT_ACTION: CLOSE_MVP2_WITH_KNOWN_LIMITATIONS
```

Este documento define somente a governança futura do conjunto HOLDOUT. Ele não
cria perguntas, respostas esperadas, targets ou qualquer dataset de avaliação.

## Custódia e separação de contexto

O usuário é o custodiante independente do HOLDOUT. O conteúdo do conjunto não
pode ser revelado na mesma sessão ou contexto em que decisões de implementação,
calibração ou tuning estejam sendo tomadas.

Enquanto o runtime ainda estiver sendo desenvolvido contra DEV, o implementador
poderá conhecer somente:

- `dataset_id`;
- quantidade de casos;
- distribuição por categoria;
- SHA-256 do conjunto congelado.

Perguntas, targets, respostas esperadas e resultados individuais permanecem sob
custódia exclusiva do usuário.

A validação estrutural local do pacote é uma `CUSTODY_VALIDATION_READ`: ela
confere formato, hashes e cobertura do mapping, sem imprimir o conteúdo. Essa
leitura de custódia não é a `HOLDOUT_RUNTIME_FIRST_READ`, que somente ocorre
quando o runtime congelado recebe o conjunto para a medição cega final.

## Condições para uso

O conteúdo real do HOLDOUT somente poderá ser apresentado quando todas estas
condições forem satisfeitas:

1. as iterações contra DEV estiverem encerradas;
2. o runtime, modelos, prompts, thresholds e demais variáveis relevantes
   estiverem congelados;
3. a avaliação ocorrer em sessão ou contexto independente daquele usado para
   implementação;
4. a execução for final e não houver tuning posterior orientado pelos casos.

Qualquer mudança no runtime depois da abertura do HOLDOUT invalida o caráter
cego da medição e exige um novo conjunto independente, novamente congelado sob
esta governança.

## Contrato público e pacote privado

Schemas e templates sem casos reais são versionados em `evaluation/holdout/`.
O pacote real foi criado e selado pelo usuário em `evaluation/holdout/private/`,
caminho ignorado pelo Git. O procedimento de criação, selagem e validação está em
`docs/governance/blind-holdout-custody-mvp2.md`.

## Primeira campanha

A primeira leitura pelo runtime e a campanha oficial única foram concluídas
contra o freeze `integrated-runtime-mvp2/1`. O pacote permaneceu byte-identical,
não houve retry nem tuning. A revisão humana foi concluída em `32/36` all-pass;
o risco automático em evidência insuficiente não foi confirmado materialmente.
O MVP2 foi aceito com limitações conhecidas. Métricas e hashes estão em
`docs/evaluation/blind-holdout-mvp2-v1.md`.

O HOLDOUT v1 está definitivamente encerrado como instrumento cego e não pode ser
convertido em dataset de desenvolvimento. Evoluções futuras exigem fase
metodológica pós-HOLDOUT, novo baseline e novos datasets DEV.
