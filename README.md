# Consultor Jurídico

Mecanismo CLI-first de consulta jurídica baseado em fontes oficiais,
versionadas e rastreáveis. O MVP2 está sendo reconstruído com escopo reduzido;
nesta etapa existem um corpus funcional e auditável, um retrieval lexical
selecionado para o piloto, um answerer congelado e o fluxo RAG integrado.
O corpus piloto local está materializado e pronto para smoke tests manuais.

## Estado do projeto

A tag `v0.1.0` preserva o MVP1 e permanece imutável. A branch `mvp-v0.2`, na
versão `0.2.0.dev0`, concluiu a Fase 0 e mediu a Fase 1 com a Lei nº
9.784/1999 como ato piloto.

```text
MVP2_STATUS: INTEGRATED_DEV_GENERAL_FAILURE_ANALYSIS_COMPLETE_NO_FIX_JUSTIFIED
PILOT_LEGAL_ACT: BR-FED-LEI-9784-1999
PARSER: IMPLEMENTED
CORPUS_IMPLEMENTATION: MATERIALIZED_AND_AUDITABLE
CORPUS_PERSISTED_STATE: LOCAL_VERSIONED_CORPUS_READY
RETRIEVAL: POSTGRESQL_FTS_STRICT_RELAXED_OR_AND_COVERAGE
FTS: IMPLEMENTED_AND_MEASURED
EMBEDDINGS: NOT_IMPLEMENTED
GOLD_EVIDENCE: PROMPT_ENGINEERING_FROZEN_V2_FINAL_CANDIDATE
FIRST_MODEL_CANDIDATE: Qwen3-4B-Instruct-2507 Q4_K_M
FIRST_PROVIDER: OLLAMA_EVALUATION_ONLY
OLLAMA_DEPLOYMENT: DOCKER_COMPOSE_ONLY
V1_REAL_MODEL_RUN: COMPLETE
V2_REAL_MODEL_RUN: COMPLETE
V3_REAL_MODEL_RUN: COMPLETE
STABILITY_RUNS: COMPLETE_DECISION_STABLE_12_OF_12
HUMAN_REVIEW: COMPLETE
CROSS_MODEL_CANDIDATES: QWEN3.5_9B_PHI4_MINI_GEMMA3_4B_GEMMA4_12B
CROSS_MODEL_RUNS: QWEN3_5_REJECTED_PHI4_MINI_REJECTED_GEMMA3_REJECTED_GEMMA4_NEXT
LLM_RUNTIME: GEMMA4_12B_FROZEN_RAG_INTEGRATED
```

O checkpoint factual para retomadas está em
[`docs/STATE.md`](docs/STATE.md).

O PostgreSQL v0.2 é isolado do legado:

```text
database: consultor_juridico_v02
volume:   consultor_juridico_v02_pgdata
host:     localhost:5434
```

O banco e o volume do MVP1 não são migrados nem reutilizados. O baseline
Alembic ativo da branch v0.2 cria somente as tabelas da fundação documental;
as migrations históricas continuam preservadas pela tag `v0.1.0`.

Em 3 de setembro de 2026, uma regressão não commitada do Compose foi corrigida
cirurgicamente e o contrato acima foi restaurado. O volume vazio incorreto
`consultor_juridico_pgdata` foi preservado. A aquisição canônica realizada para
reconstruir o novo volume v0.2 retornou 74.941 bytes com SHA-256 `c69120fb...`,
divergente do snapshot histórico congelado `face6f55...`; por isso a
reconstrução fiel do corpus histórico permanece bloqueada. Esse incidente não foi
tratado como substituição de fonte: a identidade raw histórica continua
indisponível e sua equivalência semântica não foi afirmada.

Para habilitar o RAG sem alegar essa identidade histórica, o corpus piloto foi
materializado a partir do artifact local versionado
`docs/corpus/artifacts/lei-9784-1999-planalto-2026-08-31.raw.html`, SHA-256
`b4abab2e47732f76a16a99e8b00311dcb420b378f89e99c096b609ae84529261`.
Ele produziu a `ActVersion`
`bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6`,
com 322 provisions e 242 SearchUnits. A repetição do mesmo fluxo confirmou
idempotência sem duplicar snapshot, versão ou unidades.

## Retrieval lexical da Fase 1

O baseline recebe obrigatoriamente um `version_hash` e pesquisa somente
`SearchUnit.search_text` com a configuração portuguesa do PostgreSQL:
`websearch_to_tsquery`, `to_tsvector`, `ts_rank_cd` e desempate por
`unit_key`. A migration `002_v02_postgresql_fts` adiciona um índice GIN de
expressão, sem alterar a projeção `provision-text/1`.

