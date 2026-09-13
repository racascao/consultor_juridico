# Integrated DEV v2 com modos explícitos

## Estado

`COMPLETE_FIRST_MEASUREMENT`. A campanha oficial foi executada manualmente pelo
usuário, sem retry ou tuning, e sua revisão humana foi concluída.

## Protocolo congelado

O dataset `lei_9784_gold_evidence_dev_v1` permanece byte-identical. O mapping
`integrated-dev-query-mode-mapping/1` atribui `LEGAL_RULE` a
`SINGLE_SUPPORT`, `COMPOSITE_SUPPORT` e `INSUFFICIENT_EVIDENCE`, e
`CASE_APPLICATION` a `AMBIGUOUS`.

No perfil `integrated-dev-v2-two-mode`, os 26 casos normativos percorrem o RAG
real congelado. Os seis casos concretos retornam `CLARIFY` local, sem retrieval,
LLM, resposta de modelo ou citações. Métricas de retrieval consideram somente
casos nos quais ele foi executado; latências normativas e determinísticas são
reportadas separadamente.

O evaluator cria artifacts `v2` novos, template humano com
`MODE_BOUNDARY_CORRECTNESS` e comparação v1/v2. Arquivos existentes nunca são
sobrescritos.

## Execução manual única

```bash
docker compose --profile llm build app

docker compose --profile llm run --rm \
  --volume "$PWD/evaluation:/app/evaluation" \
  app consultor-juridico eval rag-dev \
  --dataset evaluation/datasets/lei_9784_gold_evidence_dev_v1.json \
  --version-hash bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6 \
  --output-dir evaluation/results/integrated_dev_mvp2_v2 \
  --evaluation-profile integrated-dev-v2-two-mode \
  --query-mode-mapping evaluation/runs/integrated_dev_query_mode_mapping_v1.json
```

Depois do primeiro resultado completo, não repetir nem ajustar a campanha. Os
hashes devem ser calculados imediatamente e os artifacts preservados para a
revisão humana v2. O HOLDOUT permanece fechado.

## Resultados

Foram obtidos `31/32` expected decision match, `30/32` automatic pass e zero
resposta insegura por evidência insuficiente, missed clarification, citação
inválida, citação fora da evidência ou timeout. `CASE_APPLICATION` obteve `6/6`
clarificações com zero retrieval, LLM e citações.

A revisão humana obteve `31/32` em correção jurídica, `32/32` em grounding,
`30/32` em completude, `32/32` em mode boundary e `30/32` all pass. Os resíduos
são `GOLD-003` e `GOLD-016`. A cobertura integral de evidência registrada como
`24` tem denominador `26`: são `24/26` casos `LEGAL_RULE`; os seis casos
concretos não executam evidence assembly.

O runtime resultante foi congelado como `integrated-runtime-mvp2/1`. O HOLDOUT
continua fechado até o commit manual desse freeze.
