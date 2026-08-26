# Fase 97 — Inventário pré-limpeza

## Método

Inventário produzido no estado Git limpo posterior à Fase 96 (`f6fb450`), por
busca de imports, chamadas, wiring de CLI e testes. Um item `UNKNOWN` não é
removido nesta fase.

## Métricas antes

| Medida | Valor |
| --- | ---: |
| Arquivos Python em `src/` | 87 |
| LOC Python em `src/` | 12.845 |
| LOC de `consultation/` | 3.495 |
| Arquivos Python no topo de `evaluation/` | 20 |
| Dependências diretas | 14 |

## Candidatos

| Caminho / símbolo | Categoria | Uso encontrado | Ação proposta |
| --- | --- | --- | --- |
| `consultation/core_evidence.py`, EBCG | ACTIVE_PRODUCTION | CLI, interativa, E2E, testes | Preservar |
| `evidence.py`, `selection.py`, `sufficiency.py`, `service.py` | ACTIVE_PRODUCTION | Pipeline real | Preservar |
| `attribution.py`, `locator.py`, `validator.py`, `polarity.py`, `semantic.py` | ACTIVE_PRODUCTION | Pipeline real | Preservar |
| `evaluation/target_fidelity.py`, auditores 96 | ACTIVE_EVALUATION | Harness E2E e auditorias offline | Preservar |
| `consultation/llm.py::OllamaLegalGenerator` e geração scoped | HISTORICAL_EXPERIMENT | Apenas scripts/testes experimentais; nenhum wiring MVP1 | Remover do runtime junto com experimentos dependentes |
| `consultation/atomic.py` | HISTORICAL_EXPERIMENT | Apenas `test_atomic_acceptance.py` | Remover código e teste histórico |
| `consultation/evidence_bound.py`, `completeness.py`, `qualifiers.py`, `support_slots.py` | HISTORICAL_EXPERIMENT | Apenas experimentos Fase 12/VCSA e testes | Remover código e testes históricos |
| `consultation/structured_evidence.py` | HISTORICAL_EXPERIMENT | Apenas experimento Fase 10 e teste | Remover código e teste histórico |
| `consultation/vcsa.py`, `materialization.py` | HISTORICAL_EXPERIMENT | Apenas testes; sem consumidor no runtime | Remover código e testes históricos |
| Runners `evaluation/*` de VCSA/SEU/Evidence-Bound e diagnóstico de geração livre | HISTORICAL_EXPERIMENT | Não chamados por CLI/runtime atual; alguns dependem dos módulos candidatos | Remover os runners acoplados ao código removido; preservar documentos, datasets e resultados científicos |
| `tests/test_composite_support.py` | ACTIVE_SHARED | Protege attribution/selection e contratos reutilizados | Preservar |
| `lxml` em `pyproject.toml` | DEPENDENCY_CANDIDATE | Nenhum import atual; parser usa `BeautifulSoup(..., "html.parser")` | Remover e atualizar lock |
| `.tmp_validate_interactive.py` | TEMPORARY | Sem chamada atual; docs apenas registram uso histórico | Remover; documentação histórica permanece factual |
| `consultor_juridico_erd.png` na raiz | DEAD_CODE | Hash distinto, menor resolução, sem referência; versão em `docs/` é referenciada pelo README | Remover apenas a cópia da raiz |
| `docs/consultor_juridico_erd.png` | DOCUMENTATION_ONLY | Referenciada pelo README, maior resolução | Preservar |

## Itens deliberadamente preservados

- `onnxruntime`, `transformers` e `torch`: usados por
  `evaluation/relevance_model_benchmark_90.py`; não são removidos por ausência
  de import no runtime de consulta.
- `psycopg`: necessário pelo dialeto `postgresql+psycopg`.
- Documentos, datasets e resultados experimentais em `evaluation/results/`:
  preservados para memória científica. Runners acoplados exclusivamente a módulos
  removidos podem sair, sem apagar seus artefatos de resultado.
- Normalizações textuais duplicadas: dívida técnica registrada, sem
  centralização nesta fase para não modificar comportamento.

## PRODUCTION_RUNTIME_IMPORT_GRAPH_SUMMARY

```text
CLI / interactive
  -> retrieval
  -> Evidence Selection
  -> Sufficiency
  -> EvidenceSet / EvidenceItems
  -> EBCG_V2 (core_evidence + EvidenceBoundControlledGenerator)
  -> Attribution
  -> Locator Fidelity
  -> Citation Validation
  -> Polarity
  -> Semantic Judge
  -> resposta ou abstention
```

```text
FREE_FORM_GENERATOR_IN_RUNTIME = NO
EXPERIMENTAL_GENERATION_IN_RUNTIME = NO
EBCG_V2 = ACTIVE
SEMANTIC_JUDGE = ACTIVE
```
