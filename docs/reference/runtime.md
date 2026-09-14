# Runtime

## Componentes

| Componente | Papel |
|---|---|
| PostgreSQL 16 | corpus, hierarquia e FTS |
| Ollama | `gemma4:12b` local |
| `app` | bootstrap one-shot e CLI |

O Compose publica PostgreSQL em `5434:5432` e Ollama em `11435:11434`. Entre
containers, o endereço canônico é `http://ollama:11434`. A GPU está habilitada
porque o modelo de 12B não foi operacionalmente adequado em CPU neste ambiente.

## Readiness e bootstrap

O bootstrap verifica migrations, identidade e auditoria do corpus, SearchUnits
e digest do modelo. Opera idempotentemente e encerra o container `app` com
código zero quando tudo está pronto. O web fetch existe somente para preparar
um corpus ausente.

## Answerer congelado

O runtime usa `gold-evidence-selected-answerer/1`: `format=json`, thinking
desabilitado, `stream=false`, `num_predict=1024`, `num_ctx=8192` e timeout de
180 s. O spinner da CLI é feedback de UX, não streaming do modelo.

Veja os parâmetros completos em [Seleção do modelo](model-selection.md).
