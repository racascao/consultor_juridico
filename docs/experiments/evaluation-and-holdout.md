# Avaliação e Blind HOLDOUT

O fluxo metodológico foi:

```text
DEV → análise de falhas → integrated DEV v2 → freeze
    → custódia externa do HOLDOUT → primeira medição → revisão humana
```

O DEV v2 obteve 30/32 passes automáticos e 30/32 all-pass humanos. Depois disso,
o runtime foi congelado como `integrated-runtime-mvp2/1`.

A campanha Blind HOLDOUT executou 36 casos uma única vez, sem retry, tuning ou
mutação. Houve 25/36 passes automáticos, 30/36 decisões esperadas, zero
citação inválida e zero out-of-evidence. A revisão humana registrou 34/36 em
correção, 36/36 em groundedness, 32/36 em completude e boundary 36/36.

Nove divergências automático/humano reforçaram que conformidade não substitui
avaliação jurídica. Sem threshold formal prévio, a decisão foi
`MVP2_ACCEPTED_WITH_KNOWN_LIMITATIONS`.

!!! danger "HOLDOUT fechado"
    Os casos privados não são publicados nem reutilizados como DEV. A direção
    permitida é DEV → HOLDOUT; nunca HOLDOUT → DEV.
