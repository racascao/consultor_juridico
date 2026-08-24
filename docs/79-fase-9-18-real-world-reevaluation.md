# Fase 9.18 — Reavaliação Real-World pós Boundary Routing

## Execução

Foi executada uma única avaliação `real_world_short_v1`, com a configuração
default vigente e sem tuning. A Fase 9.17 estava commitada (`eacc736`) e o
working tree estava limpo antes da execução.

## Resultado

| Métrica | Fase 9.15 | Fase 9.18 |
|---|---:|---:|
| Respostas corretas | 2/10 | 4/10 |
| False abstentions | 8 | 6 |
| Abstenção correta | 1/1 | 1/1 |
| Unsafe answers | 0 | 0 |
| Retrieval Hit@10 real-world | 0,900 | 0,900 |

Casos recuperados: `extradição` e `idade para ser presidente`. Não houve
regressões nos casos que já eram corretos.

## Primeiro estágio das falhas

- `EVIDENCE_SELECTION_MISS`: pena de morte, liberdade de expressão (2);
- `SUFFICIENCY_FALSE_NEGATIVE`: prisão perpétua (1);
- `GENERATOR_ABSTENTION`: racismo, direito à vida (2);
- `RETRIEVAL_MISS`: estado de sítio (1).

O caso `aborto` permaneceu `CORRECT_ABSTENTION`. Unsafe answers e cadeias de
citação inválidas permaneceram zero.

## Efeito do boundary routing

Na execução real-world não houve ocorrência roteada com sucesso como
`UNRESOLVED + NO_POLARITY_RELATION`; portanto, o resultado não demonstra ganho
end-to-end direto dessa classe. O boundary não introduziu regressões nem
relaxou o fail-closed. O detalhe operacional da consulta `direito à vida`
permaneceu bloqueado por validação de polaridade/atribuição em uma claim.

## Gates e decisão

Hit@10 do MVP1 permanece 0,905 e o real-world 0,900. O release gate continua
`BLOCKED`: 4/10 é inferior ao mínimo de 9/10. O maior grupo individual de
falhas é `GENERATOR_ABSTENTION` (2), empatado em impacto agregado com as
falhas de seleção/recuperação quando considerados os demais estágios.

Próxima intervenção única recomendada: diagnóstico focal do Generator
Abstention. Nenhuma correção foi implementada nesta fase.
