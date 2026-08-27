# Arquitetura da v0.2

## Objetivo

A v0.2 reconstrói o pipeline para resolver primeiro a relação entre a pergunta
e a evidência. Rastreabilidade continua obrigatória, mas não é tratada como
prova de que a evidência responde ao alvo correto.

## Camadas

- **Domain:** objetos e decisões imutáveis, sem frameworks.
- **Application:** ports e workflow; depende apenas do domínio e, na camada de
  orquestração, do LangGraph.
- **Infrastructure:** adapters futuros que implementarão os ports.
- **CLI:** composition root e apresentação; não contém regras de negócio.

## Workflow

```text
CLI
  -> ConsultationGraph (LangGraph)
  -> CandidateRetriever
  -> EvidenceRelevanceJudge
  -> Ambiguity Resolution
  -> AnswerGenerator
  -> AnswerJudge
  -> CitationValidator
  -> Result
```

O julgamento de relevância produz `CLEAR`, `AMBIGUOUS` ou `UNSUPPORTED`.
Ambiguidade pausa o grafo com `interrupt()` e pode ser retomada com `Command`.

O julgamento de resposta produz `ACCEPT`, `REWRITE`, `RETRIEVE_AGAIN` ou
`ABSTAIN`. `REWRITE` volta ao gerador; `RETRIEVE_AGAIN` volta ao retriever. Os
três loops são limitados e resultam em abstenção quando esgotados.

LangGraph não executa retrieval, SQL, HTTP, regras jurídicas ou formatação. As
dependências chegam por um contexto tipado e não são persistidas no estado.

## Estado atual

A Fase 0.2.1 implementa somente contratos, tipos, grafo e testes com fakes. Não
há adapters reais, integração com a CLI, checkpointer PostgreSQL ou inferência.
