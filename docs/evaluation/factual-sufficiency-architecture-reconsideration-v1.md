# Reconsideração arquitetural de factual sufficiency

## Problema

O contrato atual contém apenas pergunta e evidência jurídica. Ele não representa
fatos alegados, fatos necessários nem fatos ausentes. Por isso, não é possível
distinguir deterministicamente uma explicação normativa de uma aplicação
concreta incompleta. O Integrated DEV demonstrou `RISK-01` em `GOLD-029` e
`RISK-05` nos seis casos ambíguos.

Esta revisão considerou a human review e a análise geral pelos hashes
`6eeea6b...396ec` e `e3535ea...eeb7`. Não houve alteração de runtime, prompt,
modelo, retrieval ou freeze; nenhuma inferência foi executada.

## Comparação

| Alternativa | Safety | Determinismo | Complexidade | Chamadas LLM | Prompt/freeze | CLI | Decisão |
|---|---|---|---|---:|---|---|---|
| A — status quo | baixa | alta | baixa | 1 | preservados | não | rejeitada: mantém RISK-01 |
| B — structured user facts | média | média | média | 1 | invalida | sim | insuficiente sozinha |
| C — requisitos pelo answerer | média | baixa | média | 1 | invalida | não | rejeitada: requisitos não verificáveis |
| D — estágio semântico prévio | média | baixa | alta | 2 | invalida | não | rejeitada para o MVP2 |
| E — validador semântico posterior | média | baixa | alta | 2 | invalida | não | rejeitada para o MVP2 |
| F — contrato de dois modos | alta | alta | baixa | 1 ou 0 | preservados | sim | recomendada |

### A — Status quo

É simples e testável, mas o `RISK-01` impede o freeze. Respostas condicionais não
eliminam a possibilidade de aplicação factual prematura.

### B — Structured user facts

Separar `question` e `facts` melhora rastreabilidade, porém não informa quais
fatos são juridicamente necessários. Sozinha, a alternativa apenas desloca o
problema. Para usar esses fatos na geração seria necessário alterar o prompt e
reavaliar o answerer.

### C — Fact requirements produzidos pelo answerer

Exige novo contrato e prompt. Como os requisitos seriam declarados pelo mesmo
modelo que será validado, não há fonte determinística para comprovar completude.

### D — Estágio semântico pré-answer

Classifica intenção e suficiência, mas introduz segunda chamada, nova política e
duplicação de inteligência. A saída continuaria probabilística.

### E — Validação pós-answer

Pode vetar aplicações perigosas, mas precisa interpretar semanticamente
pergunta, resposta e evidência. Na prática vira outro judge e atua somente após
a geração potencialmente insegura.

### F — Two-mode contract

O usuário declara explicitamente `LEGAL_RULE` ou `CASE_APPLICATION`. Isso torna
a intenção parte do contrato, sem heurística escondida:

```text
LEGAL_RULE
→ retrieval e answerer congelado atuais

CASE_APPLICATION
→ CLARIFY determinístico
→ nenhuma chamada ao answerer no MVP2
```

O modo concreto poderá receber `facts` em uma evolução futura, mas só deverá
produzir aplicação quando existir um contrato verificável de fatos necessários.
Até lá, a limitação é explícita: o MVP2 explica regras jurídicas, mas não decide
se elas se aplicam definitivamente ao caso particular.

## Decisão congelada para a próxima implementação

Recomenda-se `F_TWO_MODE_CONTRACT` como limite de escopo fail-closed:

1. criar enum de domínio `LEGAL_RULE | CASE_APPLICATION`;
2. exigir modo explícito na fronteira pública de consulta;
3. manter o pipeline atual byte-semanticamente igual para `LEGAL_RULE`;
4. retornar `CLARIFY` local para `CASE_APPLICATION`, sem retrieval/modelo se não
   houver benefício auditável em recuperar a regra;
5. registrar o motivo no trace;
6. testar perguntas normativas, aplicações concretas e preservação de ABSTAIN;
7. adaptar o harness DEV com modo declarado, sem inferência heurística.

Essa solução contém `RISK-01`, mas não afirma implementar factual sufficiency
completa. Ela não exige novo prompt, invalidação do freeze ou segundo LLM. A
mudança de CLI/contrato foi implementada com modo obrigatório e sem inferência
automática. `CASE_APPLICATION` desvia antes de banco, retrieval e cliente Ollama;
`LEGAL_RULE` preserva o fluxo congelado.

## Próximo passo

Executar os smoke tests manuais dos dois modos e, depois, Integrated DEV v2 antes
de qualquer freeze. O HOLDOUT permanece fechado.

Os smokes foram aprovados e o DEV v2 foi executado manualmente com mapping
externo. Os seis casos concretos retornaram `CLARIFY` sem retrieval ou LLM, e o
contrato passou a integrar o freeze `integrated-runtime-mvp2/1`.