O DEV congelado contém 40 consultas naturais, cinco em cada uma de oito
categorias. Seu SHA-256 é
`bc47eb6e7364931767fb2305cc9ce5a55ce7763e9f88cb6bbf224609dbe221aa`.
O baseline strict obteve Hit@1/3/5/10 e MRR iguais a `0,000`; um controle
positivo literal passou 3/3, demonstrando que a falha estava na conjunção das
perguntas naturais, não no funcionamento mecânico do FTS. Um único experimento
PostgreSQL-native `RELAXED_OR` elevou Hit@10 para `0,800` e MRR para `0,549`.
Seus oito misses restantes possuem match lexical, mas ficam entre ranks 11 e
59 por diluição do ranking. O experimento posterior
`RELAXED_OR_COVERAGE`, sem mudar os candidatos, elevou Hit@10 para `0,875` e
MRR para `0,661`: três misses entraram no top 10, nenhum foi perdido e uma
posição regrediu de rank 5 para 6. Essa variante foi aceita como retrieval
lexical do piloto e permanece congelada durante a Fase 2.

O relatório e a classificação das 40 falhas estão em
[`docs/retrieval/phase-1-fts-baseline.md`](docs/retrieval/phase-1-fts-baseline.md).
O diagnóstico causal e o experimento de cobertura estão em
[`docs/retrieval/phase-1-relaxed-or-ranking-diagnostic.md`](docs/retrieval/phase-1-relaxed-or-ranking-diagnostic.md)
e
[`docs/retrieval/phase-1-lexical-coverage-ranking.md`](docs/retrieval/phase-1-lexical-coverage-ranking.md).
Não foram usados embeddings, busca vetorial, RRF, reranker, LLM ou RAG.

## Capacidade do modelo com Gold Evidence

A Fase 2 isola a capacidade do futuro modelo local do retrieval. Cada caso
declara diretamente as `Provision.stable_key` autorizadas; o materializador lê
os respectivos `citation_text` da `ActVersion` explicitamente informada e
preserva URL oficial, SHA-256 do snapshot e `source_locator`. `SearchUnit` e os
retrievers não participam desse fluxo.

Materialização e avaliação são responsabilidades distintas. O PostgreSQL é
necessário para produzir inicialmente a Gold Evidence a partir de uma
`ActVersion`, mas o bundle v2 já congela integralmente os prompts e os payloads
de evidência. O `FrozenGoldBundleRepository` permite avaliar respostas já
geradas diretamente desse bundle, sem criar engine, sessão ou conexão com o
banco. A equivalência com o resultado histórico DB-backed do Qwen v2 foi
automatizada e passou em `32/32` casos, ignorando somente o novo timestamp
operacional `evaluated_at`.

O bundle possui 51 `stable_key`, enquanto o corpus histórico possuía 322
disposições. A avaliação offline é, portanto, fail-closed: uma citação
estruturalmente plausível que não esteja no namespace congelado interrompe a
avaliação com `INCOMPLETE_FROZEN_CITATION_NAMESPACE`, em vez de ser classificada
por suposição ou resolvida por fallback ao banco. Citações inequivocamente
malformadas continuam seguindo os checks históricos.

O DEV `lei_9784_gold_evidence_dev_v1` contém 32 casos: 12
`SINGLE_SUPPORT`, 8 `COMPOSITE_SUPPORT`, 6 `INSUFFICIENT_EVIDENCE` e 6
`AMBIGUOUS`. O contrato público do modelo admite somente `ANSWER`, `ABSTAIN` e
`CLARIFY`; suporte composto exige todas as evidências declaradas
(`ALL_REQUIRED`). O prompt histórico `gold-evidence-answering/1` não recebe a
categoria nem a decisão esperada e proíbe conhecimento jurídico externo à
evidência. Seu primeiro run permanece congelado com `AUTOMATIC_PASS=19/32`. A
auditoria identificou três ambiguidades contratuais (`GOLD-021`, `GOLD-023` e
`GOLD-026`): o evaluator exigia justificativa não vazia em `ABSTAIN`, mas essa
regra não estava inequívoca no prompt. Esses casos não são promovidos
retroativamente a PASS.

O `gold-evidence-answering/2` esclarece somente o contrato de output:
`decision`, `answer` e `citations` devem estar sempre presentes, `answer` deve
ser não vazio, `ABSTAIN` deve justificar brevemente a insuficiência e usar
`citations=[]`, e `CLARIFY` deve manter o campo `citations` explícito. Schema,
evaluator, dataset, semântica jurídica e configuração de geração não mudaram.
O run v2 preservado obteve `AUTOMATIC_PASS=25/32`, JSON/schema/payload válidos
em `32/32`, decisão esperada em `29/32`, uma falsa abstenção, dois casos com
citation inválida e nenhuma resposta insegura ou citação fora da evidência.

