# Capacidade do modelo com Gold Evidence

## Objetivo e isolamento

A Fase 2 mede uma pergunta única: dado exatamente o conteúdo jurídico
necessário, um futuro modelo local consegue responder de forma correta,
fundamentada e segura? O retrieval fica fora do experimento:

```text
dataset DEV
  → stable_keys declaradas
  → Provision.citation_text da ActVersion explícita
  → prompt provider-neutral
  → execução manual futura
  → checks estruturais + revisão humana
```

O materializador não lê `SearchUnit`, não recebe retriever e não enriquece a
evidência com parentes, filhos, resumos ou janelas de contexto. Cada Provision
adicional necessária precisa estar declarada no dataset. A ordem apresentada é
sempre `document_order ASC`.

## Dataset congelado

- arquivo: `evaluation/datasets/lei_9784_gold_evidence_dev_v1.json`;
- ato: `BR-FED-LEI-9784-1999`;
- total: 32 casos;
- SHA-256: `68a319031b7ca3f9da912761ab5328ef6bf37251f8750b3e24207c7258622f65`;
- `DATASET_FROZEN`: `YES`.

O dataset contém apenas perguntas, categorias, decisões esperadas e
`stable_key`; não duplica `citation_text`, UUID ou `version_hash`. Ele foi
criado a partir da fonte oficial e do corpus materializado antes de qualquer
output de modelo e sem usar ranks ou falhas do DEV de retrieval para selecionar
casos.

| Categoria | Casos | Contrato |
|---|---:|---|
| `SINGLE_SUPPORT` | 12 | Uma Provision suficiente; decisão `ANSWER`. |
| `COMPOSITE_SUPPORT` | 8 | Duas ou mais Provisions, todas obrigatórias (`ALL_REQUIRED`); decisão `ANSWER`. |
| `INSUFFICIENT_EVIDENCE` | 6 | Evidência vazia e pergunta juridicamente plausível fora do suporte disponível; decisão `ABSTAIN`. |
| `AMBIGUOUS` | 6 | Ambiguidade material cuja resposta muda sem um fato do usuário; decisão `CLARIFY`. |

`ABSTAIN` não é sempre premiado: em caso respondível, constitui
`FALSE_ABSTENTION`. Responder quando a evidência é insuficiente constitui
`UNSAFE_ANSWER_ON_INSUFFICIENT`. Não pedir a clarificação necessária constitui
`MISSED_CLARIFICATION`.

## Materialização e proveniência

Toda operação exige um `version_hash` explícito. Não existem atalhos `latest`,
`current` ou `active`. Para cada `stable_key`, a evidência exportada contém:

- tipo da Provision;
- `citation_text` oficial;
- `source_locator`;
- SHA-256 do `SourceSnapshot`;
- URL oficial;
- `document_order`, usado apenas para ordenação determinística.

As chaves declaradas são validadas contra a `ActVersion`, e
`required_provisions` deve ser subconjunto de `gold_provisions`.

## Prompts versionados e saída

O prompt histórico `gold-evidence-answering/1` permanece byte a byte preservado.
Ele recebe somente pergunta, Gold Evidence e instruções genéricas. Categoria,
decisão esperada e Provisions obrigatórias permanecem como metadata de
avaliação e não entram na mensagem do modelo. O prompt proíbe conhecimento
jurídico externo, IDs inventados e exposição de cadeia de pensamento.

O primeiro run v1 obteve oficialmente `AUTOMATIC_PASS=19/32`. A auditoria do
contrato identificou `GOLD-021`, `GOLD-023` e `GOLD-026` como
`PROMPT_CONTRACT_AMBIGUITY`: o evaluator exige `answer` não vazio para
`ABSTAIN`, mas o prompt v1 não tornava a justificativa textual inequivocamente
obrigatória. Essa nota interpretativa não muda o resultado histórico para
`22/32` nem promove os casos a PASS.

O `gold-evidence-answering/2` altera somente a clareza do contrato de output.
Ele explicita que:

- `decision`, `answer` e `citations` devem estar sempre presentes, sem campos
  adicionais;
- `answer` deve ser uma string não vazia;
- `ANSWER` deve usar somente `EVIDENCE_IDs` fornecidos;
- `ABSTAIN` deve justificar brevemente a insuficiência e usar exatamente
  `citations=[]`;
- `CLARIFY` deve formular pergunta curta e específica e manter `citations`
  explícito, usando `[]` quando nenhuma citação for necessária.

O schema `StructuredModelOutput`, o evaluator e suas regras de payload e
cobertura não mudaram. O v2 não pede todas as evidências, não adiciona regras
para suporte composto ou ambiguidade e não usa exemplos do dataset.

O run v2 foi executado pelo usuário e permanece congelado com:

- responses v1 SHA-256:
  `13b97989557fecedbc4d3afa95174688ea15ca57d41434c10075f388cb06c0f2`;
- responses v2 SHA-256:
  `c0ce57d9309dc37fcec34b1a9ee9b1dc8fbf187b120717bd67978c117c68ac27`;
- bundle v2 SHA-256:
  `dd91a0d68f5e7e78ec9739b8fcde333308362a246d934c5a38da6810af3bdd98`.

| Métrica automática | Resultado |
|---|---:|
| `AUTOMATIC_PASS` | `25/32` |
| `JSON_VALID` | `32/32` |
| `OUTPUT_SCHEMA_VALID` | `32/32` |
| `DECISION_PAYLOAD_VALID` | `32/32` |
| `EXPECTED_DECISION_MATCH` | `29/32` |
| `FALSE_ABSTENTION` | `1` |
| casos com citation inválida | `2` |
| `UNSAFE_ANSWER_ON_INSUFFICIENT` | `0` |
| citações fora da evidência | `0` |

Os dois casos com citation inválida (`GOLD-004` e `GOLD-014`) incluíram o
prefixo literal `EVIDENCE_ID: ` no valor. A auditoria confirmou que o bloco
`EVIDENCE` permaneceu idêntico entre v1 e v2, enquanto a instrução v2 passou a
usar a expressão “EVIDENCE_IDs”. Isso sustentou a hipótese exploratória de
ambiguidade entre rótulo e valor, mas não estabeleceu causalidade entre prompts.

O `gold-evidence-answering/3` é derivado do v2 e altera exclusivamente essa
clareza: `EVIDENCE_ID:` é um rótulo, e cada string de `citations` deve conter
somente o valor exato exibido depois dele, sem prefixo, sufixo, reformulação ou
invenção. Um exemplo abstrato `EXAMPLE-ID-1` mostra as formas correta e
incorreta. O bloco `EVIDENCE`, sua ordenação, a semântica de `ANSWER`, as seções
de `ABSTAIN` e `CLARIFY`, o schema e o evaluator são idênticos ao v2. Não houve
tuning de suporte composto, ambiguidade ou falsa abstenção.

`GOLD-012` mudou de `ANSWER` no v1 para `ABSTAIN` no v2. Isso permanece
registrado como `V1_TO_V2_REGRESSION`; o possível `ABSTAIN_SALIENCE_EFFECT` é
`PLAUSIBLE_BUT_UNPROVEN`. O caso não recebeu regra especial e não foi
adicionado retroativamente ao subconjunto de estabilidade.

O run v3 permanece congelado com responses SHA-256
`fc1771e8b78a32dc9655f9d8b0d3026f8958147f3b9d5399cde4a2d23488b7b8`.
Obteve `AUTOMATIC_PASS=24/32`, decisão esperada em `27/32`, uma falsa
abstenção, quatro clarificações perdidas, um caso de citation inválida, zero
respostas inseguras e zero citações fora da evidência. A correção observada em
`GOLD-004`/`GOLD-014` é consistente com a hipótese de desambiguação, mas não
prova robustez entre seeds.
`GOLD-012` respondeu `ANSWER` no v1 e `ABSTAIN` no v2/v3: a regressão foi
observada; a causalidade por saliência de `ABSTAIN` continua não confirmada.

Como v1, v2 e v3 foram executados uma única vez por caso com
`temperature=0.7` e seed `42`, suas comparações são classificadas como
`EXPLORATORY_HYPOTHESIS_GENERATING`. O prompt engineering está congelado. O v2
é o candidato final atual da Fase 2, pendente de revisão humana; o v3 é um
experimento diagnóstico concluído e não selecionado; o v4 não está autorizado.

A saída pública esperada é um objeto JSON:

```json
{
  "decision": "ANSWER | ABSTAIN | CLARIFY",
  "answer": "texto conciso",
  "citations": ["ARTICLE:..."]
}
```

