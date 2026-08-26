# Fase 97 — Resultado da limpeza arquitetural

## Escopo e garantia funcional

Esta fase removeu somente código cujo inventário prévio comprovou não integrar
o caminho MVP1 atual. Não houve mudança de algoritmo, ranking, prompt,
threshold, schema, migration, corpus ou dado jurídico. Não houve chamada a
Ollama, embedding real ou E2E.

O caminho preservado é:

```text
CLI / interactive
  -> Retrieval
  -> Evidence Selection
  -> Sufficiency
  -> EvidenceSet / EvidenceItems
  -> EBCG_V2
  -> Attribution
  -> Locator Fidelity
  -> Citation Validation
  -> Polarity
  -> Semantic Judge fail-closed
  -> resposta ou abstention
```

## Validação

- Testes focais do pipeline preservado: `80 passed`.
- Harness científico 91 preservado após internalizar seu schema histórico:
  `9 passed`.
- Suíte completa: `356 passed, 5 skipped`.
- `ruff format --check .`, `ruff check .` e `git diff --check`: aprovados.
- `uv sync --frozen --offline`: aprovado; removeu `lxml` do ambiente isolado.
- Importabilidade: `uv run consultor-juridico --help` e a mesma verificação em
  imagem Docker reconstruída foram aprovadas sem acionar LLM.

## Removido

- A geração jurídica livre (`OllamaLegalGenerator`, contrato, schemas, parser
  de resposta e geração scoped). O arquivo `consultation/llm.py` foi reduzido
  ao contrato e ao construtor determinístico `EvidenceBoundControlledGenerator`.
- Módulos experimentais rejeitados e sem consumidor ativo: `atomic`,
  `evidence_bound`, `completeness`, `qualifiers`, `structured_evidence`,
  `support_slots`, `materialization` e `vcsa` de `consultation/`.
- O parâmetro experimental `support_slots` do Citation Validator, seu tipo
  `ScopedGeneration` e reexports/imports associados.
- Seis testes exclusivos desses módulos e os testes exclusivos da geração
  livre no antigo `test_consultation.py`.
- Sete runners de avaliação acoplados aos módulos removidos. Documentos,
  datasets e resultados em `evaluation/results/` não foram apagados.
- A dependência direta `lxml`; o parser ativo continua explicitamente em
  `BeautifulSoup(..., "html.parser")`.
- O driver temporário `.tmp_validate_interactive.py` e o PNG ERD órfão na raiz.
  A cópia referenciada em `docs/consultor_juridico_erd.png` foi preservada.

## Preservado deliberadamente

- EBCG-v2, sua policy de Core Evidence e Target Fidelity da Fase 96.
- Retrieval, Selection, Sufficiency, Attribution, Locator Fidelity, Citation
  Validation, Polarity e Semantic Support Validator.
- Infraestrutura Ollama ainda usada pelo Semantic Judge e embeddings.
- `test_composite_support.py`, que protege contratos reutilizados no pipeline.
- `psycopg`, `onnxruntime`, `transformers` e `torch`: possuem uso ativo por
  configuração de banco ou avaliações ainda preservadas.
- Documentação, ADRs, datasets e resultados históricos, inclusive os de
  experimentos rejeitados.

## Métricas antes e depois

| Medida | Antes | Depois | Variação |
| --- | ---: | ---: | ---: |
| Arquivos Python em `src/` | 87 | 79 | -8 |
| LOC Python em `src/` | 12.845 | 11.518 | -1.327 |
| LOC em `consultation/` | 3.495 | 2.168 | -1.327 |
| Arquivos Python no topo de `evaluation/` | 20 | 13 | -7 |
| Dependências diretas | 14 | 13 | -1 |
| Arquivos históricos movidos | 0 | 0 | 0 |
| Módulos de produção removidos | 0 | 8 | +8 |
| Testes exclusivos removidos | 0 | 6 arquivos | +6 |

Os testes removidos cobriam exclusivamente módulos removidos, não a cadeia
MVP1 atual. A cobertura do pipeline preservado é confirmada pelos testes
focais e pela suíte completa desta fase.

## Lock e dependências

`lxml` não possui import em `src/`, `tests/` ou `evaluation/`; a estratégia de
DOM aprovada é `html.parser`. A remoção foi aplicada em `pyproject.toml` e
`uv.lock` foi regenerado exclusivamente por `uv lock --offline`.

## Riscos e itens não limpos

- Runners históricos restantes não foram reorganizados em massa: fazê-lo agora
  geraria churn e risco para referências documentais. A reorganização profunda
  permanece dívida explícita.
- Normalizações textuais semelhantes continuam locais; centralizá-las pode
  mudar o comportamento de retrieval/validação e foi adiado.
- `qualifier preservation` ainda não foi medido.
- O E2E manual EBCG-v2 continua pendente. Esta fase não substitui essa medição.
- O Hit@10 atualmente documentado como `0,900` continua abaixo do gate
  histórico `0,905`; retrieval não foi alterado.

## Confirmações

- Nenhuma mudança funcional planejada foi introduzida.
- Nenhuma migration ou dado de banco foi alterado.
- Nenhum artefato bruto, dataset ou resultado de avaliação foi sobrescrito.
- Nenhuma inferência LLM, benchmark ou E2E foi executado.
