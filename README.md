# Consultor Jurídico

Aplicação CLI-first de consulta jurídica baseada em fontes oficiais,
versionadas e rastreáveis.

## Estado do projeto

A versão `v0.1.0` é o release histórico congelado do MVP1 e permanece imutável.
Ela é também o último checkpoint técnico estável usado para reiniciar a branch
`mvp-v0.2`.

A primeira tentativa do MVP2 foi abandonada porque a complexidade e os
experimentos realizados não produziram qualidade prática satisfatória. A branch
continua identificada como `0.2.0.dev0`, mas não contém uma implementação ativa
do novo MVP2.

```text
MVP2_STATUS: REDESIGN_PENDING
MVP2_ARCHITECTURE: NOT_DEFINED
MVP2_PHASES: NOT_DEFINED
```

Restaurar a base técnica de `v0.1.0` não adota automaticamente a arquitetura do
MVP1 para o novo MVP2. Funcionalidades, decisões e métricas documentadas naquele
release pertencem ao baseline histórico e poderão ser mantidas, substituídas ou
removidas somente após nova decisão arquitetural.

Não há alegação atual de qualidade, acurácia ou prontidão do novo MVP2.

## Próximo passo

Antes de qualquer nova implementação, o projeto deve:

1. redefinir o objetivo funcional do MVP2;
2. definir critérios de sucesso do produto;
3. definir uma estratégia de avaliação e generalização;
4. escolher a arquitetura mínima capaz de atender esses critérios;
5. somente então planejar a implementação.

O charter do reinício está em
[`docs/v0.2/restart.md`](docs/v0.2/restart.md).