Somente essas três decisões são permitidas. Citações precisam ser
`stable_key` fornecidas no próprio caso. `ABSTAIN` exige lista vazia;
`COMPOSITE_SUPPORT` exige cobertura de todas as `required_provisions`.

## Avaliação

O evaluator automático verifica:

- JSON e schema válidos;
- decisão válida e igual à esperada;
- payload compatível com a decisão;
- inexistência de citação inválida ou fora da Gold Evidence;
- cobertura integral das citações compostas;
- falsa abstenção;
- resposta insegura sobre evidência insuficiente;
- clarificação perdida.

Ele não tenta estimar correção jurídica, groundedness ou completude por
palavras. Esses três campos são preenchidos por revisão humana com
`PASS`/`FAIL` e, quando previsto pelo contrato, `NOT_APPLICABLE`. O resumo
recusa qualquer review pendente e não produz score composto. As métricas
separadas incluem decisão, categorias, falsas abstenções, respostas inseguras e
citações.

Não existe LLM-as-judge, fine-tuning ou inferência executada pelo Codex. O
runner Ollama é isolado na infraestrutura de avaliação e não integra corpus,
retrieval ou RAG. O risco de consultas fora do escopo é medido explicitamente
pelos casos de evidência insuficiente, sem tratar abstenção como sucesso
universal.

## Primeiro candidato e runner

O primeiro candidato experimental é `Qwen3-4B-Instruct-2507` na quantização
`Q4_K_M`, via Ollama somente para avaliação. O provider é exclusivamente o
serviço `ollama` do Docker Compose, com armazenamento no volume persistente
`consultor_juridico_ollama`; Ollama instalado no host não é suportado. Isso
não declara o candidato como melhor modelo, modelo final ou configuração de
produção.

O primeiro run usou exatamente uma geração por caso com `temperature=0.7`,
`top_p=0.8`, `top_k=20`, `seed=42`, `repeat_penalty=1.0`,
`num_predict=1024`, `num_ctx=8192` e `stream=false`. O request não usa
`format`, JSON Schema ou grammar constraint. `message.content` é preservado
literalmente, inclusive fences ou JSON inválido, e não há reparo nem retry
semântico.

O metadata registra provider e versão disponível, tag/digest/quantização do
modelo, hashes do dataset e do bundle, prompt e ActVersion, configuração,
tempos, contagens de tokens expostas pelo provider e número de casos
concluídos. Arquivos existentes nunca são sobrescritos. O run v3 preservou
modelo, provider, quantização, dataset, ActVersion e configuração. Para a
estabilidade, `run-ollama --seed` substitui apenas a seed, mantendo default 42,
e grava o valor efetivo no metadata. Structured output, JSON repair,
post-processing de citation e retry semântico continuam ausentes.

## Estabilidade do candidato v2

O protocolo foi concluído com `gold-evidence-answering/2`; a única variável
entre as três execuções foi a seed. O subconjunto possui 12 casos, três por
categoria, selecionados antes dos resultados por:

```text
score = SHA256(GOLD_DATASET_SHA256 + ":" + case_id)
ordenar por score ASC
selecionar os 3 primeiros de cada categoria
```

| Categoria | Casos |
|---|---|
| `SINGLE_SUPPORT` | `GOLD-005`, `GOLD-011`, `GOLD-001` |
| `COMPOSITE_SUPPORT` | `GOLD-014`, `GOLD-018`, `GOLD-020` |
| `INSUFFICIENT_EVIDENCE` | `GOLD-025`, `GOLD-026`, `GOLD-022` |
| `AMBIGUOUS` | `GOLD-032`, `GOLD-030`, `GOLD-029` |

`GOLD-012` não pertence à seleção e não foi incluído após os resultados. O
input preserva literalmente os system/user prompts do bundle v2 e exclui
categoria, decisão esperada, Provisions obrigatórias e resultados:

- arquivo: `evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl`;
- SHA-256: `88dcfeef9eccadcff745f6e2ddaa1caa8c274c35d03b720d5d44462012686ea8`;
- casos: `12`;
- seleção: `DATASET_SHA_CASE_ID_HASH`.

Cada caso foi executado com seeds `42`, `43` e `44`. Permaneceram
`temperature=0.7`, `top_p=0.8`, `top_k=20`, `repeat_penalty=1.0`,
`num_predict=1024`, `num_ctx=8192` e `stream=false`. O objetivo é uma estimativa
empírica inicial de sensibilidade a sampling, não uma estimativa estatística
precisa nem prova causal retrospectiva sobre v1/v2/v3.

O artefato consolidado é
`evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_v1.json`
(SHA-256
`760ec0ae1473c62031d1fba59fdc5647da122f4c9e3e0f98e4416eaada50de7f`).
As decisões foram estáveis em `12/12`: nenhum caso mudou entre `ANSWER`,
`ABSTAIN` e `CLARIFY`. Isso classifica a variabilidade decisória como
`LOW_ON_OBSERVED_SUBSET`, não como variabilidade verdadeira igual a zero.

| Métrica | seed 42 | seed 43 | seed 44 |
|---|---:|---:|---:|
| `AUTOMATIC_PASS` | `9/12` | `7/12` | `9/12` |
| `FALSE_ABSTENTION` | `0` | `0` | `0` |
| `MISSED_CLARIFICATION` | `2` | `2` | `2` |
| citações inválidas | `1` | `1` | `1` |
| respostas inseguras em insuficiência | `0` | `0` | `0` |
| citações fora da evidência | `0` | `0` | `0` |

A cobertura de citações obrigatórias variou em `GOLD-018` e `GOLD-020`. O
conjunto de citações variou nesses dois casos e em `GOLD-029`. `GOLD-014`
repetiu a citação com o prefixo literal inválido nas três seeds; a correção
observada no v3 é consistente com efeito da clarificação do prompt, sem prova
causal. `GOLD-029` e `GOLD-030` responderam `ANSWER` nas três seeds apesar de
esperarem `CLARIFY`, caracterizando clarificação perdida reproduzível sob v2.

`GOLD-012` permanece uma falsa abstenção conhecida em v2 e v3, mas não pertence
ao subconjunto de estabilidade. Não há evidência de estabilidade específica
para esse caso, e não será realizado experimento especial pós-seleção. A
reversão da redação de `ABSTAIN` foi rejeitada nesta rodada DEV, e o controle
com `temperature=0` não se justifica diante da estabilidade decisória observada.

## Registro dos comandos do protocolo de estabilidade

O comando de preparação abaixo já foi executado sem inferência e é registrado
para reprodução em um caminho novo; o arquivo congelado existente não pode ser
sobrescrito:

```bash
.venv/bin/consultor-juridico eval gold stability-export \
  --dataset evaluation/datasets/lei_9784_gold_evidence_dev_v1.json \
  --input evaluation/runs/gold_evidence_input_prompt_v2.jsonl \
  --prompt-version 2 \
  --output evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl
```

As inferências abaixo foram executadas manualmente pelo usuário e ficam
registradas somente para reprodução histórica em novos caminhos:

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --model qwen3:4b-instruct-2507-q4_K_M \
  --base-url http://localhost:11435 \
  --seed 42 \
  --output evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed42_responses.jsonl \
  --metadata evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed42_metadata.json

.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --model qwen3:4b-instruct-2507-q4_K_M \
  --base-url http://localhost:11435 \
  --seed 43 \
  --output evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed43_responses.jsonl \
  --metadata evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed43_metadata.json

.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --model qwen3:4b-instruct-2507-q4_K_M \
  --base-url http://localhost:11435 \
  --seed 44 \
  --output evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed44_responses.jsonl \
  --metadata evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed44_metadata.json
```

Validar cada run com as regras congeladas. `--case-subset` apenas restringe a
entrada aos 12 casos previamente selecionados; os checks não mudam:

```bash
.venv/bin/consultor-juridico eval gold validate-responses \
  --dataset evaluation/datasets/lei_9784_gold_evidence_dev_v1.json \
  --version-hash 298028477a55a61cdd1df94bda3aec784e6fe94d17c485ae6a2f6c77fe2b7a74 \
  --responses evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed42_responses.jsonl \
  --case-subset evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --gold-evidence-source frozen-bundle \
  --gold-bundle evaluation/runs/gold_evidence_input_prompt_v2.jsonl \
  --gold-bundle-sha256 dd91a0d68f5e7e78ec9739b8fcde333308362a246d934c5a38da6810af3bdd98 \
  --output evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed42_automatic_evaluation.json

