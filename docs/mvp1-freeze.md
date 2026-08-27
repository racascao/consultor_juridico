# Freeze do MVP1 — 0.1.0

## Escopo e corpus

O MVP1 consulta exclusivamente a Constituição Federal de 1988 e o ADCT,
capturados da fonte oficial do Planalto. A captura preserva `raw_bytes`,
SHA-256 e metadados HTTP; parsing, versões, provisões e elementos são dados
derivados rastreáveis.

## Pipeline ativo

```text
SourceDocument -> parsing/versionamento -> LegalProvision/LegalElement
-> Chunk -> retrieval híbrido -> EvidenceSet -> EBCG_V2
-> Citation/Locator/Polarity validation -> Semantic Judge -> resposta/abstenção
```

O `EBCG_V2` não usa geração jurídica livre. Ele produz uma Core Claim factual
amarrada à evidência autorizada. O juiz semântico local atua somente como veto
conservador após validações determinísticas.

## Configuração congelada

- versão do pacote: `0.1.0`;
- embedding: `nomic-embed-text`;
- Semantic Judge: `ministral-3:8b`;
- Generator LLM livre: `NO`;
- modelos devem ser preparados explicitamente no Ollama; o Compose não executa
  pull automático.

### Auditoria de referências a modelos

| Classe | Local | Estado |
|---|---|---|
| `ACTIVE_RUNTIME` | `config.py`, CLI e consultation service | usam `ministral-3:8b` via Settings; EBCG_V2 não chama Generator livre |
| `ACTIVE_CONFIG` | `.env.example` | juiz e fallback em `ministral-3:8b` |
| `ACTIVE_INFRA` | `docker-compose.yml` | juiz e fallback em `ministral-3:8b` |
| `ACTIVE_EVALUATION` | harnesses de benchmark | podem listar candidatos históricos, sem alterar runtime |
| `HISTORICAL_DOC` / `HISTORICAL_ARTIFACT` | fases e resultados anteriores | preservam Granite e outros modelos como evidência científica |
| `TEST_FIXTURE` | testes de independência/readiness | usa nomes de modelos falsos para testar configuração, sem configurar produção |

`CONSULTATION_MAX_TOKENS` foi removido da configuração versionada: não tinha
consumidor no EBCG_V2 nem no runtime atual. As demais variáveis de consulta são
consumidas por CLI, avaliação ou seleção e foram preservadas. O `.gitignore`
continua protegendo `.env`, `.venv`, caches e artefatos locais; `uv.lock` segue
versionado para reprodução.

## Medição e qualidade

O dataset atual é `real_world_short_v2`, com dez casos respondíveis e uma
abstenção esperada. O reassessment **offline** do último artefato E2E aponta
8/10 respostas respondíveis corretas, 1/1 abstenção correta e zero respostas
inseguras. Não é uma medição E2E nativa final contra v2.

O E2E nativo final deve declarar o dataset explicitamente:

```bash
OLLAMA_BASE_URL=http://localhost:11435 \
uv run python -m evaluation.e2e_single_model_91 \
  --dataset-version v2 \
  --output evaluation/results/mvp1_final_v2/e2e.json
```

O harness aceita apenas `v1` e `v2`, valida o SHA-256 antes de qualquer
provider/inferência e não sobrescreve outputs. `v1` continua reproduzindo o
artefato histórico da Fase 96; `v2` registra `MVP1_FINAL_NATIVE_V2` para não
ser confundido com ele.

| Indicador | Estado |
|---|---|
| Reassessment offline v2 | 8/10 respondíveis; 1/1 abstention; unsafe 0 |
| Retrieval Hit@10 | 0.900 |
| Threshold histórico Hit@10 | 0.905 |
| Retrieval gate | FAIL |
| Qualifier preservation | NOT_YET_MEASURED |
| Formal stability | NOT_RUN |

## Limitações aceitas

- **Prisão perpétua:** há dependência de contexto negativo do elemento pai; a
  abstenção conservadora pode ocorrer.
- **Estado de sítio:** arts. 137/138 não chegaram ao top-10 no benchmark atual.
- O E2E nativo final do dataset v2 ainda não foi realizado.

## Experimentos fora da produção

Atomic Claim Acceptance, VCSA, Structural Expansion, Structural Reserve e
Evidence Selection experimental permanecem congelados e não integrados. O
runtime não ativa esses componentes.

## Próximos passos pós-MVP1

1. medir E2E nativo v2, estabilidade e preservação de qualificadores;
2. tratar contexto estrutural e estado de sítio por mudanças gerais e auditáveis;
3. somente depois ampliar corpus, escopo normativo ou interface.
