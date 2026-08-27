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

## Desenvolvimento v0.2

A versão v0.1.0 permanece congelada e preserva o MVP1 histórico descrito neste
README. A branch `mvp-v0.2` inicia uma reestruturação arquitetural; ela ainda
não representa um novo pipeline funcional de consulta.

O objetivo central da v0.2 é corrigir localização e relevância da evidência
antes da geração. A fundação usa Clean Architecture e SOLID: o domínio é
independente de frameworks, capacidades externas são ports injetáveis e o
LangGraph coordena apenas estado, rotas, retries e clarificações.

O workflow distinguirá um **Evidence Relevance Judge**, responsável pela
relação pergunta-evidência, de um **Answer Judge**, responsável pela relação
pergunta-resposta-evidência. Evidência ambígua poderá suspender o fluxo para
pedir esclarecimento ao usuário. Não haverá fine-tuning; as próximas etapas
implementarão primeiro corpus contextual e retrieval, antes da geração.

Documentação ativa: [arquitetura](docs/v0.2/architecture.md),
[aprendizados da v0.1](docs/v0.2/lessons-from-v0.1.md) e
[plano de implementação](docs/v0.2/implementation-plan.md).

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
      -> LegalProvision -> LegalVersion -> LegalAct
      -> SourceDocument -> Source
```

Cada entidade cumpre um papel específico nessa cadeia:

- **Claim:** afirmação jurídica apresentada pela consulta.
- **Citation:** vínculo entre uma Claim e a evidência que a fundamenta.
- **EvidenceItem:** snapshot imutável da evidência efetivamente utilizada na
  consulta.
- **Chunk:** unidade textual indexada e recuperada pelo mecanismo de retrieval.
- **LegalElement:** ocorrência concreta de um elemento normativo em uma versão
  específica, como artigo, parágrafo, inciso, alínea ou item.
- **LegalProvision:** identidade normativa estável da disposição jurídica,
  independente de sua ocorrência em uma versão específica.
- **LegalVersion:** versão materializada de um `LegalAct` em determinado estado
  temporal, representando o conteúdo normativo válido daquela versão.
- **LegalAct:** identidade do ato normativo ao qual a versão pertence, como a
  Constituição Federal de 1988 ou o ADCT.
- **SourceDocument:** captura física do documento oficial ingerido, com
  proveniência e hash do conteúdo.
- **Source:** origem oficial do documento, como a fonte primária do Planalto.

Essa cadeia permite rastrear uma afirmação da resposta até o documento oficial
original, preservando a evidência utilizada, a versão normativa e a proveniência
da captura. O diagrama representa a cadeia lógica de rastreabilidade até a fonte
oficial, e não necessariamente uma sequência de relacionamentos 1:1 entre
tabelas.

Os bytes brutos nunca são canonicalizados ou sobrescritos. Cada captura possui
SHA-256, metadados HTTP e proveniência até a URL oficial.

## EBCG_V2

EBCG significa **Evidence-Bound Controlled Generation**. `EBCG_V2` é a segunda
versão da arquitetura de geração controlada e vinculada à evidência usada pelo
MVP1. O sistema não utiliza um LLM como gerador jurídico livre.

O fluxo conceitual é:

```text
Pergunta
  -> Retrieval
  -> EvidenceItems
  -> seleção da Core Evidence
  -> Claim vinculada à evidência
  -> validators
  -> resposta ou abstention