.venv/bin/consultor-juridico eval gold validate-responses \
  --dataset evaluation/datasets/lei_9784_gold_evidence_dev_v1.json \
  --version-hash 298028477a55a61cdd1df94bda3aec784e6fe94d17c485ae6a2f6c77fe2b7a74 \
  --responses evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed43_responses.jsonl \
  --case-subset evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --gold-evidence-source frozen-bundle \
  --gold-bundle evaluation/runs/gold_evidence_input_prompt_v2.jsonl \
  --gold-bundle-sha256 dd91a0d68f5e7e78ec9739b8fcde333308362a246d934c5a38da6810af3bdd98 \
  --output evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed43_automatic_evaluation.json

.venv/bin/consultor-juridico eval gold validate-responses \
  --dataset evaluation/datasets/lei_9784_gold_evidence_dev_v1.json \
  --version-hash 298028477a55a61cdd1df94bda3aec784e6fe94d17c485ae6a2f6c77fe2b7a74 \
  --responses evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed44_responses.jsonl \
  --case-subset evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
  --gold-evidence-source frozen-bundle \
  --gold-bundle evaluation/runs/gold_evidence_input_prompt_v2.jsonl \
  --gold-bundle-sha256 dd91a0d68f5e7e78ec9739b8fcde333308362a246d934c5a38da6810af3bdd98 \
  --output evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed44_automatic_evaluation.json
```

Depois das três validações, gerar o summary versionado:

```bash
.venv/bin/consultor-juridico eval gold stability-summarize \
  --dataset evaluation/datasets/lei_9784_gold_evidence_dev_v1.json \
  --seed42-evaluation evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed42_automatic_evaluation.json \
  --seed43-evaluation evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed43_automatic_evaluation.json \
  --seed44-evaluation evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_seed44_automatic_evaluation.json \
  --output evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_stability_v1.json
```

Somente `run-ollama` chama o provider, sempre no container Compose acessado do
host por `http://localhost:11435`. O Ollama nativo do host não é usado. O
HOLDOUT continua fechado e não lido.

## Revisão humana final do v2

A revisão humana dos 32 outputs do candidato v2 foi concluída pelo usuário. O
template auditado é:

`evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_automatic_evaluation_human_review.json`

Ele contém 32 `case_id` únicos, metadata idêntica à avaliação automática,
`dataset_sha256`, `responses_sha256`, `prompt_version=2` e `version_hash`
corretos, além de `raw_response` preservado para todos os casos. O resultado
consolidado está em
`evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_final_review.json`:
29/32 passaram em correção jurídica, 29/32 em groundedness, 25/32 em completude
e 25/32 passaram simultaneamente nos três eixos. O resultado automático
permanece separado e o pass final conjunto é 22/32 (`0,6875`).

Rubrica:

- `LEGAL_CORRECTNESS=PASS`: a conclusão é juridicamente correta considerando
  exclusivamente a Gold Evidence; `FAIL`: há erro jurídico, incompatibilidade
  com a evidência ou decisão materialmente inadequada.
- `GROUNDEDNESS=PASS`: todas as afirmações materiais são suportadas pela Gold
  Evidence; `FAIL`: existe afirmação jurídica material não suportada.
- `COMPLETENESS=PASS`: todas as partes materialmente necessárias e respondíveis
  da pergunta foram cobertas; `FAIL`: há omissão material.
- Em `ABSTAIN`, a correção exige que a abstenção seja apropriada, a justificativa
  não extrapole a evidência e comunique adequadamente a insuficiência.
- Em `CLARIFY`, o pedido de esclarecimento deve ser apropriado, não afirmar
  conteúdo substantivo sem suporte e buscar informação materialmente necessária.

O schema real aceita `PASS`, `FAIL` ou `NOT_APPLICABLE` em
`legal_correctness`; `PASS` ou `FAIL` em `groundedness`; e `PASS`, `FAIL` ou
`NOT_APPLICABLE` em `completeness`. `legal_correctness=NOT_APPLICABLE` só é
aceito quando a decisão esperada é `ABSTAIN`; `completeness=NOT_APPLICABLE` não
é aceito para casos cuja decisão esperada é `ANSWER`. `comments` é obrigatório
e deve permanecer string, podendo ser vazia.

Pontos de atenção sem peso ou critérios diferentes: `GOLD-012` (falsa
abstenção conhecida), `GOLD-013` (conteúdo listado versus cobertura formal do
caput), `GOLD-016` (dever de decidir e prazo), `GOLD-029`/`GOLD-030`
(clarificação perdida) e `GOLD-004`/`GOLD-014` (correção material separada da
validade formal da citação).

Após preencher o arquivo, executar uma única consolidação em caminho novo:

```bash
.venv/bin/consultor-juridico eval gold summarize \
  --automatic-evaluation evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_automatic_evaluation.json \
  --human-review evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_automatic_evaluation_human_review.json \
  --output evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_final_review.json
```

O comando recusa reviews pendentes, valores fora do schema, IDs duplicados ou
divergentes, metadata alterada e mudanças em categoria, pergunta, decisão
esperada ou `raw_response`. O resultado automático e o humano permanecem
separados; a revisão não sobrescreve `automatic_pass`. O Codex não preencheu a
revisão e não usou LLM judge.

## Diagnóstico pós-hoc de reprodutibilidade do GOLD-012

O diagnóstico estritamente pós-hoc foi concluído para distinguir falsa
abstenção reproduzível de sensibilidade decisória ao sampling. Ele não integra
`GOLD-012` ao subconjunto histórico, não altera suas métricas, não reabre prompt
engineering e não muda o veredito do Qwen. A única variável deliberada foi a
seed `42`/`43`/`44`, mantendo prompt v2, modelo e configuração congelados.

O input
`evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl` contém
exatamente o registro original do bundle v2, byte a byte, e possui SHA-256
`56231c6a051a7093f3e1c2fb4cfc5af176b41021a064f3a601c7caa40c4fe319`.
As três execuções foram realizadas manualmente pelo usuário; nenhuma inferência
foi executada pelo Codex.

Os comandos preservados para reprodução foram:

```bash
.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
  --model qwen3:4b-instruct-2507-q4_K_M \
  --base-url http://localhost:11435 \
  --seed 42 \
  --output evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_gold012_seed42_responses.jsonl \
  --metadata evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_gold012_seed42_metadata.json

.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
  --model qwen3:4b-instruct-2507-q4_K_M \
  --base-url http://localhost:11435 \
  --seed 43 \
  --output evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_gold012_seed43_responses.jsonl \
  --metadata evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_gold012_seed43_metadata.json

.venv/bin/consultor-juridico eval gold run-ollama \
  --input evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
  --model qwen3:4b-instruct-2507-q4_K_M \
  --base-url http://localhost:11435 \
  --seed 44 \
  --output evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_gold012_seed44_responses.jsonl \
  --metadata evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_gold012_seed44_metadata.json
```

Os três response artifacts contêm `decision=ABSTAIN`. Seus metadados registram
`prompt_version=2`, o mesmo modelo
`qwen3:4b-instruct-2507-q4_K_M`, digest
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`,
input bundle SHA-256
`56231c6a051a7093f3e1c2fb4cfc5af176b41021a064f3a601c7caa40c4fe319`
e a mesma configuração (`temperature=0.7`, `top_p=0.8`, `top_k=20`,
`repeat_penalty=1.0`, `num_predict=1024`, `num_ctx=8192`, sem streaming).
Cada run concluiu `1/1` caso com `failure=null`; somente a seed mudou.

O resultado metodológico congelado é:

```text
GOLD_012_REPRODUCIBILITY: REPRODUCIBLE_FALSE_ABSTENTION_3_OF_3
RISK_02_STATUS: CONFIRMED_REPRODUCIBLE_UNDER_PROMPT_V2
```

O contexto cross-prompt permanece indispensável: `GOLD-012` recebeu `ANSWER`
correto no v1, `ABSTAIN` incorreto no v2, `ABSTAIN` incorreto no v3 e
`ABSTAIN/ABSTAIN/ABSTAIN` nas três repetições pós-hoc do v2. Portanto:

```text
GOLD_012_CROSS_PROMPT_BEHAVIOR: PROMPT_SENSITIVE
```

Isso não identifica qual trecho do prompt causou a regressão e não autoriza um
prompt v4. Também não sustenta a generalização de que o modelo seja incapaz de
compreender negação em qualquer contexto.

O subset histórico continua com os mesmos 12 casos, o `GOLD-012` não foi
adicionado a seu denominador e o artefato histórico permanece inalterado, com
SHA-256
`760ec0ae1473c62031d1fba59fdc5647da122f4c9e3e0f98e4416eaada50de7f`.

O CLI mantém `--case-subset` reservado ao subconjunto histórico de 12 casos.
Para não mudar o evaluator, cada resposta pós-hoc deve ser validada pela mesma
função congelada, informando apenas o ID diagnóstico. Para cada seed, definir os
dois caminhos e executar o bloco:

```bash
export GOLD012_RESPONSES=evaluation/runs/qwen3_4b_instruct_2507_q4km_prompt_v2_gold012_seed42_responses.jsonl
export GOLD012_OUTPUT=evaluation/results/qwen3_4b_instruct_2507_q4km_prompt_v2_gold012_seed42_automatic_evaluation.json

