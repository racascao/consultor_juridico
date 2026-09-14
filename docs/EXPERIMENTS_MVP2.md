# Experimentos e caminhos avaliados no MVP2

## 1. Princípios metodológicos

O MVP2 isolou uma hipótese geral por experimento, proibiu regras por caso e
separou qualidade jurídica de conformidade do contrato. Métricas automáticas não
substituíram revisão humana. Datasets, outputs e freezes foram identificados por
hash; o Blind HOLDOUT só foi lido depois do freeze e nunca orientou implementação.

## 2. Retrieval

| Problema | Experimento | Resultado | Decisão |
|---|---|---|---|
| FTS estrito falhava em perguntas naturais | `RELAXED_OR` | Hit@10 0,800 | Aceitar OR |
| Candidatos relevantes diluídos | Cobertura lexical | Hit@10 0,875; MRR 0,661 | Selecionar coverage |
| Frequência distorcia score | Peso por frequência documental | DEV Hit@10 0,900 | Integrar |
| Regra dividida entre pai e filhos | Expandir filhos diretos | HOLDOUT 26/44 → 40/44 | Integrar limites 8/24 |
| Misses heterogêneos | Fusão lexical/RRF geral | Regressão sem recuperar tudo | Rejeitar |

O runtime final ficou com PostgreSQL FTS
`RELAXED_OR_WEIGHTED_COVERAGE` e expansão estrutural. Os resíduos eram de
vocabulário, representação e diluição multipart; nenhum ajuste geral adicional
demonstrou ganho líquido antes do freeze.

## 3. Embeddings, vetor e RRF

Busca vetorial, diferentes embeddings e RRF foram avaliados nas investigações
anteriores ao redesign. A complexidade e a variabilidade aumentaram sem superar
estavelmente o lexical neste piloto. Eles não integram o MVP2 e só devem ser
reconsiderados com novo corpus, DEV independente e ganho causal mensurável.

## 4. Seleção do answerer

Gold Evidence isolou o modelo do retrieval. Qwen3 4B e Qwen3.5 9B apresentaram
aplicação factual prematura. Phi-4 Mini teve inversão de polaridade e baixa
completude. Gemma3 combinou baixa conformidade de envelope com risco decisório.
A tabela completa está em [ARCHITECTURE_MVP2.md](ARCHITECTURE_MVP2.md).

Gemma4 12B foi materialmente mais forte (`32/32` em correção e groundedness),
mas falhava no envelope. Alterar somente `format=json` levou JSON válido de
`13/32` a `32/32`, automatic pass de `12/32` a `30/32` e estabilidade de `5/12`
a `12/12`, sem regressão humana. Isso justificou sua seleção.

As execuções de estabilidade variaram apenas a seed. `GOLD-012` foi probe de
negação/polaridade, nunca regra runtime específica. A revisão material permaneceu
separada do evaluator automático.

## 5. Prompt engineering

O prompt v1 deixou ambígua a justificativa em abstenções. O v2 clarificou apenas
o objeto JSON com `decision`, `answer` e `citations`. O v3 testou a clareza do
rótulo `EVIDENCE_ID`, não teve ganho global e foi rejeitado. O prompt final é
`gold-evidence-answering/2`; não houve nova versão ou tuning pós-HOLDOUT.

## 6. QueryMode e arquitetura de dois modos

O DEV revelou `PREMATURE_FACTUAL_APPLICATION`: pergunta e evidência não
representavam fatos necessários e ausentes. Status quo, fatos incompletos,
requisitos produzidos pelo answerer, segundo LLM e validators probabilísticos
mantinham risco ou complexidade sem verdade determinística.

O contrato `F_TWO_MODE_CONTRACT` foi escolhido:

```text
LEGAL_RULE → pipeline RAG congelado
CASE_APPLICATION → CLARIFY determinístico, sem retrieval ou LLM
```

O modo explícito foi preferido a classifier implícito, gate probabilístico,
segundo LLM e heurísticas. Ele contém o risco sem alegar aplicação factual.

## 7. DEV integrado

O DEV v1 obteve `24/32` all-pass humano e revelou dois misses e seis falhas de
clarificação. A análise rejeitou fusão regressiva e levou aos dois modos. O DEV
v2 obteve `30/32` automatic pass e `30/32` all-pass; seis casos
`CASE_APPLICATION` retornaram `CLARIFY` sem retrieval/LLM. Dois misses normativos
heterogêneos foram aceitos e o runtime foi congelado.

## 8. Blind HOLDOUT

A campanha única executou 36 casos contra `integrated-runtime-mvp2/1`, sem retry,
tuning ou mutação. Obteve `25/36` passes automáticos, `30/36` decisões esperadas,
zero citação inválida e zero out-of-evidence. A revisão humana registrou `34/36`
em correção, `36/36` em groundedness, `32/36` em completude e boundary `36/36`.

Houve nove divergências automático × humano. Um risco automático em evidência
insuficiente não foi confirmado substantivamente, mas resultado e gold foram
preservados. Sem threshold formal pré-HOLDOUT, a decisão foi qualitativa:
`MVP2_ACCEPTED_WITH_KNOWN_LIMITATIONS`. O HOLDOUT está fechado e seus casos não
são reproduzidos aqui.

## 9. Lições herdadas do MVP1

- medir componentes isoladamente antes de ampliar arquitetura;
- separar retrieval de capacidade do answerer;
- exigir evidência, proveniência e Citation Validation;
- congelar contratos antes da avaliação final;
- preferir abstenção a proposição não sustentada;
- consolidar documentação e artifacts ao encerrar um ciclo.

## 10. Caminhos que não devem ser repetidos automaticamente no MVP3

| Caminho | Resultado no MVP2 | Reconsiderar quando |
|---|---|---|
| Equal-weight RRF | Sem ganho geral; regressões | Novo DEV provar falha lexical sistemática |
| Tuning por caso | Proibido e não generalizável | Nunca como regra de produto |
| Prompt pós-HOLDOUT | Invalidaria a medição | Novo baseline/HOLDOUT independente |
| Inferir `QueryMode` | Boundary probabilístico | Contrato factual verificável |
| Automatic score = qualidade | Divergiu da revisão humana | Sempre exigir revisão substantiva |
| HOLDOUT como DEV | Destrói independência | Nunca; criar novo DEV |
| Segundo LLM factual | Complexidade sem verdade | Contrato mensurável justificar |
| Vector/RRF por expectativa | Complexidade injustificada | Ganho causal reproduzível |
