# ADR 108 — Core Evidence Policy v2

## Contexto

EBCG-v1 projetava sempre `EV001` como Core Evidence. Esse código representa a
posição final da seleção, não uma garantia de aderência à pergunta. A auditoria
offline da Fase 96 mostrou 5 hits de target com v1 e 7 com a política v2
determinística, sem qualquer acesso de produção a labels dourados.

## Decisão

EBCG-v2 escolhe uma única EvidenceItem já autorizada nesta ordem:

```text
query_coverage
→ marginal_coverage
→ base_relevance
→ menor selected_position
→ menor código EvidenceItem
```

Os quatro primeiros sinais já são derivados pela Evidence Selection existente e
ficam congelados no metadata da EvidenceItem para auditoria. A política não
altera retrieval, ranking, selection, limites, thresholds ou EvidenceSet.

## Consequências

- A Core Claim segue sendo o `text_snapshot` literal da Core Evidence.
- A resposta possui uma claim e uma evidence code; não há parent composition,
  fallback, sumarização ou síntese multi-evidence.
- Ausência de signals ou Core Evidence inválida causa abstenção fail-closed.
- O LLM continua somente como veto semântico; não escolhe evidência nem gera
  proposição jurídica.
- `expected_provisions`, `acceptable_provisions`, datasets e case IDs continuam
  restritos à avaliação e não são parâmetros da política de produção.
