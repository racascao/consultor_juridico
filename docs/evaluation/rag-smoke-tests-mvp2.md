# Smoke tests manuais do RAG MVP2

## Estado

Os comandos abaixo estão preparados para reteste, mas **não foram executados
pelo Codex**.
Eles usam exclusivamente a `ActVersion` local materializada da Lei nº
9.784/1999:

```text
version_hash=bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6
source_sha256=b4abab2e47732f76a16a99e8b00311dcb420b378f89e99c096b609ae84529261
```

Execute cada comando manualmente a partir do host. Todos acessam o Ollama do
Docker Compose pela rede interna do serviço `app`.

## 1. Suporte direto

```bash
docker compose --profile llm run --rm app consultor-juridico ask \
  "Quais são os requisitos para delegação de competência?" \
  --version-hash bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6
```

## 2. Suporte composto

```bash
docker compose --profile llm run --rm app consultor-juridico ask \
  "Quais atos não podem ser delegados e em que condições a avocação é permitida?" \
  --version-hash bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6
```

## 3. Evidência insuficiente

```bash
docker compose --profile llm run --rm app consultor-juridico ask \
  "Qual é a pena para o crime de furto?" \
  --version-hash bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6
```

## Resultado histórico dos primeiros smokes

```text
SMOKE_1: PASS_AFTER_TRANSIENT_REQUEST_FAILURE
SMOKE_2: FAIL_RETRIEVAL_EVIDENCE_COVERAGE
SMOKE_3: PASS
SMOKE_4_ORIGINAL: INVALID_TEST_DESIGN_FOR_CLARIFY
SMOKE_5: PASS
```

O smoke 4 original não é um gate válido de `CLARIFY`: ao afirmar que o recurso
foi interposto fora do prazo, a pergunta já fornece o fato decisivo. Ele foi
substituído por uma pergunta cuja validade depende de fatos ausentes.

A primeira execução manual da pergunta substituta terminou em
`SELECTED_ANSWERER_REQUEST_FAILED: TIMEOUT`. Logo, seu resultado permanece
`INCONCLUSIVE_DUE_TO_TIMEOUT`: não é `PASS` nem falha de clarificação. Desde
então, a GPU NVIDIA foi exposta ao serviço Ollama e o backend CUDA foi
confirmado sem inferência; o timeout continua congelado em 180 segundos. Os
cinco comandos devem agora ser repetidos pelo usuário.

## 4. Necessidade real de clarificação

```bash
docker compose --profile llm run --rm app consultor-juridico ask \
  "A intimação que recebi no processo administrativo é válida?" \
  --version-hash bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6
```

## 5. Rastreabilidade com trace

```bash
docker compose --profile llm run --rm app consultor-juridico ask \
  "Quais são os requisitos para delegação de competência?" \
  --version-hash bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6 \
  --trace
```

## Registro pendente

```text
SMOKE_DIRECT: PASS
SMOKE_COMPOSITE: PASS_AFTER_GENERAL_RETRIEVAL_FIX
SMOKE_INSUFFICIENT: PASS
SMOKE_CLARIFY: MATERIAL_SAFE_BUT_MISSED_CLARIFICATION
SMOKE_TRACE: PASS
```

O resultado de clarificação é compatível com o risco residual `RISK-05`; ele não
foi usado para tuning individual. Os smokes foram considerados suficientes para
o Integrated DEV. O HOLDOUT permanece fechado e não deve ser usado nestes
testes.
