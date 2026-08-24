# Fase 9.13 — Diagnóstico da regressão E2E

## Baseline

O repositório está limpo no commit `4f13fca` (Fase 9.12). PostgreSQL e Ollama
estão saudáveis. O `uv` do host não pôde ser usado porque `.venv` aponta para
um interpretador inexistente; as validações foram executadas no container
isolado. A configuração permanece Granite 3B como generator/judge,
`nomic-embed-text` como embedding, Alembic 005 e corpus oficial preservado.

## Comparação observada

| Indicador | Fase 9.11 | Fase 9.12 |
|---|---:|---:|
| respostas corretas | 6/10 | 1/10 |
| abstenções corretas | 1/1 | 1/1 |
| false abstentions | 4 | 9 |
| unsafe | 0 | 0 |
| Hybrid Hit@10 | 0,905 | 0,900 |

Os casos que eram corretos e regrediram foram: liberdade religiosa, racismo,
extradição, direito à vida e estado de sítio. A primeira divergência observada
é no EvidenceSet/selection: os candidatos mudam de ocorrência e ordem mesmo
quando a identidade esperada continua recuperada. Em alguns casos o estágio
seguinte é `GENERATOR_ABSTENTION`; em prisão perpétua aparece também
`SUFFICIENCY_FALSE_NEGATIVE`.

## Evidências e causa provável

O novo pool de dez itens introduziu ocorrências tematicamente relacionadas e,
em consultas curtas, deslocou a evidência determinante. A implementação de
9.12 também passou a considerar contexto pai e a ordenar por cobertura textual.
Isso explica uma interação entre seleção, diluição do EvidenceSet e suficiência;
não há evidência de alteração no guard de polaridade ou de unsafe acceptance.

O JSON histórico não contém um snapshot completo, imutável e comparável de cada
EvidenceSet da 9.11 (incluindo todos os scores e parent_context). Portanto não
é possível reconstruir com fidelidade os pares A/B exigidos para cinco
repetições sem inventar evidências. Nenhum benchmark de repetição foi tratado
como resultado válido nesta fase.

## Classificação

O diagnóstico histórico aponta para `MULTIFACTORIAL`, com forte componente de
`EVIDENCE_DILUTION` e `EVIDENCE_ORDER_SENSITIVITY`. A confirmação causal por
repetições congeladas permanece inconclusiva.

Não foi implementado Structured Evidence Unit, nem qualquer alteração de
produção nesta fase. A próxima intervenção recomendada é criar snapshots
versionados de EvidenceSet por consulta e repetir o experimento A/B congelado;
só depois decidir entre redução de diluição e ordenação determinante.

## Validação

- Ruff format/check: aprovado no container.
- Suíte pytest: executada no container; conclusão deve ser registrada após o
  encerramento do processo.
- Nenhuma migration, ingestão, alteração de corpus ou `raw_bytes` foi feita.
- Nenhum commit foi criado nesta fase.