```

A Core Evidence é determinada pela política ativa
`QUERY_COVERAGE_MARGINAL_COVERAGE_BASE_RELEVANCE_SELECTED_POSITION`, que define
qual evidência será usada como núcleo da resposta. Depois da seleção, são
aplicadas validações de Attribution, Target Fidelity, Polarity, Locator,
Semantic Support e Citation Validation.

O Semantic Judge utiliza `ministral-3:8b` como componente fail-closed de
validação, e não como gerador jurídico livre. Quando as evidências ou as
validações são insuficientes, o sistema prefere abstention a produzir uma
proposição jurídica não sustentada.

## Stack

- Python 3.13, `uv`, Typer, Rich e Pydantic;
- PostgreSQL 16 + pgvector, SQLAlchemy e Alembic;
- httpx para aquisição; Beautiful Soup para parsing determinístico;
- Ollama local: `nomic-embed-text` para embeddings e `ministral-3:8b` como
  juiz semântico;
- Docker Compose para PostgreSQL, Ollama e aplicação.

## Requisitos

- Docker e Docker Compose;
- acesso à internet no primeiro bootstrap para a fonte oficial e os modelos.

O ambiente Python e o Ollama são preparados dentro dos containers. No
desenvolvimento pelo host, as dependências Python continuam isoladas na
`.venv` local do projeto.

## Início rápido

```bash
git clone <repo>
cd consultor_juridico
cp .env.example .env
docker compose up -d --build
docker compose run --rm app bash
```

Dentro do container, execute somente:

```bash
consultor-juridico
```

Para sair, use `exit`.

Na primeira inicialização, o sistema prepara automaticamente os modelos locais,
aplica migrations, captura a CF/88 e o ADCT da fonte oficial, materializa o
corpus e cria chunks e embeddings. Essa preparação pode demorar, sobretudo no
download inicial de `ministral-3:8b`. Em acessos seguintes, o bootstrap consulta
o estado persistido no PostgreSQL e pula as etapas já concluídas.

Os modelos `nomic-embed-text` e `ministral-3:8b` são provisionados pelo serviço
Ollama e armazenados em volume persistente. Não é necessário executar
`ollama pull` manualmente.

Observabilidade opcional:

```bash
docker compose ps
docker compose logs -f ollama
```

Checklist do primeiro acesso: containers saudáveis, modelos preparados,
bootstrap concluído e `consultor-juridico` iniciado.

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

## Operações avançadas

O bootstrap e os comandos internos permanecem disponíveis para manutenção e
diagnóstico, mas não fazem parte do início rápido:

```bash
consultor-juridico --help
consultor-juridico bootstrap
consultor-juridico db --help
consultor-juridico ingest --help
consultor-juridico ingest constituicao --help
consultor-juridico parse --help
consultor-juridico parse constituicao --help
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

## Estado da avaliação do MVP1

O benchmark de produto é `real_world_short_v2`: dez casos respondíveis e uma
abstenção esperada. O E2E nativo final foi executado contra esse dataset e
reproduziu exatamente o reassessment offline anterior:

- 8/10 respostas respondíveis corretas (80% de acurácia estrita);
- 1/1 abstenção esperada correta;
- 1 falsa abstenção;
- 1 resposta com alvo jurídico incorreto;
- 0 respostas inseguras.

O artefato final é
`evaluation/results/mvp1_v0_1_0_final_e2e/e2e_real_world_short_v2.json`
(`SHA-256 3175c5e3d5cda4f3baf7220a42ce9b47073250c31a6e6af7035765c65a84202d`).
O dataset v2 permanece identificado por
`a6ef0c9e0f3a95a44637c80d061c854a9848aaea5aad1443e7f9f0ee9b710a89`.

A cronologia científica preservada é: E2E histórico v1 com 6/10, reassessment
offline v2 com 8/10 e E2E nativo final v2 com 8/10. O retrieval do benchmark
congelado permaneceu em `Hit@10 = 0.900`, abaixo do threshold histórico de
`0.905`; portanto esse gate está em **FAIL**. O MVP1 0.1.0 foi congelado com
essa limitação conscientemente aceita, sem redefinir o threshold.

**MVP1_READY=YES:** o produto está pronto para o fechamento da versão 0.1.0,
sem declarar que todos os gates históricos de qualidade foram aprovados.

Também permanecem `QUALIFIER_PRESERVATION=NOT_YET_MEASURED` e
`FORMAL_STABILITY=NOT_RUN`.

## Limitações conhecidas

- **Prisão perpétua:** a Core Evidence foi correta, mas o Polarity Guard
  abortou conservadoramente porque o snapshot `de caráter perpétuo;` não traz
  isoladamente a negação do contexto estrutural pai. Classificação:
  `FALSE_ABSTENTION`; estágio: `POLARITY_VALIDATION`.
- **Estado de sítio:** os arts. 137/138 não alcançaram o top-10 do benchmark;
  foi usada evidência do art. 21, V. Target Fidelity classificou o resultado
  como `WRONG_TARGET`; estágio: `TARGET_FIDELITY`.
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
