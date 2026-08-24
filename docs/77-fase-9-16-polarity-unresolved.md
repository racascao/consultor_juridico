# Fase 9.16 — Diagnóstico de UNRESOLVED no Polarity Guard

## Resultado

Foram analisadas as 12 execuções congeladas que permaneciam `UNRESOLVED`, sem
retrieval, selection ou novas chamadas ao generator.

| Categoria | Execuções |
|---|---:|
| EXCEPTION_SCOPE_AMBIGUITY | 6 |
| NO_POLARITY_RELATION | 6 |
| STRUCTURAL_CONTEXT_REQUIRED | 0 |
| RULE_COVERAGE_GAP | 0 |
| GENUINELY_AMBIGUOUS | 0 |

## Direito à vida

As claims sobre o caput foram reconhecidas como afirmativas. As ocorrências
restantes ficaram `UNRESOLVED` quando a evidência continha uma exceção textual
(`a salvo de ...`) que não foi reproduzida pela claim. Isso é uma proteção
conservadora contra omissão material, não uma contradição.

## Estado de sítio

Os fragmentos selecionados contêm verbos no infinitivo (`decretar`, `autorizar`,
`aprovar`) e não expressam, por si, uma relação de permissão/proibição que o
guard possa comparar deterministicamente. A ausência de sinal é
`NO_POLARITY_RELATION`, não `CONTRADICTED`.

## Contrato arquitetural

Os três estados continuam suficientes:

- `CONTRADICTED`: inversão determinística demonstrável;
- `CONSISTENT`: relação reconhecida sem inversão;
- `UNRESOLVED`: exceção não preservada ou ausência de relação comparável,
  permanecendo fail-closed antes do Semantic Validator.

Não é necessário introduzir `NO_APPLICABLE_POLARITY` nesta fase; seria apenas
uma distinção diagnóstica dentro de `UNRESOLVED`, sem alterar a segurança.

## Métricas verificadas

- MVP1 Hybrid Hit@10: `0,9047619048` (`0,905` arredondado);
- real-world Hybrid Hit@10: `0,900`;
- unsafe acceptance: `0`.

Próxima intervenção recomendada: manter o contrato de três estados e tratar
claims `UNRESOLVED` como abstenção segura; não relaxar o fail-closed.