A auditoria pós-v2 sustentou, por observação em uma única seed, a hipótese de
que o prefixo literal `EVIDENCE_ID: ` poderia ser ambíguo. O
`gold-evidence-answering/3` testou somente a clareza entre esse rótulo e seu
valor. Como v1, v2 e v3 tiveram uma única geração por caso com
`temperature=0.7`, as diferenças entre prompts são evidência exploratória e
geradora de hipótese, não confirmação causal robusta. O run v3 terminou com
`AUTOMATIC_PASS=24/32`, quatro clarificações perdidas, uma falsa abstenção,
um caso de citation inválida, nenhuma resposta insegura e nenhuma citação fora
da evidência.

O prompt engineering está congelado nesta rodada DEV. O v2 é o candidato final
atual pelo melhor perfil decisório observado e pela estabilidade de decisão em
`12/12` casos nas seeds `42`, `43` e `44`. A cobertura de citações obrigatórias
variou em dois casos e o conjunto de citações em três. `GOLD-029` e `GOLD-030`
mantiveram clarificação perdida nas três seeds. `GOLD-012` não pertenceu ao
subset histórico; seu diagnóstico pós-hoc separado retornou `ABSTAIN` nas três
seeds. Isso confirma a falsa abstenção reproduzível sob o prompt v2, sem mudar o
denominador nem as métricas históricas. A causalidade por saliência de
`ABSTAIN` segue não confirmada. Os dados do subset histórico são uma observação,
não prova de variabilidade verdadeira igual a zero.

A avaliação combina checks estruturais automáticos — JSON, decisão, citações,
cobertura composta, falsa abstenção, resposta insegura e clarificação perdida —
com revisão humana de correção jurídica, groundedness e completude. A revisão
v2 foi concluída nos 32 casos: 29 passaram em correção jurídica, 29 em
groundedness e 25 em completude. Não há LLM-as-judge nem fine-tuning.
`Qwen3-4B-Instruct-2507 Q4_K_M` foi escolhido somente como primeiro candidato;
o runner Ollama pertence à infraestrutura de avaliação e não integra o RAG. O
HOLDOUT continua fechado.

Antes da comparação com um segundo modelo, o diagnóstico pós-hoc de
reprodutibilidade de `GOLD-012` retornou `ABSTAIN` nas seeds 42/43/44, sem
alterar o subset ou as métricas históricas. Isso confirma uma falsa abstenção
reproduzível sob o prompt v2; o comportamento é sensível ao prompt porque o v1
respondeu corretamente. As três avaliações automáticas pós-hoc ainda aguardam
execução pelo usuário. O prompt canônico entre modelos permanece
`gold-evidence-answering/2`; o v3 não resolveu completamente o contrato de
citações, pois `GOLD-015` emitiu textos de evidência em vez de IDs.

O diagnóstico read-only das seis perguntas sem evidência suficiente encontrou
10 candidatos lexicais em todos os casos. Isso descreve candidate generation,
não erro, precisão ou suficiência, e não produziu threshold nem alteração de
retrieval. Os dados estão em
[`docs/retrieval/insufficient-evidence-readonly-diagnostic.md`](docs/retrieval/insufficient-evidence-readonly-diagnostic.md).

A comparação cross-model está congelada para `qwen3.5:9b`,
`phi4-mini:3.8b-q4_K_M`, `gemma3:4b` e `gemma4:12b`, nessa ordem e sem early
stop. Todos usarão o bundle imutável do prompt
`gold-evidence-answering/2`, a mesma configuração, timeout de 180 segundos e os
mesmos três pilares: avaliação automática, estabilidade nos 12 casos
predefinidos e revisão humana. O probe GOLD-012 e o scorecard
`RISK-01..RISK-08` também são obrigatórios para todos.

As identidades reais dos quatro modelos, seus digests Q4_K_M, o hardware, a
política de thinking e os hashes dos inputs estão congelados em
[`gold_evidence_cross_model_manifest_v1.json`](evaluation/runs/gold_evidence_cross_model_manifest_v1.json).
Qwen3.5 e Gemma4 declaram thinking nativo e serão executados com
`think=false`; Phi-4-mini e Gemma3 não declaram essa capability. O Codex não
executou inferência. Os comandos manuais completos estão no
[`runbook cross-model`](docs/evaluation/cross-model-gold-evidence-runbook-v1.md).

