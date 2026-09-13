# Análise geral de falhas do Integrated DEV v1

## Integridade e escopo

A revisão humana preenchida foi validada pelo SHA-256
`6eeea6b13d26e4f9824333f5c208a98f1e5382d12e29316080d0b5f9e3e396ec`.
Os quatro artefatos da primeira campanha permaneceram byte-identical. Esta
análise não executou LLM, não abriu HOLDOUT e não modificou modelo, prompt,
freeze, retrieval ou Citation Validation.

## Retrieval

Os dois misses não possuem uma única causa homogênea:

- `GOLD-003`: a consulta usa “renunciada”, enquanto a disposição usa
  “irrenunciável”. A normalização portuguesa do PostgreSQL não aproxima esses
  lexemas. O alvo ficou no rank 35 ponderado e 19 no OR simples.
- `GOLD-016`: a pergunta combina dever de decidir e prazo. O artigo do prazo
  ficou no rank 1, mas o artigo do dever caiu para 34. Separada offline, a
  cláusula do dever ainda deixou o alvo no rank 11.

Um experimento geral fundiu, por RRF igual com `k=60`, os rankings OR simples e
weighted coverage, ambos em profundidade 100. Ele não recuperou nenhum dos dois
casos e degradou o DEV:

| Métrica | Runtime atual | Fusão experimental |
|---|---:|---:|
| Hit@1 | 0,650 | 0,600 |
| Hit@3 | 0,800 | 0,725 |
| Hit@5 | 0,850 | 0,775 |
| Hit@10 | 0,900 | 0,875 |
| MRR | 0,740625 | 0,677292 |
| Gold required | 27/34 | 26/34 |

O experimento foi rejeitado. Aumentar o top-k até 35 adicionaria ruído amplo e
não constitui uma correção mínima segura. Resolver o primeiro caso exigiria
aproximação lexical/semântica; resolver o segundo exigiria política multipart
mais forte. Nenhuma delas está justificada conjuntamente pelos dois sintomas.

## Clarificação e aplicação factual

Os seis casos ambíguos reproduzem a classe
`CONCRETE_FACTUAL_APPLICATION_WITH_MISSING_MATERIAL_FACTS`. Em cinco casos o
answerer respondeu com regra condicional sem pedir fatos; em `GOLD-029`, aplicou
prematuramente uma permissão abstrata e não recebeu as limitações materiais do
artigo 13.

O input estrutural atual contém pergunta e evidência jurídica, mas não separa
fatos alegados, fatos necessários ou fatos ausentes. Portanto, um gate
determinístico não consegue concluir genericamente que faltam fatos sem antes
interpretar semanticamente a pergunta. Regras por pronomes ou frases seriam
frágeis e expressamente proibidas. Também não existe relação estrutural objetiva
que permita expandir do artigo 12 para o artigo 13; expansão por vizinhança
introduziria ruído sem justificativa geral.

Assim, `GENERAL_FACTUAL_SUFFICIENCY_GATE` permanece `NOT_JUSTIFIED_YET`. Nenhum
gate ou alteração de prompt foi implementado. `ABSTAIN` e Citation Validation
permanecem inalterados.

## Decisão

```text
RETRIEVAL_GENERAL_FIX_JUSTIFIED=NO
GENERAL_FACTUAL_SUFFICIENCY_GATE_JUSTIFIED=NO
RUNTIME_FIX_IMPLEMENTED=NO
NEXT_ACTION=RECONSIDER_GENERAL_FIX
```

O runtime não deve ser congelado com `RISK-01` ainda presente. A próxima decisão
arquitetural deve escolher entre enriquecer deterministicamente a representação
da consulta/fatos ou autorizar um mecanismo semântico próprio, e tratar a lacuna
lexical/multipart do retrieval em experimento separado.

A reconsideração posterior escolheu o menor limite seguro: um contrato explícito
`LEGAL_RULE | CASE_APPLICATION`. O primeiro modo reutilizará o pipeline; o
segundo retornará clarificação local enquanto factual sufficiency completa não
for verificável. Consulte
[`factual-sufficiency-architecture-reconsideration-v1.md`](factual-sufficiency-architecture-reconsideration-v1.md).

O contrato foi implementado posteriormente: `LEGAL_RULE` preserva o pipeline e
`CASE_APPLICATION` retorna `CLARIFY` local, sem retrieval ou LLM. Assim, os
riscos `RISK-01` e `RISK-05` ficam contidos por intenção explicitamente declarada,
sem alegar factual sufficiency automática.

Os smokes manuais confirmaram ambos os caminhos. O evaluator da nova medição
foi preparado com mapping externo e sem alterar este diagnóstico v1. A execução
manual e revisão do DEV v2 confirmaram a contenção dos riscos de modo; os misses
heterogêneos `GOLD-003` e `GOLD-016` foram conscientemente aceitos no freeze.