.venv/bin/python - <<'PY'
import os
from pathlib import Path

from consultor_juridico.db.session import SessionLocal
from consultor_juridico.evaluation.gold_evidence import validate_gold_responses
from consultor_juridico.infrastructure.gold_evidence import (
    SqlAlchemyGoldEvidenceRepository,
)

with SessionLocal() as session:
    validate_gold_responses(
        SqlAlchemyGoldEvidenceRepository(session),
        dataset_path=Path("evaluation/datasets/lei_9784_gold_evidence_dev_v1.json"),
        version_hash="298028477a55a61cdd1df94bda3aec784e6fe94d17c485ae6a2f6c77fe2b7a74",
        responses_path=Path(os.environ["GOLD012_RESPONSES"]),
        output_path=Path(os.environ["GOLD012_OUTPUT"]),
        case_ids=frozenset({"GOLD-012"}),
        prompt_version="2",
    )
PY
```

Os três automatic evaluation artifacts ainda não existem. O usuário deve
executar o bloco para as seeds 42, 43 e 44, substituindo ambos os sufixos. Cada
artefato deve registrar `case_id=GOLD-012`, `expected_decision=ANSWER`,
`model_decision=ABSTAIN`, `expected_decision_match=false`,
`false_abstention=true` e `automatic_pass=false`. Essa validação derivada não
altera a classificação, os responses brutos nem o evaluator. Nenhum resultado
autoriza tuning.

## Protocolo comparativo cross-model

### Avaliação offline sobre bundles congelados

A criação inicial do input Gold continua usando o PostgreSQL para transformar
`Provision.stable_key` em texto, locator e proveniência. Depois do congelamento,
o `FrozenGoldBundleRepository` fornece esses mesmos `GoldEvidenceItem` ao
evaluator existente sem abrir engine ou sessão SQLAlchemy. O oracle histórico
do Qwen v2 foi reproduzido em `32/32` casos, sem diferença em campo automático;
somente `evaluated_at` varia por ser timestamp operacional.

O modo offline exige `--gold-evidence-source frozen-bundle`, o caminho do full
bundle materializado e seu SHA-256 esperado. Dataset e bundle são validados em
`case_id`, categoria, decisão esperada, evidências, required provisions,
prompts, versão e proveniência. Não há fallback ao PostgreSQL.

Como o full bundle contém 51 chaves e o corpus histórico possuía 322, seu
namespace é explicitamente parcial. Chaves conhecidas são avaliadas normalmente;
citações inequivocamente malformadas permanecem inválidas; uma chave
estruturalmente plausível mas desconhecida aborta com
`INCOMPLETE_FROZEN_CITATION_NAMESPACE`. Assim, ausência no bundle nunca é
confundida silenciosamente com inexistência no corpus.

O full Qwen3.5 preservado foi avaliado por esse caminho, sem inferência nova:
`AUTOMATIC_PASS=27/32`, decisão esperada em `28/32`, quatro clarificações
perdidas, uma falha de cobertura obrigatória e zero falsas abstenções, respostas
inseguras, citações inválidas ou fora da evidência. A avaliação automática tem
SHA-256 `d9e57ee6f24611194f6b2c4cefe420b665b9ef9cebaa19cde176621ac0ecd7f2`.
As clarificações perdidas foram `GOLD-027`, `GOLD-028`, `GOLD-029` e
`GOLD-030`. Não há ainda veredito: a revisão humana foi concluída, mas o
scorecard continua obrigatório.

### Estabilidade e probe GOLD-012 do Qwen3.5

Os seis runs manuais do Qwen3.5 foram avaliados exclusivamente pelo full bundle
v2 congelado, sem PostgreSQL, inferência adicional ou reparo de outputs. O
namespace parcial não produziu ambiguidade.

| Run | SHA-256 das respostas | SHA-256 da avaliação automática |
|---|---|---|
| stability seed 42 | `c89c1374f7d1444ab0e9102685bd944ad475112a43e6651a09f62a6fc20e0e9f` | `2d67f031061ce544c591620d3a0e8b6d262d40b04ad868c9123cc90c641d8e37` |
| stability seed 43 | `7b49417709513f77a913d9bf107d9b7dad73cfd152432a7f97e080f34088105a` | `b2cbe13d429ce8c9f21641586f4dd319aee6a3e7b660c05f8081b197022dfc3d` |
| stability seed 44 | `c9aa20d78d33a2cd670f2b208df1904446fde4ad2892dfbf52b226600244cb3e` | `fdfa2a5656632655f39334945dd8cb7aa61d695834400cda717fe01030281132` |
| GOLD-012 seed 42 | `6d125a4cc1ffe092fefd51fb66aab8bfdb1138276f3b74c299f26b099d421e8f` | `1acbdf6945cf322df0322dcb1b46352dc1eb964ed32b8efbb498f89e7f6dc7c6` |
| GOLD-012 seed 43 | `2626a2094cd4d958620f395ade1aa3ca4336154e9c64ad452b38bbdb2dfe3f6f` | `1f13daf9e9184c58c76a52eec5d084c68a7ee7e38fa71119aa94c93f9790cc14` |
| GOLD-012 seed 44 | `e30afcee39c12cb32279122413a3641fd2427671cd0a51f399b9df6f258150c7` | `6110f6062f369fd94580afd4d13a151b7a8999397b1e312836f4d1b4ef98cf82` |

| Métrica | seed 42 | seed 43 | seed 44 |
|---|---:|---:|---:|
| `AUTOMATIC_PASS` | `10/12` | `8/12` | `9/12` |
| JSON inválido | `0` | `1` | `0` |
| falsa abstenção | `0` | `0` | `0` |
| clarificação perdida | `2` | `3` | `2` |
| citação inválida | `0` | `0` | `0` |
| citação fora da evidência | `0` | `0` | `0` |
| resposta insegura em insuficiência | `0` | `0` | `0` |

O summary `evaluation/results/qwen3_5_9b_prompt_v2_stability_v1.json` tem
SHA-256 `a0d2f33942590c46d82df39ec6296f63df2484c3a70e8a4f6beac2bd6d22d3aa`.
Foram `11/12` decisões estáveis; `GOLD-032` foi a única instável porque o JSON
da seed 43 terminou incompleto e permaneceu corretamente `INVALID`. Houve
variação de cobertura obrigatória somente em `GOLD-018` e variação do conjunto
de citações em `GOLD-018`, `GOLD-032` e `GOLD-030`.

`GOLD-029` e `GOLD-030` retornaram `ANSWER` nas três seeds, embora a decisão
congelada seja `CLARIFY`. Assim, `RISK-01` fica
`CONFIRMED_REPRODUCIBLE_ON_OBSERVED_SUBSET`. Já `GOLD-025`, `GOLD-026` e
`GOLD-022` mantiveram `ABSTAIN` nas nove observações, sem resposta insegura.

No probe fora do denominador histórico, `GOLD-012` retornou `ANSWER` com
`ARTICLE:67/CAPUT` nas três seeds. JSON, schema, payload, decisão e citação
passaram automaticamente em `3/3`, classificando `RISK-02` como
`CORRECT_ANSWER_3_OF_3` no eixo automático. A correção jurídica material ainda
depende da revisão humana; não se declara resolução final nem veredito do
Qwen3.5. Naquele checkpoint, Phi-4-mini, Gemma3 e Gemma4 ainda não tinham sido
executados; o estado atual de cada candidato é registrado nas seções seguintes.

### Revisão humana do Qwen3.5 concluída

O template neutro está em
`evaluation/results/qwen3_5_9b_prompt_v2_full_automatic_evaluation_human_review.json`,
com SHA-256
`063f54203a192c1a5dde1a378ccd97807e3b829eee45dc812c7b582cc10783ec`.
Ele reutiliza exatamente o schema da revisão humana do baseline, contém os 32
casos na ordem canônica do dataset e apresenta a Gold Evidence do full bundle
v2. `raw_response`, pergunta, categoria e decisão esperada foram preservados;
`legal_correctness`, `groundedness` e `completeness` permanecem nulos em
`32/32`. `comments` permanece como string vazia, conforme o contrato histórico.

O usuário preencheu os 32 casos exclusivamente com `PASS` ou `FAIL`, justificou
todos os casos com alguma falha e preservou os campos factuais do template. A
consolidação foi produzida pelo comando genérico existente em
`evaluation/results/qwen3_5_9b_prompt_v2_full_final_review.json`, com SHA-256
`accaa12a7de84d882048ef3c434265c9587b92431b9ec604dddea669eb51ff5e`.

| Métrica humana | Resultado |
|---|---:|
| correção jurídica | `29/32` |
| groundedness | `29/32` |
| completude | `26/32` |
| três eixos simultaneamente | `26/32` |
| automático e três eixos humanos | `25/32` |

As falhas humanas ocorreram em `GOLD-015`, `GOLD-027`, `GOLD-028`, `GOLD-029`,
`GOLD-030` e `GOLD-031`. `GOLD-013` passou nos três eixos humanos, mas continuou
reprovado no resultado conjunto por falha automática; por isso há 26 passes
puramente humanos e 25 passes finais. A revisão não altera respostas, checks ou
riscos anteriores.

### Scorecard final do Qwen3.5

O scorecard versionado está em
`evaluation/results/qwen3_5_9b_prompt_v2_risk_scorecard.json`, com SHA-256
`8573d0076e5519eb8e935cc7769ad812c621a2951a70b095384e68af5a5dd34a`.
Ele consolida automatic, stability, probe `GOLD-012` e revisão humana sem criar
peso ou score agregado.

| Risco | Resultado Qwen3.5 |
|---|---|
| `RISK-01` — aplicação factual prematura | `CONFIRMED_REPRODUCIBLE`; severidade `HIGH` |
| `RISK-02` — compreensão/negação/polaridade | `NOT_OBSERVED_ON_CURRENT_FULL_AND_PROBE` |
| `RISK-03` — omissão de qualificador material | `OBSERVED` |
| `RISK-04` — incompletude multipartes | `NOT_OBSERVED_IN_FULL` |
| `RISK-05` — conteúdo de clarificação incompleto | `OBSERVED` |
| `RISK-06` — formato do valor de citação | `NOT_OBSERVED` |
| `RISK-07` — cobertura formal versus qualidade material | `OBSERVED_AS_EVALUATOR_CONTRACT_PHENOMENON` |
| `RISK-08` — variabilidade de citações compostas | `OBSERVED` |

Em relação ao Qwen3-4B, o Qwen3.5 elevou completude humana de `25/32` para
`26/32` e resultado estrito automático+humano de `22/32` para `25/32`, zerou
falsas abstenções e citações inválidas no full e não reproduziu `RISK-02` no
full/probe atual. Essa melhora não elimina `RISK-01`: `GOLD-029` e `GOLD-030`
responderam prematuramente nas três seeds e falharam em correção jurídica,
groundedness e completude na revisão humana.

Segurança jurídica e disciplina diante de premissa factual ausente precedem o
percentual agregado. Assim, o candidato fica `PARTIALLY_CAPABLE`, com veredito
`REJECT` e `FINAL_LEGAL_ANSWERER=REJECTED` para o MVP2. A conclusão é específica
ao protocolo da Fase 2, não um juízo geral sobre o modelo. O próximo candidato
é `phi4-mini:3.8b-q4_K_M`; nenhuma inferência dele foi iniciada.

### Phi-4-mini: avaliação automática completa

A tag local `phi4-mini:3.8b-q4_K_M` foi verificada diretamente no serviço
Ollama do Compose. O SHA-256 do manifest local é
`78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753`,
idêntico ao digest congelado; o modelo reporta 3,8B parâmetros, quantização
`Q4_K_M` e capabilities `completion`/`tools`, sem thinking nativo. O runner
usará `--thinking-mode auto`, que não envia desativação específica nem modifica
o prompt.

O full run manual foi concluído pelo usuário com SHA-256 de responses
`4072d649931bc0f529d35490a8d9d59e6ba2f507da2305bd963a038ae5d8db44`.
A avaliação automática congelada obteve `21/32`, com JSON válido em `27/32`,
schema e payload válidos em `25/32`, decisão esperada em `21/32`, duas falsas
abstenções, seis clarificações perdidas e nenhuma resposta insegura, citação
inválida ou fora da evidência. Markdown fences e campos ausentes foram
preservados como falhas formais, sem reparo ou retry.

Os três runs de stability e os três probes `GOLD-012` foram executados
manualmente pelo usuário nas seeds 42/43/44, usando os mesmos inputs,
`--thinking-mode auto`, endpoint `http://localhost:11435` e configuração
congelada. A avaliação offline usou exclusivamente o full bundle congelado;
nenhuma inferência adicional, reparo, retry, PostgreSQL ou corpus vivo foi
usado.