O full run já congelado do Qwen3.5 foi avaliado offline, sem nova inferência:
`AUTOMATIC_PASS=27/32`, JSON/schema/payload válidos em `32/32`, decisão esperada
em `28/32`, zero falsas abstenções, zero respostas inseguras, zero citações
inválidas ou fora da evidência, quatro clarificações perdidas e um caso sem
cobertura integral das citações obrigatórias. A estabilidade nas seeds
42/43/44 foi avaliada pelo mesmo replay offline: `11/12` casos mantiveram a
decisão, com a única instabilidade em `GOLD-032` por JSON truncado na seed 43.
Os passes automáticos foram `10/12`, `8/12` e `9/12`; houve variação do conjunto
de citações em três casos e da cobertura obrigatória em `GOLD-018`.
`GOLD-029` e `GOLD-030` responderam `ANSWER` nas três seeds apesar de exigirem
`CLARIFY`, confirmando `RISK-01` no subconjunto observado. Os três casos de
evidência insuficiente mantiveram `ABSTAIN`, sem resposta insegura.

O probe separado `GOLD-012` respondeu `ANSWER` com
`ARTICLE:67/CAPUT` nas três seeds; decisão, schema, payload e citação passaram
automaticamente em `3/3`. Isso corrige automaticamente o padrão de falsa
abstenção observado no candidato anterior, mas não constitui validação jurídica
final sem revisão humana. O template neutro dos 32 casos foi preenchido pelo
usuário em
`evaluation/results/qwen3_5_9b_prompt_v2_full_automatic_evaluation_human_review.json`;
a consolidação registrou correção jurídica em `29/32`, groundedness em `29/32`,
completude em `26/32`, os três eixos simultâneos em `26/32` e aprovação
automática+humana em `25/32`. O scorecard classificou o Qwen3.5 como
`PARTIALLY_CAPABLE`, mas o rejeitou como answerer jurídico final: `GOLD-029` e
`GOLD-030` repetiram aplicação factual prematura nas três seeds e falharam nos
três critérios humanos. O modelo melhorou frente ao Qwen3-4B em completude,
resultado conjunto, falsas abstenções e citações inválidas, sem eliminar esse
risco de severidade alta. O full run seed 42 do Phi-4-mini foi executado pelo
usuário e avaliado automaticamente em `21/32`: JSON válido em `27/32`, schema
válido em `25/32`, duas falsas abstenções, seis clarificações perdidas e nenhuma
resposta insegura em insuficiência. A estabilidade posterior ficou em `7/12`
decisões oficiais estáveis, com passes de `8/12`, `5/12` e `6/12` nas seeds 42,
43 e 44. O probe `GOLD-012` passou formalmente em `3/3`, mas a seed 43 inverteu
materialmente a polaridade da regra citada; a correção jurídica segue pendente
de validação humana e não é inferida do passe automático. A variação aparente
entre `ANSWER` e `CLARIFY` em `GOLD-029`/`GOLD-030` torna o `RISK-01`
preliminarmente `SAMPLING_SENSITIVE`. A degeneração de `GOLD-030` seed 44 e a
anomalia de grounding de `GOLD-011` seed 43 foram preservadas sem reparo. O
formulário full foi revisado pelo usuário: correção jurídica `26/32`,
groundedness `28/32`, completude `18/32` e os três critérios simultaneamente em
`17/32`. A interseção estrita entre passe automático e os três critérios
humanos ficou em `16/32`. A revisão material dos probes `GOLD-012` confirmou
duas respostas corretas e uma inversão de polaridade na seed 43, apesar de
`3/3` passes formais. O scorecard classificou o Phi-4-mini como
`PARTIALLY_CAPABLE` e o rejeitou como answerer jurídico final devido ao
`RISK-02` material observado. O próximo candidato `gemma3:4b` foi confirmado no
Ollama do Docker Compose com o digest congelado
`a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a` e está
`READY_FOR_MANUAL_RUNS`; os sete runs foram depois executados manualmente pelo
usuário e avaliados offline. O full teve `1/32` passe automático porque `31/32`
respostas vieram como JSON cercado por Markdown fences e permaneceram inválidas
sem reparo. A estabilidade registrou `11/12` decisões formais estáveis, passes
automáticos de `2/12`, `1/12` e `1/12`, e o probe `GOLD-012` falhou formalmente
em `3/3` pelo mesmo problema de JSON. A revisão humana separada registrou
correção jurídica `23/32`, groundedness `28/32`, completude `19/32` e all-pass
material `18/32`; a interseção estrita com o resultado automático foi `1/32`.
Materialmente, `GOLD-012` preservou polaridade em `3/3`. O scorecard classificou
o Gemma3 como `PARTIALLY_CAPABLE` e o rejeitou como answerer jurídico final:
`RISK-01` foi reproduzível em `GOLD-029`/`GOLD-030`, e `31/32` respostas também
descumpriram o contrato formal. Gemma4 concluiu o protocolo com `29/32`
all-pass material e `12/32` na interseção estrita automática+humana, sem
reproduzir `RISK-01` ou `RISK-02` nos casos de referência. Seu veredito é
`RECONSIDER`, pois `20/32` outputs ainda falharam no contrato formal. O corpus
vivo permanece não reconstruído.

