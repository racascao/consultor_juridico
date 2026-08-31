# Governança do HOLDOUT

## Estado

```text
HOLDOUT_CUSTODIAN: USER
HOLDOUT_CREATED: NO
HOLDOUT_READ: NO
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

## Fase 0

Na Fase 0 não existem DEV, HOLDOUT de conteúdo, retrieval evaluation ou answer
evaluation. A única entrega deste documento é registrar antecipadamente a
separação de responsabilidades.