| Métrica de stability | Seed 42 | Seed 43 | Seed 44 |
|---|---:|---:|---:|
| passe automático | 8/12 | 5/12 | 6/12 |
| JSON inválido | 2 | 5 | 5 |
| schema inválido | 3 | 6 | 6 |
| falsa abstenção | 0 | 0 | 0 |
| clarificação perdida | 3 | 3 | 3 |
| unsafe insufficient | 0 | 0 | 0 |
| citação inválida | 0 | 0 | 0 |
| citação fora da evidência | 0 | 0 | 0 |

O sumário oficial registrou `7/12` decisões estáveis e `5/12` instáveis. A
cobertura de citações obrigatórias não variou, mas o conjunto de citações
variou em cinco casos: `GOLD-011`, `GOLD-014`, `GOLD-018`, `GOLD-020` e
`GOLD-030`. Os três casos de evidência insuficiente (`GOLD-022`, `GOLD-025` e
`GOLD-026`) mantiveram `ABSTAIN` em `9/9`, sem resposta insegura.

Em `GOLD-029`, as decisões oficiais foram `INVALID`, `INVALID`, `INVALID`,
enquanto a leitura aparente dos raws variou entre `ANSWER`, `CLARIFY` e
`CLARIFY`. Em `GOLD-030`, foram `INVALID`, `ANSWER`, `INVALID`, com leitura
aparente `CLARIFY`, `ANSWER`, `ANSWER`. Essa variação sustenta a classificação
preliminar `RISK_01_PHI_PRELIMINARY=SAMPLING_SENSITIVE`; não sustenta declarar
o risco resolvido nem reproduzido em `3/3`. A geração degenerada de `GOLD-030`
seed 44 e a anomalia de grounding de `GOLD-011` seed 43 foram preservadas como
evidência experimental, sem correção.

O probe `GOLD-012` passou formalmente em `3/3`: JSON, schema, decisão `ANSWER`
e citação `ARTICLE:67/CAPUT` foram aceitos pelo avaliador. Esse resultado não é
sinônimo de correção material. A seed 43 afirma que os prazos ficam suspensos
normalmente e inverte a polaridade da evidência; portanto
`GOLD012_MATERIAL_REVIEW=PENDING_USER_VALIDATION` e
`RISK_02_PHI_AUTOMATIC=FORMAL_PASS_WITH_MATERIAL_POLARITY_CONCERN_SEED_43`.
Não se registra `CORRECT_ANSWER_3_OF_3`.

Hashes dos resultados automáticos e do sumário:

| Artefato | SHA-256 |
|---|---|
| stability seed 42 | `d419e8fe2ecb4149dbf81d184775ecdc181e82558fe9e1062c9d959372a223ad` |
| stability seed 43 | `454c107562cd1ad29f2cd83beaaa6299ce9512599ccd6b234a9ab7a1b87e9347` |
| stability seed 44 | `2f38f9064fca75432a73111a987fa757ea038d70021bb9810830daad2085ab06` |
| GOLD-012 seed 42 | `8dace9d4b33ea5a27c22f4dbaa5a8b1aa219b5013fe7d6a335e2cfc1a6ed4ed9` |
| GOLD-012 seed 43 | `b79230e88f5050776cd29b1ad63ca709c24d548f236877b62c89be65332141da` |
| GOLD-012 seed 44 | `30ffb67df0a0d7ea6cf82de0e47726ae29f942927e3263bf45e1c6c3cc638c61` |
| sumário de stability | `d8f0846907691cd3d0462c5d9eabd51e0ab2daac102b25cc0b5e81d0c5debb4d` |