O contrato, os formatos e o procedimento manual estão em
[`docs/evaluation/gold-evidence-model-capability.md`](docs/evaluation/gold-evidence-model-capability.md).

## Arquitetura da Fase 0

```text
Source
  → SourceSnapshot
  → LegalAct
  → ActVersion
  → Provision
  → SearchUnit
  → SearchUnitProvision
```

- `SourceSnapshot.raw_bytes` preserva exatamente a resposta HTTP, com SHA-256
  calculado sobre esses bytes e proteção de imutabilidade no PostgreSQL.
- A aquisição usa `If-None-Match` e `If-Modified-Since` quando existem
  metadados anteriores. `304` reutiliza a captura sem alterar `acquired_at`;
  uma resposta `200` com o mesmo SHA também é idempotente.
- O contrato validado da fonte é `windows-1252`, sempre com decoding estrito.
- O parser `planalto-lei-structural/1` opera em memória e termina o documento
  estrutural no primeiro `</html>`. A cauda dinâmica posterior permanece intacta
  em `raw_bytes`, mas não entra na árvore jurídica.
- `ARTICLE` é o contêiner estrutural; `CAPUT` guarda seu texto normativo. As
  demais classes observadas são `DOCUMENT_ROOT`, `CHAPTER`, `PARAGRAPH` e
  `INCISO`.
- A materialização valida parser, cobertura e projeção antes de uma única
  transação. Falhas causam rollback integral.
- Não existe versão `active`, `current` ou `latest`. Cada `ActVersion` possui
  identidade natural e `version_hash` derivados explicitamente do snapshot e
  das versões do parser e da projeção.
- A projeção `provision-text/1` é intencionalmente simples:
  `SearchUnit.search_text = Provision.citation_text`, sem enriquecimento.
- Reprojeção é offline: recebe um SHA de snapshot persistido e não possui
  cliente HTTP ou fallback remoto.

Os contratos completos estão em
[`docs/corpus/foundation-corpus-v02.md`](docs/corpus/foundation-corpus-v02.md).
A investigação da fonte está em
[`docs/corpus/lei-9784-investigation.md`](docs/corpus/lei-9784-investigation.md).

## Banco e corpus

Com o PostgreSQL v0.2 ativo:

```bash
docker compose up -d db
uv run consultor-juridico db migrate
uv run consultor-juridico db status
```

Adquirir a fonte oficial sem materializá-la:

```bash
uv run consultor-juridico corpus adquirir
```

Materializar ou reprojetar um snapshot explicitamente, sem HTTP:

```bash
uv run consultor-juridico corpus materializar --snapshot-sha <sha256>
uv run consultor-juridico corpus reprojetar --snapshot-sha <sha256>
```

Listar e auditar versões:

```bash
uv run consultor-juridico corpus versoes
uv run consultor-juridico corpus auditar --version-hash <hash>
```

Rastrear uma unidade textual até a captura oficial:

```bash
uv run consultor-juridico corpus rastrear \
  --version-hash <hash> \
  --unit-key <unit_key>
```

Executar uma busca lexical isolada:

```bash
uv run consultor-juridico retrieval buscar \
  --mode strict \
  --version-hash <hash> \
  --limit 10 \
  "pergunta"
```

O evaluator grava um novo JSON e recusa sobrescrever resultados existentes:

```bash
uv run consultor-juridico eval retrieval \
  --mode relaxed-or-coverage \
  --dataset evaluation/datasets/lei_9784_retrieval_dev_v1.json \
  --version-hash <hash> \
  --output <novo-arquivo.json>
```

O bundle v3 já foi preparado sem inferência. Para reproduzir o export:

```bash
.venv/bin/consultor-juridico eval gold export \
  --dataset evaluation/datasets/lei_9784_gold_evidence_dev_v1.json \
  --version-hash 298028477a55a61cdd1df94bda3aec784e6fe94d17c485ae6a2f6c77fe2b7a74 \
  --prompt-version 3 \
  --output <novo-bundle-v3.jsonl>
```

O artefato congelado desta rodada está em
`evaluation/runs/gold_evidence_input_prompt_v3.jsonl`.

O protocolo de estabilidade do prompt v2 foi concluído a partir do subset
congelado em `evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl`.
As três seeds mantiveram a decisão em `12/12`; houve variação de cobertura em
dois casos e de conjunto de citações em três. O artefato consolidado está em
`evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_v1.json`.

O template humano v2 preenchido está em
`evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_automatic_evaluation_human_review.json`.
O resultado consolidado está em
`evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_final_review.json`.
A rubrica, o diagnóstico pós-hoc e o scorecard comparativo `RISK-01..RISK-08`
estão documentados no guia da Fase 2.

