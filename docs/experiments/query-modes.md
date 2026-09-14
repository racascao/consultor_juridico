# Experimentos de Query Modes

## Problema

O DEV revelou `PREMATURE_FACTUAL_APPLICATION`: uma pergunta sobre caso concreto
não continha fatos estruturados suficientes, mas o answerer podia completar
lacunas implicitamente.

## Alternativas avaliadas

Classifier, LLM router, heurísticas textuais e gates probabilísticos adicionavam
outra decisão não auditável sem fornecer verdade factual.

## Decisão

```text
LEGAL_RULE       → RAG completo
CASE_APPLICATION → CLARIFY determinístico, sem retrieval/LLM
```

O caller escolhe explicitamente. A interface humana apresenta as opções
"Consultar uma regra jurídica" e "Perguntar sobre uma situação concreta".
Reconsiderar roteamento automático apenas quando houver contrato factual
verificável, não por conveniência de UX.