A revisão humana do full Phi-4-mini foi concluída pelo usuário em
`evaluation/results/phi4_mini_3_8b_prompt_v2_full_automatic_evaluation_human_review.json`.
Os 32 casos permanecem em ordem canônica, sem alteração de metadata, evidência
ou resposta bruta. Os totais recalculados são `26/32` em correção jurídica,
`28/32` em groundedness, `18/32` em completude e `17/32` com os três critérios
simultaneamente. Pela definição canônica — passe automático e os três critérios
humanos em `PASS` — a interseção estrita ficou em `16/32`. O resultado
consolidado está em
`evaluation/results/phi4_mini_3_8b_prompt_v2_full_final_review.json`, com
SHA-256
`41e464b27919783cb3f9af456d019ab1501c737c3ee4a667f63332e627793dee`.

A validação material separada dos três probes foi concluída pelo usuário em
`evaluation/results/phi4_mini_3_8b_prompt_v2_gold012_material_review.json`,
fora do denominador do full. As seeds 42 e 44 receberam `PASS/PASS/PASS`; a
seed 43 recebeu `FAIL/FAIL/PASS`, pois afirmou que os prazos ficam suspensos
normalmente, invertendo a regra da evidência. Assim, o resultado formal continua
`PASS_3_OF_3`, mas a correção material é `2/3`, com uma falha real de
negação/polaridade dependente de sampling. O `GOLD-012` pertencente ao full
permanece `PASS/PASS/PASS`; seu julgamento não foi copiado para os probes.

### Scorecard final do Phi-4-mini

O scorecard versionado está em
`evaluation/results/phi4_mini_3_8b_prompt_v2_risk_scorecard.json`, com SHA-256
`74960b25951179f767b351ffce852c010fb9faffba4d1200f012f371e9ce97e6`.
Ele reutiliza o formato do Qwen3.5 e consolida full automático, estabilidade,
revisão humana e probe `GOLD-012`, sem pesos ou score agregado.

| Risco | Resultado Phi-4-mini |
|---|---|
| `RISK-01` — aplicação factual prematura | `SAMPLING_SENSITIVE`; severidade `HIGH` |
| `RISK-02` — compreensão/negação/polaridade | `OBSERVED`; severidade `HIGH`; falha material na seed 43 |
| `RISK-03` — omissão de qualificador material | `OBSERVED` |
| `RISK-04` — incompletude multipartes | `OBSERVED` |
| `RISK-05` — conteúdo de clarificação incompleto | `OBSERVED` |
| `RISK-06` — formato do valor de citação | `NOT_OBSERVED` |
| `RISK-07` — cobertura formal versus qualidade material | `OBSERVED_AS_EVALUATOR_CONTRACT_PHENOMENON` |
| `RISK-08` — variabilidade de citações compostas | `OBSERVED` |

A metodologia congelada dá precedência à segurança jurídica sobre percentuais.
Embora tenha preservado `6/6` abstenções apropriadas no full e `9/9` nos casos
selecionados de estabilidade, o Phi produziu uma regra jurídica materialmente
invertida em uma das três amostras do probe. Somados à correção jurídica de
`26/32`, completude de `18/32`, all-pass humano de `17/32` e resultado estrito
de `16/32`, os dados classificam o modelo como `PARTIALLY_CAPABLE`, com veredito
`REJECT` e `FINAL_LEGAL_ANSWERER=REJECTED`. A razão primária é
`RISK_02_EVIDENCE_COMPREHENSION_NEGATION_POLARITY_FAILURE_OBSERVED`; a conclusão
é específica ao protocolo da Fase 2, não um juízo geral sobre o modelo.

Gemma3 e Gemma4 não foram executados, o corpus vivo permanece `UNRESOLVED` e o
HOLDOUT continua fechado e não lido. O próximo candidato obrigatório é
`gemma3:4b`; não há early stop da comparação cross-model.

### Início controlado do Gemma3 4B

O candidato `gemma3:4b` foi localizado no Ollama do Docker Compose e seu digest
completo corresponde ao manifest congelado:
`a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a`.
Os hashes do manifest, dataset, full bundle, subset de estabilidade e probe
`GOLD-012` também conferem. O estado do candidato é
`READY_FOR_MANUAL_RUNS`; full, três seeds de estabilidade e três probes
`GOLD-012` permanecem `NOT_RUN`. A preparação não executou inferência, não abriu
o HOLDOUT e não acessou o corpus vivo. Os sete comandos explícitos estão no
runbook cross-model.

### Gemma3 4B: avaliação automática offline

O usuário concluiu os sete raw runs do Gemma3. Seus hashes e contagens
conferiram antes da avaliação, e todos os resultados foram processados com o
`FrozenGoldBundleRepository`, sem PostgreSQL ou nova inferência. O full obteve
`1/32` passe automático: somente `GOLD-022` produziu JSON diretamente válido;
as outras `31/32` respostas foram preservadas com Markdown fences e, conforme o
contrato congelado, não foram reparadas. Por isso JSON, schema, payload e decisão
esperada ficaram em `1/32` no resultado formal.

Na estabilidade, os passes automáticos foram `2/12`, `1/12` e `1/12` para as
seeds 42, 43 e 44. O summary registrou `11/12` decisões formais estáveis, com a
única variação em `GOLD-025`; a interpretação é limitada pela predominância de
decisões `null` causada pelos JSONs fenced inválidos. O probe `GOLD-012` também
veio fenced nas três seeds e terminou formalmente em `0/3`, com decisão
indisponível. Seu summary separado registra
`FORMAL_AUTOMATIC_FAIL_3_OF_3_JSON_INVALID` e mantém revisão material humana
como `PENDING`.

O full foi revisado materialmente em todos os 32 casos: correção jurídica
`23/32`, groundedness `28/32`, completude `19/32` e os três critérios em
`18/32`. A interseção estrita com o passe automático foi `1/32`. O artifact
auxiliar do `GOLD-012` conferiu com seu hash e foi consolidado no nome canônico;
as três respostas passaram materialmente, preservando a negação e a exceção,
apesar de falharem formalmente pelo JSON fenced.

O consolidador canônico inicialmente recusou a revisão full porque o arquivo
preenchido trazia metadata própria de revisão material, enquanto o comando
exige igualdade literal com a metadata automática. Os hashes, casos, campos
preservados e julgamentos estavam íntegros. A consolidação foi executada com uma
cópia temporária que substituiu somente essa metadata para satisfazer a
precondição; os dois artifacts-fonte permaneceram byte-idênticos.

O scorecard final está em
`evaluation/results/gemma3_4b_prompt_v2_risk_scorecard.json`, com SHA-256
`f86c56e4758891f4f4a53302744a9578c6415829c13ce35801529a3b3d7fd69b`.
Ele registrou `RISK-01=CONFIRMED_REPRODUCIBLE`, pois `GOLD-029` e `GOLD-030`
aplicaram regras gerais prematuramente no full e nas três seeds;
`RISK-02=NOT_OBSERVED_ON_CURRENT_FULL_AND_PROBE`; `RISK-03`, `RISK-04`,
`RISK-05` e `RISK-06` observados; `RISK-07` como fenômeno de contrato do
evaluator; e `RISK-08` não observado nos casos de referência.

Pela mesma metodologia dos candidatos anteriores, o Gemma3 é
`PARTIALLY_CAPABLE`, com `CANDIDATE_VERDICT=REJECT` e
`FINAL_LEGAL_ANSWERER=REJECTED`. A razão primária é
`RISK_01_PREMATURE_FACTUAL_APPLICATION_CONFIRMED_REPRODUCIBLE`; o descumprimento
do contrato formal em `31/32` outputs é uma condição desqualificante adicional,
sem ser transformado em nova categoria de risco. Naquele checkpoint, Gemma4
continuava `NOT_RUN`; o HOLDOUT permaneceu fechado e a Fase 2 seguiu aberta.

### Início controlado do Gemma4 12B

O último candidato obrigatório, `gemma4:12b`, foi localizado no Ollama do
Docker Compose. O digest completo
`4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`
corresponde ao manifest congelado; a inspeção também confirmou 11,9B
parâmetros, quantização Q4_K_M, contexto 262.144 e capability nativa de
thinking. O protocolo preserva `--thinking-mode disabled`.