O runner de avaliação Ollama também está preparado, mas deve ser executado
manualmente pelo usuário após instalar o primeiro candidato. Ele preserva a
resposta bruta e faz uma única geração por caso, sem reparo ou retry semântico.

## Ollama de avaliação

O MVP2 suporta exclusivamente o serviço `ollama` definido no Docker Compose,
sob o profile `llm`. Instalações Ollama no host não são suportadas nem usadas
como fallback. Entre containers, o endereço canônico é
`http://ollama:11434`, configurado por `OLLAMA_BASE_URL`. O endereço
`http://localhost:11435` só pode ser usado por comandos no host para acessar,
via port mapping, esse mesmo container. A instância nativa eventualmente
existente em `http://localhost:11434` não pode ser usada pelo projeto.

Os modelos ficam no volume persistente `consultor_juridico_ollama` e o
download continua deliberadamente manual:

```bash
docker compose --profile llm up -d ollama
docker compose exec ollama \
  ollama pull qwen3:4b-instruct-2507-q4_K_M
```

Não há `ollama pull` em Dockerfile, entrypoint ou startup. O provider atende a
avaliação manual e o runtime RAG; nenhum fallback para Ollama nativo do host é
permitido.

### GPU NVIDIA

Em hosts Linux com GPU NVIDIA, o runtime atual requer driver NVIDIA funcional e
NVIDIA Container Toolkit configurado no Docker. O serviço `ollama` recebe as
GPUs disponíveis pela diretiva Compose `gpus: all`; isso é uma propriedade
operacional do runtime e não altera modelo, digest, prompt ou configuração do
answerer congelado.

Verificações úteis, sem executar inferência:

```bash
nvidia-smi
docker compose --profile llm up -d ollama
docker compose exec ollama nvidia-smi
docker compose logs ollama
```

Nos logs, o Ollama deve identificar um backend CUDA. O endpoint interno continua
`http://ollama:11434` e o acesso ao mesmo container pelo host continua
`http://localhost:11435`. O timeout congelado permanece em 180 segundos. O
smoke de clarificação anterior ficou inconclusivo por timeout e deve ser repetido
manualmente depois desta validação de GPU.

## Consulta RAG integrada

O runtime usa `RELAXED_OR_WEIGHTED_COVERAGE`: os lexemas da pergunta são
ponderados pela raridade documental na `ActVersion`, evitando que termos comuns
ocultem termos discriminativos. Ele converte as `SearchUnit` recuperadas em
evidências canônicas identificadas por
`Provision.stable_key` e monta exatamente o prompt
`gold-evidence-answering/2`. O answerer é o freeze
`gold-evidence-selected-answerer/1`: `gemma4:12b`, digest congelado,
`format=json`, thinking desabilitado e configuração validada antes da chamada.
JSON inválido, drift do freeze/modelo, citação desconhecida ou citação fora do
conjunto fornecido falham fechadamente.

Quando uma SearchUnit recuperada representa um pai textual com filhos normativos
diretos, o assembly inclui esses filhos em ordem documental, limitado a oito por
pai e 24 evidências no total. A expansão é estrutural, determinística e não usa
número de artigo, pergunta ou dataset.

O freeze é uma dependência crítica do runtime. A imagem `app` empacota somente
o artifact canônico e os 13 arquivos cujos hashes ele valida, preservando os
caminhos relativos em `/app/evaluation`. A árvore de avaliações não é copiada
integralmente e nenhum artifact de HOLDOUT entra na imagem. Assim, os comandos
`consultor-juridico eval gold selected-answerer-status` e
`consultor-juridico rag status` funcionam também dentro do container.

O banco local contém uma `ActVersion` materializada da Lei nº 9.784/1999 e
`consultor-juridico rag status` reporta `RAG_READINESS=READY`. Confira o estado,
sem chamar o modelo, com:

```bash
consultor-juridico rag status
consultor-juridico corpus versoes
```

Nos smoke tests manuais, consulte informando a identidade da versão:

```bash
consultor-juridico ask \
  "Quais são os requisitos para delegação de competência?" \
  --version-hash bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6
```

Os cinco cenários e os comandos exatos estão em
[`docs/evaluation/rag-smoke-tests-mvp2.md`](docs/evaluation/rag-smoke-tests-mvp2.md).
O reteste confirmou quatro fluxos seguros e funcionais; o caso de clarificação
respondeu condicionalmente, mas não pediu os fatos faltantes. A primeira campanha
Integrated DEV foi então executada em 32 casos: 24 passaram automaticamente,
sem citação inválida ou resposta insegura em evidência insuficiente. Permanecem
dois misses de retrieval e `RISK-05` nos seis casos ambíguos. A revisão jurídica
material confirmou `24/32` casos integralmente aprovados. A análise geral não
encontrou um fix mínimo único e seguro: os misses têm causas distintas, e o
input atual não representa fatos ausentes de modo que permita um gate de
clarificação determinístico. Nenhum runtime foi alterado e o HOLDOUT continua
fechado.

