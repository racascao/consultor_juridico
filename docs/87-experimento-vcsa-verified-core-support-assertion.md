# Experimento offline VCSA

## Escopo

VCSA foi avaliada somente em memória. Não houve Generator, Semantic Judge, retrieval, seleção, ingestão, migration ou integração em produção.

Ela recompõe texto normativo literal e mínimo a partir de fragments autorizados de um `SupportSlot`; não é `GeneratedClaim`.

## Ambiente local

A `.venv` anterior pertencia a `nobody`, apontava para interpretador ausente e não permitia reparo pelo `uv`. Foi preservada como `.venv.invalid-pre-vcsa`.

`uv sync --frozen` recriou a `.venv` usando apenas `pyproject.toml` e `uv.lock`. Nenhum arquivo de dependências foi alterado.

`uv run python --version`, `uv run pytest --version` e `uv run ruff --version` foram validados pela nova `.venv`.

## Regra estrutural

`parent.rstrip() + " " + child.lstrip()`

O parent precisa ser direto, terminar em `:`, e os dois elementos precisam ser do mesmo ato/versão, `NORMATIVE` e `CURRENT`, sem `NOTE`, histórico, revogado ou editorial.

Relações permitidas: `CAPUT → INCISO`, `PARAGRAPH → INCISO`, `INCISO → ALINEA` e `ALINEA → ITEM`.

O prefixo técnico do snapshot é removido somente quando sua segunda linha coincide exatamente com `LegalElement.normalized_text`; o texto jurídico não é modificado.

## Resultado

Os controles estruturais cobriram relação válida, parent sem `:`, sibling pollution, ancestor não direto, child independente, annotation/editorial, histórico, revogado, qualifier, pontuação, provenance, hash, slot externo e estado de sítio. Todos passaram; não houve composição entre siblings, ancestors distantes ou EvidenceItems distintos.

Pena de morte produziu assertion `VERIFIED`, `RELEVANT` e `CENTRAL`: `não haverá penas: de morte, salvo em caso de guerra declarada, nos termos do art. 84, XIX;`.

Prisão perpétua também foi `VERIFIED`: `não haverá penas: de caráter perpétuo;`.

Porém, o boundary de relevance retornou `IRRELEVANT`: ele não introduz equivalência entre “prisão perpétua” e “penas de caráter perpétuo”. Não houve sinônimo, hardcode ou nova heurística. Trata-se de `RELEVANCE_LIMIT`.

Estado de sítio não atende à forma permitida e permaneceu em `SAFE_ABSTENTION`.

| Medida | Resultado |
|---|---:|
| Pena de morte recovered | Sim |
| Prisão perpétua structural verified | Sim |
| Prisão perpétua recovered | Não — relevance limit |
| Estado de sítio | Safe abstention |
| Regressões históricas | 0 |
| Unsafe product answers | 0 |
| Potencial offline | 8/10 |

`VCSA_DIRECTION: NOT_JUSTIFIED` como rota isolada para 9/10. VCSA é uma fundação estrutural validada, mas não deve ser integrada em produção.

O artefato reproduzível está em `evaluation/results/vcsa_87.json`.