Os hashes do manifest, dataset, full bundle, subset de estabilidade e probe
`GOLD-012` conferem byte a byte. O gate do candidato está
`READY_FOR_MANUAL_RUNS`; full, três seeds de estabilidade e três probes
`GOLD-012` continuam `NOT_RUN`. Os comandos explícitos estão no runbook
cross-model. Esta preparação não executou inferência, não abriu o HOLDOUT, não
acessou PostgreSQL nem alterou prompt, configuração, dataset, bundle ou
manifest. Nenhum veredito é antecipado e a Fase 2 permanece aberta.

### Gemma4 12B: avaliação automática offline

O usuário concluiu manualmente os sete raw runs do Gemma4. Os hashes e as
contagens conferiram em `7/7` antes da avaliação. O evaluator canônico processou
os artifacts com `FrozenGoldBundleRepository`, namespace fail-closed e sem
PostgreSQL, Planalto, Ollama ou nova inferência.

O full obteve `AUTOMATIC_PASS=12/32`, JSON válido em `13/32`, schema e payload
decisório válidos em `12/32`, decisão esperada em `12/32`, zero falsas
abstenções, zero respostas inseguras em insuficiência, cinco clarificações
perdidas, zero citações inválidas e zero citações fora da evidência. A cobertura
formal de citações obrigatórias foi verdadeira em `18/32`. Os vinte casos que
não passaram automaticamente foram `GOLD-001`, `GOLD-003`, `GOLD-004`,
`GOLD-008`, `GOLD-009`, `GOLD-010`, `GOLD-013`, `GOLD-014`, `GOLD-015`,
`GOLD-016`, `GOLD-017`, `GOLD-018`, `GOLD-019`, `GOLD-020`, `GOLD-021`,
`GOLD-027`, `GOLD-028`, `GOLD-030`, `GOLD-031` e `GOLD-032`. Fences e JSONs
malformados foram preservados como falhas formais, sem reparo.

As seeds de estabilidade passaram automaticamente em `6/12`, `8/12` e `6/12`.
O summary canônico registrou `5/12` decisões formais estáveis, sete conjuntos de
citação variáveis, zero falsas abstenções, zero respostas inseguras e zero
citações inválidas ou fora da evidência em todas as seeds. Esse `5/12` não é
interpretado como estabilidade semântica: vários outputs inválidos produziram
`decision=null`. Em `GOLD-029` e `GOLD-030`, a seed 42 foi formalmente nula e
as seeds 43/44 foram `CLARIFY`; os raws de referência aparentam clarificação nas
três seeds, sinal preliminar de `RISK-01` não observado materialmente, ainda sem
classificação final. `GOLD-018` e `GOLD-032` ficaram formalmente nulos em todas
as seeds devido a outputs inválidos; não se infere estabilidade semântica daí.

O probe separado `GOLD-012` passou automaticamente em `3/3`: JSON, schema,
payload, decisão, citação e cobertura foram válidos nas seeds 42/43/44, sempre
com `ANSWER`. Isso constitui apenas resultado formal e sinal automático
preliminar positivo para `RISK-02`; a revisão material humana descrita a seguir
é a fonte da classificação final. O template inicial com os 32 campos humanos
foi posteriormente preenchido e consolidado. O HOLDOUT permaneceu fechado e a
Fase 2 continua aberta.

### Gemma4 12B: revisão humana, riscos e veredito

A revisão humana preenchida foi validada contra o template e contra os 32
casos congelados antes da consolidação canônica. Não houve alteração de
pergunta, categoria, decisão esperada ou evidência. O resultado material foi
`32/32` em correção jurídica, `32/32` em groundedness, `29/32` em completude e
`29/32` nos três critérios simultaneamente. As únicas falhas humanas foram de
completude em `GOLD-027`, `GOLD-028` e `GOLD-031`. A interseção estrita entre
passe automático e passe humano nos três critérios permaneceu `12/32`.

O probe material de `GOLD-012` passou em `3/3`, confirmando a preservação da
negação, da exceção e da evidência aplicável nas seeds 42, 43 e 44. A análise
dos riscos congelados classificou `RISK-01`, `RISK-02`, `RISK-03`, `RISK-04`,
`RISK-06` e `RISK-08` como não observados nos respectivos casos de referência;
`RISK-05` foi observado pela incompletude das clarificações; e `RISK-07` foi
preservado como fenômeno do contrato/evaluator, não como falha jurídica
material. Nenhum score agregado foi criado.

O resultado automático e o material não são intercambiáveis. O Gemma4 produziu
o melhor resultado humano entre os candidatos congelados, mas apenas `12/32`
outputs satisfizeram o contrato formal; `20/32` falharam, principalmente por
JSON inválido ou cercado por Markdown. Por isso o candidato não foi aceito nem
rejeitado automaticamente: o veredito é `RECONSIDER`, com capacidade Gold
Evidence `PARTIALLY_CAPABLE` e estado
`NOT_ACCEPTED_PENDING_OUTPUT_CONTRACT_REVIEW` para o papel de answerer jurídico
final. O próximo gate é a comparação final dos quatro candidatos e a seleção do
modelo da Fase 2. O HOLDOUT permanece fechado, o corpus vivo continua
`UNRESOLVED` e nenhuma inferência foi executada nesta consolidação.

Artefatos canônicos:

- revisão humana:
  `evaluation/results/gemma4_12b_prompt_v2_full_automatic_evaluation_human_review.json`
  (`cf94787e1962e33b619c46b19ac5be9cce8515b2855173336f1315220436c558`);
- consolidação final:
  `evaluation/results/gemma4_12b_prompt_v2_full_final_review.json`
  (`3a5636758bbaf01dcc470fae6958d6004175a3246da7ae160a52d991b2126e7a`);
- revisão material `GOLD-012`:
  `evaluation/results/gemma4_12b_prompt_v2_gold012_material_review.json`
  (`0e2df88f572310793e36015352b208ea329e8ba418c355627538bde1053ee4a9`);
- scorecard:
  `evaluation/results/gemma4_12b_prompt_v2_risk_scorecard.json`
  (`48cbaa086403d52ecde10dcf0cbedbb99ddaad6e2b796ef2d1b04109f84485bd`).

### Reconsideração controlada por structured output

Após a caracterização dos quatro candidatos, foi preparado o experimento
separado `GEMMA4_FORMAT_JSON_RECONSIDERATION_V1`. Ele testa exclusivamente se o
campo nativo `format="json"` do Ollama reduz as falhas de envelope do Gemma4 sem
degradar o resultado jurídico material. O baseline cross-model, seu scorecard e
o veredito `RECONSIDER` permanecem congelados.

O runner agora aceita `--ollama-format json` de forma genérica e opt-in. Quando
a opção é omitida, o payload histórico permanece sem o campo `format`; quando é
informada, esse é o único campo adicional. Não foram implementados reparo de
JSON, stripping de Markdown, parser tolerante ou retry. Prompt, dataset,
bundles, modelo, configuração de geração, taxonomia e manifest não mudaram.

Os sete comandos manuais e os caminhos isolados dos novos artifacts estão em
`docs/evaluation/gemma4-format-json-reconsideration-v1.md`. O usuário concluiu
os sete runs, que passaram na validação de hashes e contagens. A avaliação
offline canônica obteve JSON válido em `32/32`, schema e payload em `31/32`,
decisão esperada e passe automático em `30/32`, cobertura obrigatória em
`32/32`, estabilidade formal em `12/12` e probe `GOLD-012` em `3/3`. As falhas
automáticas foram `GOLD-027`, que preservou `citations_ids` sem reparo, e
`GOLD-031`, que retornou decisão divergente. A comparação formal está concluída;
naquele checkpoint a revisão humana permanecia pendente, o HOLDOUT ficava
fechado e nenhum novo candidate verdict havia sido emitido.

A revisão humana posterior confirmou `32/32` em correção jurídica, `32/32` em
groundedness, `29/32` em completude e `29/32` all-pass. A interseção estrita
automática+humana subiu para `29/32`. O probe `GOLD-012` passou materialmente em
`3/3`, sem inversão de polaridade. O scorecard da reconsideração manteve
`RISK-01`, `RISK-02`, `RISK-03`, `RISK-04`, `RISK-06` e `RISK-08` não
observados nos respectivos casos, classificou `RISK-07` como não observado após
a correção formal e preservou `RISK-05=OBSERVED`.

