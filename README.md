# Consultor Jurídico

Sistema CLI-first de consulta jurídica fundamentada em fontes oficiais,
versionadas e rastreáveis. O MVP1 cobre exclusivamente a Constituição Federal
de 1988 (CF/88) e o Ato das Disposições Constitucionais Transitórias (ADCT).

> O sistema não substitui análise profissional. Quando a cadeia de evidência
> não é suficiente, ele responde por abstenção, e não por inferência jurídica.

## Objetivo

Oferecer consulta jurídica auditável sobre legislação oficial: o corpus é
versionado, o retrieval produz evidências autorizadas e toda resposta mantém
citações verificáveis até a fonte primária. O LLM local não é fonte jurídica.

## Escopo do MVP1

- aquisição da fonte oficial do Planalto, preservando os bytes recebidos;
- parsing determinístico, versionamento e proveniência do corpus;
- busca lexical PostgreSQL FTS, vetorial pgvector e híbrida;
- EvidenceSet, citações e validações determinísticas;
- geração controlada por evidência (`EBCG_V2`), sem geração jurídica livre;
- juiz semântico local e conservador;
- interface de linha de comando, inclusive modo interativo.

Não fazem parte do MVP1: API HTTP, frontend, jurisprudência, doutrina,
legislação infraconstitucional ou LLM como fonte de verdade.

## Arquitetura

```text
Planalto
  -> ingestão HTTP + raw_bytes + SHA-256
  -> parsing/versionamento
  -> LegalProvision + LegalElement
  -> chunks + FTS + embeddings
  -> retrieval híbrido + Evidence Selection
  -> EBCG_V2 + validators + juiz semântico
  -> resposta fundamentada ou abstenção
```

`EBCG_V2` determina a Core Claim a partir do texto factual da evidência já
autorizada. Não há modelo redigindo livremente proposições jurídicas. O juiz
semântico apenas veta de forma conservadora; ele não promove uma resposta a
suportada.

### Rastreabilidade

```text
Claim -> Citation -> EvidenceItem -> Chunk -> LegalElement
      -> LegalProvision -> LegalVersion -> SourceDocument -> Source
```

Os bytes brutos nunca são canonicalizados ou sobrescritos. Cada captura possui
SHA-256, metadados HTTP e proveniência até a URL oficial.

## Stack

- Python 3.13, `uv`, Typer, Rich e Pydantic;
- PostgreSQL 16 + pgvector, SQLAlchemy e Alembic;
- httpx para aquisição; Beautiful Soup para parsing determinístico;
- Ollama local: `nomic-embed-text` para embeddings e `ministral-3:8b` como
  juiz semântico;
- Docker Compose para PostgreSQL, Ollama e aplicação.

## Requisitos

- Docker e Docker Compose;
- `uv`;
- Ollama acessível no modo de execução escolhido.

As dependências Python são instaladas exclusivamente na `.venv` local do
projeto.

## Instalação e corpus

```bash
uv sync --frozen
cp .env.example .env
docker compose up -d --build
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull ministral-3:8b
docker compose run --rm app db migrate
```

O Compose apenas configura os nomes dos modelos; o pull é uma etapa explícita.
Depois de preparados banco e modelos, execute:

```bash
docker compose run --rm app ingest constitution
docker compose run --rm app parse constitution
docker compose run --rm app index build
```

Esses comandos são idempotentes. A ingestão usa Conditional GET quando a fonte
oferece validators HTTP; CF/88 e ADCT pertencem à mesma captura física.

## Configuração

O arquivo [`.env.example`](.env.example) documenta os defaults. Os valores
relevantes para o runtime do MVP1 são:

```dotenv
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=ministral-3:8b
SEMANTIC_JUDGE_MODEL=ministral-3:8b
EMBEDDING_MODEL=nomic-embed-text
```

`OLLAMA_MODEL` é o fallback de compatibilidade do runtime; no pipeline de
consulta atual não existe Generator LLM livre. `SEMANTIC_JUDGE_MODEL` é o veto
semântico local, depois de citation, locator fidelity e polarity validation.

## CLI

Consulte os comandos instalados em vez de depender desta lista:

```bash
consultor-juridico --help
consultor-juridico db --help
consultor-juridico ingest --help
consultor-juridico parse --help
consultor-juridico index --help
consultor-juridico retrieval --help
consultor-juridico eval --help
```

Exemplos usuais:

```bash
consultor-juridico db status
consultor-juridico ingest status
consultor-juridico parse status
consultor-juridico retrieval search "direitos fundamentais" --mode hybrid
consultor-juridico consult "Qual é a regra constitucional sobre voto obrigatório?"
consultor-juridico
```

O último comando inicia o menu interativo em terminal TTY. O modo normal evita
mostrar SQL, vetores e payloads extensos.

## Qualidade e freeze do MVP1

O dataset de produto é `real_world_short_v2`: dez casos respondíveis e uma
abstenção esperada. A reavaliação **offline** do último artefato E2E obteve:

- 8/10 respostas respondíveis corretas (80% strict accuracy);
- 1/1 abstenção esperada correta;
- 0 respostas inseguras.

A seleção de Core Evidence atingiu o target em 7/10 casos no E2E original,
antes da correção de contrato do benchmark. A métrica permanece preservada
como referência histórica e não deve ser confundida com o reassessment v2.

Isso não é um E2E nativo final contra v2: essa inferência ainda não foi
executada. O retrieval do benchmark congelado permaneceu em `Hit@10 = 0.900`,
abaixo do threshold histórico de `0.905`; portanto esse gate está em **FAIL** e
é uma limitação assumida, não uma métrica mascarada.

O E2E nativo final deve escolher a versão congelada de forma explícita e nunca
sobrescreve um artefato existente:

```bash
OLLAMA_BASE_URL=http://localhost:11435 \
uv run python -m evaluation.e2e_single_model_91 \
  --dataset-version v2 \
  --output evaluation/results/mvp1_final_v2/e2e.json
```

O comando acima executa inferência e deve ser rodado manualmente após revisão.
O harness também preserva `--dataset-version v1` para reproduzir o histórico da
Fase 96; cada versão verifica seu SHA-256 antes de criar providers ou chamar
Ollama.

Também permanecem: `QUALIFIER_PRESERVATION=NOT_YET_MEASURED` e
`FORMAL_STABILITY=NOT_RUN`.

## Limitações conhecidas

- **Prisão perpétua:** a Core Evidence correta pode depender de informação
  negativa no elemento estrutural pai; o MVP1 pode abstê-la conservadoramente.
- **Estado de sítio:** os arts. 137/138 não alcançaram o top-10 no benchmark
  atual de retrieval.
- O corpus do MVP1 continua restrito à CF/88 e ao ADCT.

## Desenvolvimento

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
git diff --check
```

Há testes de integração opt-in para Planalto, parsing, retrieval e consulta;
eles exigem a infraestrutura e/ou modelos locais correspondentes. Consulte
[docs/README.md](docs/README.md) para a documentação por tema e
[docs/mvp1-freeze.md](docs/mvp1-freeze.md) para o estado congelado.

## Roadmap pós-MVP1

- contexto parent/ancestor para validators;
- recuperação de estado de sítio;
- medição de preservação de qualificadores e estabilidade formal;
- benchmark e corpus mais amplos;
- legislação infraconstitucional; API ou frontend somente após nova decisão de
  escopo.
