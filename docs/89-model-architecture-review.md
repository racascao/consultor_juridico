# Fase 89 — Model Architecture Review

## 1. Decisão executiva

Esta revisão aprova **cross-encoder** como a arquitetura principal para a tarefa
isolada `Query ↔ Verified/Core Assertion relevance`. A primeira escolha para um
benchmark futuro é
[`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1),
com
[`BAAI/bge-reranker-v2-m3`](https://huggingface.co/BAAI/bge-reranker-v2-m3)
como único controle discriminativo. O Granite 3B já medido permanece apenas como
controle histórico de LLM.

Esta decisão **não autoriza implementação, download, benchmark ou integração**.
Ela congela a arquitetura e o protocolo do próximo experimento.

O cross-encoder é preferido porque recebe Query e Assertion conjuntamente e
pode modelar interação entre seus tokens. Isso é uma capacidade diferente da
similaridade geométrica do bi-encoder atual. Ainda não há evidência de que um
modelo concreto satisfaça o gate jurídico: modelos de reranking treinados em IR
podem confundir “mesmo tema” com “responde à pergunta”. Por isso, o potencial é
classificado como `MEDIUM` até o benchmark adversarial.

## 2. Estado factual e baseline

O checkpoint estava commitado, na branch `main`, e o working tree estava limpo
antes desta documentação. Os oito commits mais recentes começavam em
`dd0048f`, seguido de `dea3ba7`, `dd36bd2`, `56c248b`, `3d8ce68`, `68c3991`,
`eacc736` e `4f13fca`.

Estado congelado usado nesta decisão:

- produto: `7/10`, `unsafe=0`;
- Evidence-Bound: provenance e binding válidos, mas duas respostas off-target;
- política lexical da Fase 86: eliminou off-target, mas bloqueou prisão perpétua;
- VCSA: pena de morte recuperada; prisão perpétua estruturalmente verificada,
  porém bloqueada por relevância; estado de sítio em abstenção segura;
- bi-encoder `nomic-embed-text`: `max_negative=0.811347` acima de
  `min_positive=0.757939`, portanto sem threshold seguro;
- Granite 3B: reconheceu pares reais, mas aceitou sete controles off-target e
  marcou um par relevante como irrelevante;
- potencial aritmético: `9/10`, sem fronteira de segurança aprovada.

Nenhum modelo foi baixado e nenhum benchmark foi executado nesta revisão.

## 3. CURRENT_FAILURE_ANALYSIS

### 3.1 Lexical

A regra lexical é auditável e barata, mas não representa paráfrases ou relações
morfológicas gerais. Ela não conecta de forma segura “prisão perpétua” a
“penas de caráter perpétuo”. Ampliar listas ou regras locais repetiria o padrão
de tuning por caso e não resolveria papéis jurídicos incorretos.

### 3.2 Bi-encoder

O bi-encoder calcula as representações separadamente e reduz a decisão a uma
medida global. Na amostra congelada, pares tematicamente próximos e incorretos
receberam score maior do que pares válidos. Isso confirma o limite do sinal
`nomic-embed-text + cosine` **para esta tarefa**, não um limite universal de todo
bi-encoder.

### 3.3 Granite 3B

O judge generativo entendeu as relações reais, mas falhou justamente na
fronteira de segurança: `TRUE_BUT_IRRELEVANT`, ator jurídico errado e dispositivo
relacionado que não responde. A falha confirma o limite do Granite 3B no
contrato testado. Não prova que todo modelo pequeno seja incapaz.

### 3.4 Diagnóstico comum

Os três mecanismos falham por razões distintas, mas deixam a mesma lacuna:
avaliar a relação do **par completo**, incluindo a proposição pedida, ator,
predicado, objeto, modalidade e qualificadores, sem gerar uma resposta.

## 4. TASK_DEFINITION

### 4.1 Entrada

- `query`: pergunta original do usuário;
- `core_assertion`: afirmação literal e verificável, produzida por VCSA;
- opcionalmente, apenas metadados estruturais já verificados do SupportSlot
  quando um experimento pré-declarado demonstrar necessidade.

Não entram expected answer/provision, `case_id`, artigo esperado, label do
dataset nem resposta de referência.

### 4.2 Pergunta única

> A assertion responde materialmente à proposição principal solicitada pela
> query?

Não cabe a este componente validar citation, provenance, suporte da evidência,
polaridade, preservação de qualificadores ou completude jurídica global.

### 4.3 Saída

O modelo fornece score contínuo. Uma camada determinística, calibrada e
congelada posteriormente, traduz o score em:

- `RELEVANT`, acima de `HIGH_THRESHOLD`;
- `IRRELEVANT`, abaixo de `LOW_THRESHOLD`;
- `UNRESOLVED`, entre os thresholds.

O classifier nunca altera texto, escolhe evidência, corrige retrieval ou
promove uma assertion não verificada.

## 5. ARCHITECTURE_COMPARISON

| Arquitetura | Adequação | Vantagens | Limites | Decisão |
|---|---|---|---|---|
| Cross-encoder/reranker | Alta | Codificação conjunta; score direto; barato em lote pequeno; determinístico em inferência | Domain shift de IR geral para relevância jurídica; exige runtime novo | Principal |
| NLI | Parcial | Classes entailment/neutral/contradiction; boa auditabilidade | Query não é hipótese; conversão determinística pode perder intenção ou criar outra camada semântica | Não benchmarkar agora |
| Small LLM alternativo | Baixa como próximo passo | Contrato em linguagem natural; flexível | Generativo, lento e já demonstrou fronteira instável; novo modelo não isola arquitetura | Somente Granite 3B histórico |
| LLM maior | Não justificada agora | Capacidade potencialmente maior | Mais RAM/latência; pode mascarar desenho ruim e não garante zero false relevant | Último recurso |
| Classificador pairwise próprio | Potencial futuro alto | Alinhamento exato à tarefa | Exige dataset rotulado suficiente e governança de treino inexistentes hoje | Adiar |

### 5.1 Cross-encoder versus bi-encoder

Sim, são capacidades diferentes. O cross-encoder tokeniza o par e deixa a rede
observar interações entre palavras da pergunta e da assertion. Isso pode
distinguir sujeito, papel e predicado, em vez de comparar apenas vetores globais.
É a melhor hipótese arquitetural para separar `SAME_TOPIC` de `ANSWERS_QUERY`,
mas o resultado precisa ser demonstrado.

### 5.2 NLI

NLI tradicional julga uma hipótese declarativa à luz de uma premissa. Uma query
interrogativa não é essa hipótese. Transformar “Quem decreta X?” em uma ou mais
proposições exigiria conhecer ou extrair o slot de resposta; uma conversão
frágil transferiria o problema para um parser semântico novo. NLI pode se tornar
útil depois, para relações entre duas proposições já declarativas, mas não é a
primeira escolha para o boundary atual.

### 5.3 LLMs

Outro LLM de 2B–4B mudaria simultaneamente treinamento e comportamento
generativo, sem isolar se o ganho veio da arquitetura. O Granite 3B existente é
controle suficiente. Modelo maior somente se os dois discriminativos falharem e
uma revisão justificar explicitamente o custo.

## 6. MODEL_CANDIDATES

As especificações abaixo vêm das model cards e configurações oficiais. RAM e
latência são **estimativas de planejamento**, não medições deste projeto.

| Rank | Model | Arquitetura / parâmetros | Português | Licença | CPU / latência esperada | Dependências novas | Potencial de segurança | Recomendação |
|---:|---|---|---|---|---|---|---|---|
| 1 | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | XLM-R MiniLM, sequence classification, ~118M | Explícito no mMARCO multilíngue; treino traduzido exige validação jurídica | Apache-2.0 | Alto; dezenas a centenas de ms por pequeno lote é hipótese a medir | tokenizer + ONNX Runtime ou Transformers/PyTorch | Médio/alto, sujeito ao gate adversarial | Primary |
| 2 | `BAAI/bge-reranker-v2-m3` | XLM-R cross-encoder, ~568M | Multilíngue; português precisa ser comprovado no corpus | Apache-2.0 | Aceitável a arriscado; centenas de ms a poucos segundos por lote é hipótese | FlagEmbedding/Transformers/PyTorch; ONNX exigiria caminho validado | Potencialmente maior, com custo superior | Control |
| 3 | `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` | mDeBERTa NLI, ~279M | Transferência multilíngue; português não aparece no conjunto XNLI listado | MIT | Aceitável; ONNX quantizado publicado, mas tarefa exige transformação | tokenizer + ONNX Runtime ou Transformers | Incerto pela inadequação Query→NLI | Não levar ao próximo benchmark |

### 6.1 Ficha — primary

- `MODEL_ID`: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- `TASK`: reranking/query-passage relevance
- `ARCHITECTURE`: XLM-R MiniLM sequence classifier, 12 camadas, hidden 384
- `PARAMETERS`: aproximadamente 118 milhões
- `LANGUAGES`: 14 no treinamento mMARCO, incluindo português
- `PORTUGUESE_SUPPORT`: explícito, mas proveniente de tradução automática
- `LICENSE`: Apache-2.0
- `RAM_ESTIMATE`: ~0,47 GB de pesos FP32; ~0,12 GB de pesos INT8; RSS de
  aproximadamente 0,4–1,2 GB conforme runtime e batch
- `CPU_EXPECTATION`: adequada para poucos pares; medir warm-up, batch e p95
- `MAX_SEQUENCE`: 514 posições na configuração
- `DEPENDENCIES`: runtime ONNX e tokenizer, ou stack Transformers/PyTorch
- `QUANTIZATION_OR_ONNX`: artefatos ONNX/OpenVINO, inclusive quantizados,
  publicados no repositório
- `OFFLINE_CAPABLE`: sim, após provisionamento explícito
- `AUDITABILITY`: score por par, versão/hash do modelo e thresholds congeláveis
- `RELEVANCE_FOR_PROJECT`: melhor compromisso inicial de CPU, português e tarefa

### 6.2 Ficha — control

- `MODEL_ID`: `BAAI/bge-reranker-v2-m3`
- `TASK`: reranking multilíngue
- `ARCHITECTURE`: XLM-R sequence classifier, 24 camadas, hidden 1024
- `PARAMETERS`: aproximadamente 568 milhões
- `LANGUAGES`: multilíngue
- `PORTUGUESE_SUPPORT`: provável, mas deve passar o mesmo gate português
- `LICENSE`: Apache-2.0
- `RAM_ESTIMATE`: ~2,27 GB de pesos FP32; RSS planejado ~3–5 GB; quantização
  futura reduziria peso, mas não está aprovada
- `CPU_EXPECTATION`: viável como controle em lote pequeno, com risco de latência
- `MAX_SEQUENCE`: configuração suporta até 8194, embora a model card exemplifique
  `max_length=512`; o benchmark deve congelar 512
- `DEPENDENCIES`: Transformers/PyTorch ou FlagEmbedding; ONNX demandaria caminho
  de exportação/validação separado
- `QUANTIZATION_OR_ONNX`: não assumir artefato oficial equivalente ao primary
- `OFFLINE_CAPABLE`: sim
- `AUDITABILITY`: score por par e configuração congelável
- `RELEVANCE_FOR_PROJECT`: controle de capacidade para separar falha do MiniLM de
  limite da arquitetura

### 6.3 Ficha — NLI não selecionado

- `MODEL_ID`: `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`
- `TASK`: NLI zero-shot multilíngue
- `ARCHITECTURE`: mDeBERTa-v3-base sequence classifier
- `PARAMETERS`: aproximadamente 279 milhões
- `LANGUAGES`: transferência declarada para 100 idiomas; XNLI de treino não
  lista português
- `PORTUGUESE_SUPPORT`: risco
- `LICENSE`: MIT
- `RAM_ESTIMATE`: ~0,56 GB em FP16; menor em ONNX quantizado, além do runtime
- `CPU_EXPECTATION`: aceitável em lote pequeno
- `MAX_SEQUENCE`: 512
- `DEPENDENCIES`: tokenizer + ONNX Runtime ou Transformers/PyTorch
- `QUANTIZATION_OR_ONNX`: ONNX quantizado publicado
- `OFFLINE_CAPABLE`: sim
- `AUDITABILITY`: classes claras, mas dependentes da transformação da query
- `RELEVANCE_FOR_PROJECT`: baixo como próxima experiência; tarefa desalinhada

## 7. DEPENDENCY_AND_CPU_ANALYSIS

O projeto não possui `torch`, `transformers`, `sentence-transformers`,
`optimum` ou `onnxruntime`. Portanto, qualquer candidato exige dependência nova.
Ollama não é o runtime adequado para sequence classifiers/rerankers neste
desenho e não deve ser forçado a esse papel.

O caminho recomendado para o primary é inferência CPU via **ONNX Runtime**, com
tokenização compatível e artefato versionado. A opção reduz peso operacional em
relação a PyTorch/Sentence Transformers. A futura fase deverá decidir o pacote
mínimo após um spike isolado; esta revisão não autoriza sua adição.

O desenho atual seleciona no máximo três EvidenceItems. Assim, VCSA produziria
tipicamente de zero a três Core Assertions por consulta, e o classifier avaliaria
no máximo três pares, preferencialmente em um batch. Não há justificativa para
comparar centenas de chunks nem reexecutar retrieval.

Metas operacionais propostas para o benchmark, subordinadas à segurança:

- primary: p95 aquecido por consulta (até três pares) ≤ 2 s em CPU de referência;
- control: p95 aquecido ≤ 5 s;
- primary: RSS incremental desejável ≤ 2 GB;
- determinismo de labels e scores dentro de tolerância numérica declarada;
- registrar cold start separadamente, sem escondê-lo na média.

Essas são metas de aceite experimental, não promessas de performance.

## 8. FUTURE_BENCHMARK_DESIGN

### 8.1 Matriz máxima

- primary: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`;
- control: `BAAI/bge-reranker-v2-m3`;
- controle histórico, sem nova matriz de tuning: Granite 3B;
- máximo de modelos discriminativos: **2**.

Não incluir NLI, outro LLM ou modelo maior nessa rodada.

### 8.2 Dataset congelado

Usar os positivos já congelados, os controles históricos e as classes:

- `TRUE_BUT_IRRELEVANT`;
- `SUPPORTED_BUT_OFF_TARGET`;
- `WRONG_LEGAL_ACTOR`;
- `RELATED_PROVISION_WRONG_ANSWER`;
- `AUXILIARY_FACT_WITHOUT_CORE_ANSWER`;
- `PARTIAL_TRUE_ANSWER_TO_BINARY_QUERY`;
- `THEMATICALLY_SIMILAR_BUT_WRONG_RELATION`;
- `CORRECT_TOPIC_WRONG_NORMATIVE_ROLE`;
- `SEMANTICALLY_CLOSE_BUT_IRRELEVANT`;
- `VALID_PARAPHRASE`;
- `MORPHOLOGICAL_VARIATION`;
- `VALID_ALTERNATIVE_WORDING`.

Exemplos adicionais gerais só podem ser escritos e rotulados antes de qualquer
score. `real_world_short_v1` permanece inalterado. Prisão perpétua e pena de
morte são targets de recuperação. Estado de sítio entra somente como controle
negativo lateral, não como target de retrieval.

### 8.3 Calibração sem overfit

1. Congelar dados, labels, versão/hash de modelo, tokenizer e preprocessing.
2. Separar um conjunto de calibração geral de um holdout adversarial antes da
   inferência; os casos-alvo permanecem no holdout.
3. Escolher `HIGH_THRESHOLD` impondo zero `FALSE_RELEVANT` na calibração.
4. Escolher `LOW_THRESHOLD` de modo conservador; scores intermediários tornam-se
   `UNRESOLVED`, nunca são promovidos.
5. Congelar ambos antes de abrir os resultados do holdout.
6. Executar uma única avaliação final e publicar todos os scores, inclusive os
   erros e margens.

Com dataset pequeno, os thresholds são gates regressivos, não estimativas
estatísticas de qualidade geral. Se a calibração não produzir margem estável,
o candidato falha.

### 8.4 Gate congelado proposto

Qualidade e segurança:

- prisão perpétua: `RELEVANT`;
- pena de morte: `RELEVANT`;
- assertions laterais de estado de sítio: `IRRELEVANT` ou `UNRESOLVED`;
- `FALSE_RELEVANT=0` em todos os controles adversariais;
- regressões dos sete pares históricos corretos: `0`;
- `TRUE_BUT_IRRELEVANT`, `WRONG_LEGAL_ACTOR` e
  `RELATED_PROVISION_WRONG_ANSWER`: todos passam;
- `UNSAFE_PRODUCT_ANSWERS=0`;
- VCSA/provenance/qualifier hashes permanecem inalterados;
- resultado determinístico em cinco repetições e invariável a batch order.

Produto, somente depois do gate isolado:

- potencial real-world de pelo menos `9/10`;
- estado de sítio pode permanecer em abstenção segura;
- nenhuma integração automática em produção: exige revisão humana do benchmark.

Performance:

- cumprir as metas CPU/RAM da seção anterior ou justificar desvio sem comprometer
  o uso local.

### 8.5 Critério de abandono

Se primary e control não separarem os adversariais sem `FALSE_RELEVANT`, não
testar uma sequência de modelos ou thresholds. Classificar
`DISCRIMINATIVE_RELEVANCE_LIMIT` e voltar à revisão de representação normativa,
dataset supervisionado próprio ou capacidade semântica maior.

## 9. WORKTREE_ARCHITECTURE_DECISIONS

| Componente | Decisão | Motivo |
|---|---|---|
| SupportSlot | `KEEP_FOUNDATION` | Unidade pequena, provenance e escopo verificáveis |
| Parent provenance | `KEEP_FOUNDATION` | Necessária para reconstrução e auditoria |
| Qualifier preservation | `KEEP_FOUNDATION` | Evita resposta materialmente incompleta |
| VCSA | `KEEP_FOUNDATION` | Fonte determinística da Core Assertion; não decide relevância |
| Evidence-Bound Generator | `KEEP_EXPERIMENTAL` | Pode cobrir slots sem VCSA, mas produziu off-target |
| Marginal selection | `KEEP_FOUNDATION` | Cobertura determinística sem ampliar EvidenceSet |
| Clause attribution | `LEGACY_ONLY` | Útil ao pipeline legado; VCSA reduz a necessidade no novo núcleo |
| Answer Relevance/Core Policy | `REWORK` | Boundary conceitual correto, mecanismo lexical insuficiente |
| Semantic adaptations | `KEEP_FOUNDATION` | Continuam validando suporte; não devem decidir answer relevance |
| Evaluation harness | `REWORK` | Deve separar calibração, holdout, scores, latência e hashes |

Arquitetura híbrida provável, ainda não aprovada para produção:

```text
SupportSlot
    ↓
VCSA (quando estruturalmente possível)
    ↓
Verified Core Assertion
    ↓
Cross-Encoder Query/Core Relevance
    ↓
Core Answer Policy
    ↓
validadores existentes

slot sem VCSA
    ↓
Evidence-Bound Generator experimental
    ↓
mesmo relevance boundary e mesmos validadores
```

## 10. Respostas às questões obrigatórias

1. **Sim.** Cross-encoder é adequado porque decide sobre o par completo.
2. **Sim.** Ele modela interação conjunta, não apenas distância entre vetores.
3. **Sim, com potencial real, não comprovado.** O gate adversarial decidirá.
4. **NLI não é a primeira escolha.** A query exigiria transformação artificial.
5. **Somente Granite 3B como controle histórico.** Não testar outro small LLM.
6. **Não.** Modelo maior é último recurso após os discriminativos.
7. **Cross-encoder MiniLM** oferece a melhor relação segurança/custo candidata.
8. **Cross-encoder** tem a melhor chance, pela interação entre o par.
9. **`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`.**
10. **`BAAI/bge-reranker-v2-m3`.**
11. O primary possui português explícito, mas traduzido; o control é
    multilíngue. Ambos exigem validação jurídica, logo o estado é `RISK`.
12. Ambos usam **Apache-2.0**; o NLI listado usa **MIT**.
13. Primary: sim. Control: aceitável com risco de latência/RAM.
14. Planejamento: primary ~0,4–1,2 GB de RSS; control ~3–5 GB em FP32.
15. ONNX Runtime + tokenizer para o primary; stack maior para o control.
16. **Sim.** ONNX faz sentido, sobretudo porque o primary publica artefatos.
17. **Sim.** Score com zona `UNRESOLVED` preserva fail-closed.
18. Separar calibração/holdout antes dos scores e congelar thresholds com zero
    false relevant na calibração.
19. **Dois** modelos discriminativos.
20. **Dois** é o limite; Granite é somente referência histórica.
21. **Sim**, como controle já medido, sem nova busca de LLMs.
22. Abandonar cosine como **decisor final de relevance**; embeddings continuam
    válidos para retrieval.
23. **Sim.** VCSA permanece a fonte da assertion verificável.
24. **Provavelmente como fallback experimental** para slots sem VCSA, nunca como
    autoridade ou atalho do boundary.
25. Como target, sim; incluir apenas assertions laterais como controles negativos.
26. **Sim.** `9/10` com `unsafe=0` continua adequado.
27. Um classificador pairwise treinado no domínio seria melhor em tese, mas não
    há dataset suficiente; é evolução futura do mesmo desenho.
28. **Domain/task shift:** reranker de IR aceitar conteúdo tematicamente próximo.
29. **Sim**, se e somente se o benchmark isolado passar; a capacidade não existe
    no stack atual.
30. **Sim.** Prosseguir para benchmark controlado, sem integração automática.

## 11. Riscos residuais

- suporte a português não equivale a competência jurídica brasileira;
- mMARCO é traduzido automaticamente e otimiza relevância de passagem, não
  answer adequacy jurídica;
- o BGE é significativamente maior e pode não ser confortável em CPU;
- scores de rerankers não são probabilidades calibradas;
- dataset pequeno favorece thresholds frágeis;
- quantização pode alterar margens perto dos thresholds;
- dependências de inferência ampliam superfície de manutenção e supply chain;
- um falso relevante continua mais grave do que uma abstenção.

## 12. RECOMMENDATION

Congelar **cross-encoder pairwise** como arquitetura principal e executar, em
fase posterior explicitamente autorizada, um benchmark com apenas MiniLM mMARCO
e BGE reranker. VCSA permanece imutável como fonte da Core Assertion; o novo
componente decide apenas relevance. O Granite 3B serve de baseline histórica.
Não testar NLI, outro LLM ou modelo maior na mesma rodada.

## 13. Fontes externas consultadas

- [Model card do mMARCO MiniLM cross-encoder](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1)
- [Model card do BGE reranker v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- [Model card do mDeBERTa MNLI/XNLI](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli)
- [Documentação de CrossEncoder do Sentence Transformers](https://sbert.net/docs/package_reference/cross_encoder/cross_encoder.html)

MODEL_ARCHITECTURE_REVIEW:
APPROVED

PRIMARY_ARCHITECTURE:
CROSS_ENCODER

PRIMARY_CANDIDATE:
cross-encoder/mmarco-mMiniLMv2-L12-H384-v1

CONTROL_CANDIDATE:
BAAI/bge-reranker-v2-m3

LLM_CONTROL:
GRANITE_3B

GRANITE_3B_RELEVANCE_LIMIT:
CONFIRMED

BI_ENCODER_RELEVANCE_LIMIT:
CONFIRMED

SMALL_DISCRIMINATIVE_MODEL_POTENTIAL:
MEDIUM

PROJECT_MODEL_CAPABILITY_LIMIT:
NOT_CONFIRMED

PORTUGUESE_SUPPORT:
RISK

CPU_FEASIBILITY:
HIGH

NEW_DEPENDENCY_REQUIRED:
YES

RECOMMENDED_RUNTIME:
ONNX Runtime CPU com tokenizer compatível e artefato versionado

RELEVANCE_OUTPUT:
SCORE_WITH_UNRESOLVED_ZONE

MAX_MODELS_NEXT_BENCHMARK:
2

VCSA_DECISION:
KEEP_FOUNDATION

EVIDENCE_BOUND_DECISION:
KEEP_EXPERIMENTAL

STATE_OF_SIEGE_NEXT_BENCHMARK:
INCLUDE_AS_NEGATIVE_CONTROL

EXPECTED_PATH_TO_9_OF_10:
VCSA recupera pena de morte e cross-encoder libera prisão perpétua sem aceitar assertions laterais; estado de sítio permanece em abstenção segura

BIGGEST_NEXT_RISK:
Domain shift de reranking geral para answer relevance jurídica produzir false relevant

DO_NOT_DO_NEXT:
tuning por caso, matriz de LLMs, alteração de VCSA ou integração direta em produção

RECOMMENDED_NEXT_STEP:
CONTROLLED_RELEVANCE_MODEL_BENCHMARK

IMPLEMENTATION_AUTHORIZATION:
NO

COMMIT:
READY_FOR_MANUAL_COMMIT
