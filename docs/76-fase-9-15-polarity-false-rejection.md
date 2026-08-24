# Fase 9.15 — Polarity Guard False-Rejection Hardening

## Diagnóstico

As 18 execuções congeladas da Fase 9.14 produziam claims e attribution válida,
mas nenhuma passava pelo guard. A análise identificou duas causas gerais:

1. o recognizer não possuía sinais afirmativos para `garantida`, `assegurado`,
   `inviolável`, `inviolabilidade`, `protege` e `estabelece`;
2. `sem` era tratado como negação, gerando falso sinal em “sem distinção de
   qualquer natureza”.

## Correção

Foi adicionada a categoria diagnóstica `AFFIRMATIVE`, sem alterar as relações
de contradição. O token genérico `sem` foi removido da expressão de negação;
negações explícitas (`não`, `proibido`, `vedado`, etc.) continuam protegidas.

`CONSISTENT` continua significando apenas ausência de contradição detectável.
Claims sem sinais comparáveis continuam `UNRESOLVED` e permanecem bloqueadas
por fail-closed antes do Semantic Validator.

## Reexecução congelada

- liberdade religiosa: A `3/3` e B `3/3` chegaram ao Semantic Validator e
  terminaram respondidas;
- direito à vida: A/B permaneceram `UNRESOLVED` em claims que omitem exceção
  ou não apresentam sinal comparável;
- estado de sítio: A/B permaneceram `UNRESOLVED` porque os fragmentos em
  infinitivo não expressam polaridade suficiente.

Não houve claim legítima classificada como `CONTRADICTED`. As inversões de
prisão perpétua, voto obrigatório e permissão/proibição continuam cobertas
pelos testes de segurança.

## Limitação e decisão

O guard não foi transformado em Semantic Validator. O gate focal fica
aprovado quanto à eliminação de falsos `CONTRADICTED`, mas o fail-closed de
`UNRESOLVED` mantém algumas abstenções. A reavaliação real-world é necessária
para medir impacto, sem novo tuning nesta fase.

## Reavaliação real-world

Foi executada uma única avaliação: `2/10` respostas corretas, `1/1` abstenção
correta, `8` false abstentions, `0` unsafe answers e Hybrid Hit@10 `0,900`.
O release permanece bloqueado. Artefato: `evaluation/results/real_world_short_e2e_9_15.json`.
