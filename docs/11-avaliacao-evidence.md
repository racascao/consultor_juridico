# Avaliação de Grounding e Citações

Além de métricas tradicionais de retrieval, o MVP deve medir:

- Evidence Validity Rate
- Source Recall
- Citation Correctness
- Citation Completeness
- Evidence Coverage
- Unsupported Claim Rate
- Hallucination Rate
- latência CPU

## Unsupported Claim Rate

```text
claims factuais sem evidência válida
-------------------------------------
claims factuais totais
```

A seleção do modelo local deve considerar a qualidade do sistema completo, e não somente o tamanho do modelo.
