# Arquitetura

## Pipeline normativo

```text
Pergunta → PostgreSQL FTS → SearchUnits → expansão de filhos diretos
         → Evidence Assembly → Gemma4:12b → JSON estrito
         → Citation Validation → RagResult
```

O domínio define contratos imutáveis; a aplicação orquestra casos de uso; a
infraestrutura implementa PostgreSQL, HTTP e Ollama; a CLI compõe essas portas.
Essa separação permite testar regras sem serviços reais.

`RunRagQuery` cria o pedido de retrieval, materializa evidências, chama o
answerer congelado, interpreta o contrato e valida as citações. O
`EvidenceAssembler` inclui filhos diretos em ordem documental, com limites 8/24
e deduplicação por `stable_key`.

## Boundary de aplicação concreta

```text
CASE_APPLICATION → CLARIFY
                 → retrieval=NOT_EXECUTED
                 → answerer=NOT_EXECUTED
                 → citations=[]
```

O caller declara `LEGAL_RULE` ou `CASE_APPLICATION`; o texto nunca é
classificado implicitamente.

## Invariantes

- a fonte oficial é preservada como bytes e SHA-256;
- consulta não acessa a web;
- toda citação deve pertencer ao corpus e à evidência da consulta;
- contrato inválido falha fechado;
- Gold Evidence e HOLDOUT nunca alimentam o runtime.
