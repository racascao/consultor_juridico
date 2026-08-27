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
- generation mode: `EBCG_V2`;
- Core Evidence policy:
  `QUERY_COVERAGE_MARGINAL_COVERAGE_BASE_RELEVANCE_SELECTED_POSITION`;
- relevance: `DETERMINISTIC`;
- embedding: `nomic-embed-text`;
- Semantic Judge: `ministral-3:8b`;
- Generator LLM livre: `NO`;
- corpus: CF/88 + ADCT;
- interface: CLI;
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
abstenção esperada. O E2E nativo final foi executado com
`evaluation_context=MVP1_FINAL_NATIVE_V2` e reproduziu o reassessment offline
v2: 8/10 respostas respondíveis corretas (80%), 1/1 abstenção correta, uma
falsa abstenção, um alvo incorreto e zero respostas inseguras.

Artefato final:
`evaluation/results/mvp1_v0_1_0_final_e2e/e2e_real_world_short_v2.json`

SHA-256 do artefato:
`3175c5e3d5cda4f3baf7220a42ce9b47073250c31a6e6af7035765c65a84202d`

SHA-256 do dataset
`evaluation/datasets/real_world_short_v2.json`:
`a6ef0c9e0f3a95a44637c80d061c854a9848aaea5aad1443e7f9f0ee9b710a89`

O harness aceita apenas `v1` e `v2`, valida o SHA-256 antes de qualquer
provider/inferência e não sobrescreve outputs. `v1` continua reproduzindo o
artefato histórico da Fase 96; `v2` identifica esta execução como
`MVP1_FINAL_NATIVE_V2`.

| Indicador | Estado |
|---|---|
| E2E histórico v1 | 6/10 respondíveis |
| Reassessment offline v2 | 8/10 respondíveis; 1/1 abstention; unsafe 0 |
| E2E nativo final v2 | 8/10 respondíveis (80%); 1/1 abstention; false abstention 1; wrong target 1; unsafe 0 |
| Retrieval Hit@10 | 0.900 |
| Threshold histórico Hit@10 | 0.905 |
| Retrieval gate | FAIL |
| Qualifier preservation | NOT_YET_MEASURED |
| Formal stability | NOT_RUN |

## Gates não cumpridos / não medidos

O `Hit@10` do retrieval é `0.900`, abaixo do threshold histórico de `0.905`;
seu status continua **FAIL**. `QUALIFIER_PRESERVATION=NOT_YET_MEASURED` e
`STABILITY=NOT_RUN`. Esses fatos não foram transformados em sucesso técnico:
são limitações conscientemente aceitas no escopo do MVP1 0.1.0.

## Limitações aceitas

- **Prisão perpétua:** a Core Evidence target foi correta, mas o Polarity Guard
  produziu `FALSE_ABSTENTION` em `POLARITY_VALIDATION` porque o snapshot não
  traz isoladamente a negação do elemento estrutural pai.
- **Estado de sítio:** arts. 137/138 não chegaram ao top-10; a evidência usada
  foi o art. 21, V, resultando em `WRONG_TARGET` em `TARGET_FIDELITY`.

## Experimentos fora da produção

Atomic Claim Acceptance, VCSA, Structural Expansion, Structural Reserve e
Evidence Selection experimental permanecem congelados e não integrados. O
runtime não ativa esses componentes.

## Próximos passos pós-MVP1

1. medir estabilidade e preservação de qualificadores;
2. tratar contexto estrutural e estado de sítio por mudanças gerais e auditáveis;
3. somente depois ampliar corpus, escopo normativo ou interface.