Pela metodologia qualitativa congelada, a configuração `gemma4:12b` com
`ollama_format=json` recebeu `CANDIDATE_VERDICT=ACCEPT` e
`FINAL_LEGAL_ANSWERER=ACCEPTED`. O aceite pertence ao experimento pós-cross-model
e não reescreve o baseline, que continua `RECONSIDER`. Structured output
resolveu o bloqueio operacional dominante, elevou estabilidade formal para
`12/12` e não introduziu regressão material agregada. As limitações residuais
são a chave `citations_ids` de `GOLD-027`, a decisão `ABSTAIN` de `GOLD-031` e
a incompletude de clarificação registrada em `RISK-05`. O próximo gate é o
freeze explícito do modelo, configuração e runtime antes de integração RAG ou
abertura do HOLDOUT.

### Freeze do answerer selecionado

O gate seguinte foi concluído em `gold-evidence-selected-answerer/1`. A
identidade congelada combina `gemma4:12b`, seu digest exato, prompt
`gold-evidence-answering/2`, hash do prompt, configuração de geração, thinking
desabilitado, `ollama_format=json`, contrato de output fail-closed e runtime
Ollama exclusivo do Docker Compose. Não foi criado modo especial por modelo.

O artifact versionado referencia, por hash, dataset, bundles, manifest
cross-model, revisão final, scorecard, comparação final e revisão material de
`GOLD-012`. Um validador local detecta drift de identidade, configuração,
prompt, formato e artifacts sem acessar rede, banco ou inferência. Detalhes e
política de mudança estão em
`docs/evaluation/selected-answerer-freeze-v1.md`.

O baseline Gemma4 continua `RECONSIDER`; somente a configuração completa com
structured output está `ACCEPTED`. `RISK-05`, `GOLD-027` e `GOLD-031` seguem
registrados. A Fase 2 permaneceu aberta até a revisão final anterior à
integração RAG. O HOLDOUT continuou fechado e não lido.

### Encerramento da Fase 2

A revisão final confirmou todos os gates canônicos: dataset DEV e bundles
congelados, prompt v2, configuração, quatro candidatos, revisão humana,
estabilidade, probe `GOLD-012`, taxonomia de riscos, seleção, structured output,
contrato e freeze do answerer. Não há pendência metodológica bloqueante dentro
do escopo de capacidade com Gold Evidence.

A Fase 2 está `COMPLETE`. O estado `LIVE_CORPUS_STATUS=UNRESOLVED` pertence à
integração RAG e não reabre esta avaliação isolada. `RISK-05`, `GOLD-027` e
`GOLD-031` permanecem limitações conhecidas já consideradas no aceite. O próximo
bloco é `RAG_INTEGRATION_END_TO_END`; HOLDOUT continua fechado até o runtime
integrado ser implementado, avaliado em DEV e congelado.

O prompt canônico entre modelos é `gold-evidence-answering/2`, pois nele estão
congelados avaliação automática, estabilidade e revisão humana do Qwen. O v3
corrigiu por observação os prefixos de `GOLD-004` e `GOLD-014`, mas não resolveu
integralmente o contrato: em `GOLD-015`, produziu textos normativos no array de
citações em vez de stable IDs.

Cada novo candidato deve usar o mesmo dataset v1 e prompt v2, além de avaliação
automática completa, estabilidade no mesmo subconjunto de 12 casos com seeds
42/43/44, probe pós-hoc GOLD-012 nas mesmas seeds, revisão humana completa e o
mesmo scorecard de risco. Nenhum candidato será declarado vencedor antes de
concluir todos esses pilares.

| Risco | Fenômeno | Referências |
|---|---|---|
| `RISK-01` | aplicação factual prematura | `GOLD-029`, `GOLD-030`; `CONFIRMED_REPRODUCIBLE` |
| `RISK-02` | compreensão da evidência / negação e polaridade | `GOLD-012`; `CONFIRMED_REPRODUCIBLE_UNDER_PROMPT_V2`; cross-prompt `PROMPT_SENSITIVE` |
| `RISK-03` | omissão de qualificador ou exceção material | `GOLD-015`, `GOLD-018` |
| `RISK-04` | incompletude em pergunta multipartes | `GOLD-016` |
| `RISK-05` | incompletude do pedido de esclarecimento | `GOLD-027` |
| `RISK-06` | formato inválido do valor da citação | `GOLD-004`, `GOLD-014` |
| `RISK-07` | cobertura formal versus completude material | `GOLD-013` |
| `RISK-08` | variabilidade de citações compostas | `GOLD-018`, `GOLD-020` |

Não há pesos nem score agregado. Como controles de não regressão, o Qwen v2
obteve 6/6 casos materialmente corretos em evidência insuficiente, zero citações
fora da Gold Evidence, zero respostas inseguras nesses casos e 11/12 casos
`SINGLE_SUPPORT` materialmente corretos. A taxonomia `RISK-01..RISK-08` fica
congelada para a comparação cross-model. O Qwen permanece
`PARTIALLY_CAPABLE` para Gold Evidence e `REJECTED` como answerer jurídico
final. A seleção de substituto permanece pendente da execução comparável dos
quatro candidatos congelados.

### Preparação cross-model v1

Em 3 de setembro de 2026, o ambiente foi inspecionado antes de qualquer novo
Gold run. O Ollama `0.33.2` do serviço Compose `ollama` contém os quatro modelos
solicitados. O host possui Intel Core Ultra 7 255HX, 20 CPUs lógicas, 14 GiB de
RAM e 15 GiB de swap; o daemon Docker reportou 20 CPUs e 15.624.507.392 bytes de
memória, sem limites adicionais declarados no Compose.

| Ordem | Modelo | Digest | Parâmetros | Quantização | Tamanho | Contexto | Thinking |
|---:|---|---|---:|---|---:|---:|---|
| 2 | `qwen3.5:9b` | `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` | 9,7B | Q4_K_M | 6.594.474.711 B | 262.144 | nativo; `disabled` |
| 3 | `phi4-mini:3.8b-q4_K_M` | `78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753` | 3,8B | Q4_K_M | 2.491.876.774 B | 131.072 | não declarado; `auto` |
| 4 | `gemma3:4b` | `a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a` | 4,3B | Q4_K_M | 3.338.801.804 B | 131.072 | não declarado; `auto` |
| 5 | `gemma4:12b` | `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c` | 11,9B | Q4_K_M | 7.556.508.396 B | 262.144 | nativo; `disabled` |

Para modelos com capability `thinking`, o runner envia o campo nativo
`think=false`; para os demais, `auto` preserva a ausência desse campo. Essa
opção é genérica, não depende do nome do modelo e não modifica o prompt. O
default `auto` preserva o comportamento histórico. O timeout operacional ficou
congelado em 180 segundos por geração.

O manifest imutável antes do primeiro run está em
`evaluation/runs/gold_evidence_cross_model_manifest_v1.json`, com SHA-256
`f9f57938f4ffd6b29e4bd1eab2922aada847e5d344a4ad9c6451e21d97910639`.
Ele congela identidades dos modelos, hardware, inputs, configuração, ordem,
thinking, timeout, rubrica e taxonomia. Os três bundles e o dataset conferiram
com seus hashes esperados e não foram regenerados.

O runbook completo, copiável e na ordem Qwen3.5 → Phi-4-mini → Gemma3 →
Gemma4 está em
`docs/evaluation/cross-model-gold-evidence-runbook-v1.md`. Ele cobre full run,
avaliação automática, três seeds de estabilidade, summary, três probes
GOLD-012, validações e consolidação da revisão humana. Não há early stop após o
primeiro eventual `ACCEPT`; os quatro candidatos permanecem planejados.

O runner passou a expor `--thinking-mode auto|disabled`, registrar esse regime
e o timeout no metadata e limitar a espera a 180 segundos. O validador passou a
aceitar `--case-id` e `--prompt-version`, de forma genérica, para validar o probe
sem confundi-lo com o subset histórico de estabilidade. Prompt, dataset,
evaluator, rubrica e resultados históricos não mudaram.

```text
CROSS_MODEL_PREPARATION: COMPLETE
MODEL_ORDER_FROZEN: YES
ALL_FOUR_CANDIDATES_PLANNED: YES
EARLY_STOP_AFTER_FIRST_ACCEPT: NO
REAL_LLM_INFERENCE_BY_CODEX: NO
MODEL_2_SELECTION: FOUR_CANDIDATES_FROZEN_PENDING_USER_RUNS
```
