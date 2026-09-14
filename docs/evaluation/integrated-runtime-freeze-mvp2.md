# Freeze do runtime integrado do MVP2

## Estado congelado

`INTEGRATED_RUNTIME_FREEZE=COMPLETE`, identidade
`integrated-runtime-mvp2/1`. O freeze foi criado depois da primeira medição
Integrated DEV v2 e de sua revisão humana, e antes de qualquer leitura do
HOLDOUT.

```text
RUNTIME_CHANGED_AFTER_FREEZE: NO
MODEL_CHANGED: NO
PROMPT_CHANGED: NO
RETRIEVAL_CHANGED: NO
QUERY_MODE_CHANGED: NO
STRUCTURAL_EXPANSION_CHANGED: NO
CORPUS_CHANGED: NO
```

O modo `LEGAL_RULE` usa PostgreSQL FTS
`RELAXED_OR_WEIGHTED_COVERAGE`, expansão de filhos diretos (máximo 8 por pai e
24 evidências), o answerer congelado `gemma4:12b`, prompt
`gold-evidence-answering/2`, validação JSON estrita e Citation Validation. O
modo `CASE_APPLICATION` retorna `CLARIFY` deterministicamente sem retrieval,
answerer ou citações. O modo é sempre declarado pelo caller.

## Evidência de validação

O DEV v2 obteve `31/32` decisões esperadas e `30/32` automatic pass, sem
resposta insegura por evidência insuficiente, clarificação perdida, citação
inválida, citação fora da evidência ou timeout. Os seis casos
`CASE_APPLICATION` produziram `6/6 CLARIFY`, zero retrieval e zero chamadas ao
LLM.

A revisão humana registrou `31/32` em correção jurídica, `32/32` em grounding,
`30/32` em completude, `32/32` no boundary de modo e `30/32` all pass. A
cobertura integral de evidência é `24/26` entre casos `LEGAL_RULE`; os seis
casos concretos não pertencem ao denominador porque deliberadamente não
executam retrieval.

## Riscos aceitos

`GOLD-003` e `GOLD-016` permanecem misses heterogêneos de ranking lexical e
multipart. A fusão RRF geral previamente testada não os recuperou e degradou as
métricas globais; nenhum fix geral foi justificado ou integrado. O freeze não
afirma retrieval perfeito.

`RISK-01` e `RISK-05` estão contidos pelo contrato explícito de modos, não
eliminados do modelo. `RISK-04` permanece observado no nível sistêmico com causa
de retrieval em `GOLD-016`. `RISK-08` não foi medido porque a campanha foi uma
execução única.

## Proveniência e imutabilidade

O corpus congelado é a `ActVersion` local
`bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6`,
derivada do snapshot `b4abab2e...9261`. A URL oficial nas citações representa
proveniência; `runtime_web_fetch=NOT_IMPLEMENTED` não equivale a uma medição de
isolamento de rede.

O artifact canônico é
`evaluation/runtime_freeze/integrated_runtime_mvp2_freeze_v1.json`, acompanhado
por manifesto SHA-256; seu hash é
`5f0df6b41f0d35fcba0a514777a2370385620007ff3e6122473ca6793067514d`.
Qualquer mudança de modelo, prompt, configuração,
retrieval, corpus, expansão, modos ou validação invalida este freeze e exige nova
avaliação.

O Blind HOLDOUT v1 foi posteriormente criado e selado pelo usuário e executado
uma única vez contra este runtime imutável. O freeze permaneceu byte-identical,
sem tuning, retry ou mudança de configuração. A primeira medição automática foi
`25/36`; a revisão humana posterior obteve `34/36` em correção jurídica,
`36/36` em groundedness, `32/36` em completude e `32/36` all-pass. Sem threshold
formal pré-HOLDOUT, o MVP2 foi aceito com limitações conhecidas. Consulte
[`blind-holdout-mvp2-v1.md`](blind-holdout-mvp2-v1.md).

Essa decisão não altera o freeze. O HOLDOUT v1 não pode ser reutilizado como
DEV; qualquer evolução requer uma fase metodológica pós-HOLDOUT.
