# Contrato de consulta em dois modos do MVP2

## Decisão implementada

`FACTUAL_SUFFICIENCY_ARCHITECTURE=IMPLEMENTED_TWO_MODE_CONTRACT`. Toda entrada
do fluxo RAG declara `LEGAL_RULE` ou `CASE_APPLICATION`; o sistema nunca infere
o modo pelo texto da pergunta.

`LEGAL_RULE` preserva o retrieval
`POSTGRESQL_FTS_RELAXED_OR_WEIGHTED_COVERAGE`, a expansão estrutural
`DIRECT_CHILDREN_ONLY`, o assembly, o answerer `gemma4:12b`, o prompt
`gold-evidence-answering/2`, o freeze `gold-evidence-selected-answerer/1` e a
Citation Validation existentes.

`CASE_APPLICATION` retorna imediatamente `CLARIFY`, com evidências e citações
vazias. O desvio acontece antes de sessão de banco, retrieval e cliente Ollama;
seu trace registra `retrieval=NOT_EXECUTED`, `answerer=NOT_EXECUTED` e
`reason=CASE_APPLICATION_NOT_SUPPORTED_IN_MVP2`.

## Limite do produto

O MVP2 explica regras jurídicas no modo normativo. Ele ainda não possui contrato
verificável de fatos alegados, necessários, presentes e ausentes; por isso não
aplica conclusivamente a regra a um caso concreto. A contenção explícita evita
heurísticas por pronomes, pergunta, dispositivo ou caso de benchmark.

## Validação determinística

Os seis casos ambíguos congelados (`GOLD-027..032`) foram mapeados externamente
para `CASE_APPLICATION`: `6/6` retornaram `CLARIFY`, com zero chamadas de
retrieval e zero chamadas de LLM. O dataset DEV não foi alterado. Testes também
provam que perguntas arbitrárias não mudam a decisão desse modo e que
`LEGAL_RULE` continua atravessando o pipeline normal.

Essa verificação não é uma campanha Integrated DEV v2. Nenhuma inferência real
foi executada e o HOLDOUT permaneceu fechado.

## Freeze e próximo gate

O selected-answerer freeze continua válido: modelo, digest, prompt e generation
config não mudaram, e `CASE_APPLICATION` não usa o answerer. O próximo passo é o
usuário executar os dois smoke tests manuais; depois poderá ser executada a
Integrated DEV v2 com mapping externo de modos, antes do freeze do runtime.

Os dois smokes foram aprovados. O DEV v2 foi executado manualmente e confirmou
`6/6 CLARIFY`, zero retrieval, zero chamadas LLM e zero citações nos casos
`CASE_APPLICATION`. O contrato está congelado em `integrated-runtime-mvp2/1`.