A reconsideração arquitetural selecionou, para a próxima implementação, um
contrato explícito de dois modos: `LEGAL_RULE` continuará usando o pipeline
congelado; `CASE_APPLICATION` deverá falhar fechadamente com `CLARIFY`, sem
chamar o modelo, enquanto não existir um contrato verificável de fatos. Essa
decisão contém `RISK-01` sem heurísticas, segundo LLM ou mudança do prompt. Ela
ainda não foi integrada ao runtime.

Use `--trace` para inspecionar ranks, scores, `unit_key`, evidências montadas,
citações e identidades de modelo/freeze/prompt, sem expor raciocínio interno.
Dentro do Compose a URL Ollama é `http://ollama:11434`; no host, use somente
`--base-url http://localhost:11435`. Retrieval vazio produz `ABSTAIN` local sem
chamar o modelo. O MVP2 não possui tabelas de chunk ou embedding: `SearchUnit`
é a unidade recuperável, e busca vetorial/RRF permanecem `NOT_JUSTIFIED` pela
Fase 1.

## Desenvolvimento

```bash
uv sync
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
```

Os testes automáticos não acessam o Planalto. A integração PostgreSQL usa um
banco descartável indicado por `V02_TEST_DATABASE_URL`.

## Governança e roadmap

A Fase 0 foi aceita depois da conferência humana de cinco amostras distribuídas
no documento. `citation_text`, limites estruturais, hierarquia, proveniência,
SourceSnapshot e URL oficial foram validados. A Fase 1 selecionou
`RELAXED_OR_COVERAGE` para o piloto. A Fase 2 preparou o DEV, o materializador,
os prompts versionados, a avaliação e o runner manual de Gold Evidence. O
primeiro run do Qwen foi congelado e auditado; os experimentos v2 e v3 foram
concluídos. Novas versões de prompt estão congeladas. O v2 é o candidato do
protocolo de estabilidade concluído com decisões estáveis em `12/12`. A revisão
humana dos 32 outputs também foi concluída. O diagnóstico pós-hoc de `GOLD-012`
confirmou `ABSTAIN` em 3/3 seeds e aguarda somente seus artefatos automáticos. O
v2 permanece como baseline canônico e o Qwen foi rejeitado como answerer
jurídico final. Os quatro candidatos substitutos estão congelados e prontos para
execução manual comparável; nenhum vencedor foi antecipado. A avaliação
automática agora opera sobre o full bundle congelado, com paridade histórica
`32/32` e sem depender do corpus vivo. O full Qwen3.5 foi avaliado em `27/32`,
sua estabilidade em `11/12` decisões estáveis e o probe `GOLD-012` em `3/3`
respostas automáticas válidas. A revisão humana foi concluída e consolidada em
`25/32` passes conjuntos. O scorecard está concluído e rejeitou o candidato
como answerer jurídico final por aplicação factual prematura reproduzível. O
Phi-4-mini concluiu os pilares automáticos: full em `21/32`, estabilidade
oficial em `7/12` e probe `GOLD-012` formalmente aprovado em `3/3`. O probe
teve uma inversão material de polaridade confirmada na seed 43. A revisão humana
do full foi consolidada em `26/32` para
correção jurídica, `28/32` para groundedness, `18/32` para completude, `17/32`
nos três critérios e `16/32` na interseção estrita com o passe automático. O
scorecard final rejeitou o Phi como answerer jurídico devido à falha material de
negação/polaridade observada sob sampling. O próximo candidato obrigatório
`gemma3:4b` concluiu os sete raw runs, avaliação offline e revisão humana. Seu
scorecard o rejeitou como answerer jurídico final por aplicação factual
prematura reproduzível e descumprimento massivo do contrato de output. O último
candidato obrigatório, `gemma4:12b`, concluiu a comparação sem early stop. Seus
sete raw runs manuais passaram na verificação de integridade e foram avaliados
offline com o bundle congelado. O full obteve `12/32` passes automáticos,
`13/32` JSONs válidos e `12/32` payloads/schema válidos; não houve falsa
abstenção, resposta insegura em insuficiência, citação inválida ou fora da
evidência. A estabilidade formal ficou em `5/12`, limitada por JSONs inválidos
e decisões nulas, com passes de `6/12`, `8/12` e `6/12`. O probe `GOLD-012`
passou formal e materialmente em `3/3`. A revisão humana obteve `32/32` em
correção jurídica e groundedness, `29/32` em completude e `29/32` all-pass; o
resultado estrito automático+humano foi `12/32`. O scorecard marcou somente
`RISK-05` como materialmente observado e classificou o candidato como
`RECONSIDER`, sem aceitá-lo como answerer final enquanto persistissem `20/32`
falhas do contrato de output. Naquele checkpoint, a Fase 2 permaneceu aberta
para comparação final e seleção; o corpus vivo seguia `UNRESOLVED` e o HOLDOUT,
fechado e não lido.

Como rodada pós-cross-model separada, o Gemma4 está em reconsideração controlada
com `GEMMA4_FORMAT_JSON_RECONSIDERATION_V1`. A única variável é o structured
output nativo do Ollama (`format=json`); prompt v2, modelo, evidências, seeds,
thinking, timeout e demais opções permanecem congelados. O runner expõe
`--ollama-format json` de forma genérica e opt-in, sem alterar o request padrão.
Os sete comandos estão no
[`runbook da reconsideração`](docs/evaluation/gemma4-format-json-reconsideration-v1.md)
e foram executados manualmente. A avaliação offline obteve JSON válido em
`32/32`, schema/payload em `31/32`, passe automático em `30/32`, cobertura de
citações obrigatórias em `32/32` e estabilidade formal em `12/12`. As duas
falhas preservadas foram `GOLD-027` e `GOLD-031`; `GOLD-012` passou em `3/3`.
Naquele checkpoint automático, a revisão humana ainda estava pendente e não
havia conclusão sobre regressão material. Nenhum resultado ou veredito anterior
fora substituído naquele momento:
`GEMMA4=RECONSIDER` e o HOLDOUT continua fechado.

A revisão humana posterior preservou exatamente o resultado material do
baseline: `32/32` em correção jurídica e groundedness, `29/32` em completude e
all-pass. A interseção estrita subiu de `12/32` para `29/32`. A configuração
`gemma4:12b` com a opção genérica `ollama_format=json` foi, portanto,
`ACCEPTED` como answerer jurídico final da Fase 2. O baseline sem structured
output continua historicamente `RECONSIDER`. As limitações residuais são
`RISK-05`, o schema inválido de `GOLD-027` e a decisão inadequada de
clarificação em `GOLD-031`. O HOLDOUT permanece fechado; o próximo gate é
congelar a configuração e o runtime selecionados antes de RAG ou HOLDOUT.

Esse freeze foi concluído como `gold-evidence-selected-answerer/1`. A identidade
selecionada é `gemma4:12b`, digest
`4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`,
prompt `gold-evidence-answering/2`, thinking desabilitado e
`ollama_format=json`, além da configuração de geração congelada. O contrato é
fail-closed e aceita somente JSON com `decision`, `answer` e `citations`. O
artifact e a política de mudança estão descritos no
[`freeze do answerer`](docs/evaluation/selected-answerer-freeze-v1.md). O risco
residual é `RISK-05`; o HOLDOUT segue fechado. A integração RAG foi
implementada posteriormente, sem modificar esse freeze.

A revisão final confirmou todos os gates canônicos e encerrou formalmente a
Fase 2. O answerer selecionado permanece a configuração completa congelada —
não apenas a tag do modelo — e nenhuma limitação residual foi ocultada. O
próximo bloco é a integração RAG end-to-end: retrieval, evidence assembly,
answerer congelado, validação de citações e resposta rastreável. O HOLDOUT só
poderá ser aberto depois que esse runtime integrado for implementado, avaliado
em DEV e congelado.

```text
Fase 0: Fundação e Corpus (concluída)
  → Fase 1: Retrieval isolado (RELAXED_OR_COVERAGE selecionado)
  → Fase 2: Gold Evidence (concluída; answerer selecionado e congelado)
  → Integração RAG end-to-end (implementada; corpus local pronto)
  → Smoke tests RAG manuais (concluídos o suficiente para DEV)
  → Integrated DEV (primeira medição concluída; revisão humana pendente)
  → HOLDOUT
  → Teste manual
```

A governança do HOLDOUT está documentada em
[`docs/governance/holdout.md`](docs/governance/holdout.md), mas nenhum dataset
HOLDOUT foi criado ou lido nesta fase. O DEV conhecido da Fase 1 não é um
HOLDOUT. Não há alegação atual de qualidade ou prontidão do consultor.

## Seleção do answerer do MVP2

A Fase 2 concluiu a comparação de modelos locais e selecionou o `gemma4:12b`
com structured output (`format=json`) como answerer jurídico congelado do MVP2.
O comparativo completo — métricas, prós e contras, riscos observados e
justificativa da seleção — está em
[`docs/evaluation/comparativo-modelos-answerer-mvp2.md`](docs/evaluation/comparativo-modelos-answerer-mvp2.md).
