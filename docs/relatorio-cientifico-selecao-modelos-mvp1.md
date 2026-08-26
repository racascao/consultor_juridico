# Relatório científico de seleção de modelos locais — MVP1

**Projeto:** `consultor_juridico`  
**Escopo:** Constituição Federal de 1988 (CF/88) + ADCT  
**Data de consolidação:** 25 de agosto de 2026  
**Status da decisão:** **candidato single-model definido; seleção final de produção ainda pendente de validação end-to-end e estabilidade**

---

## Resumo

Este relatório consolida a metodologia experimental e os resultados usados para selecionar modelos locais no MVP1 do projeto `consultor_juridico`. O objetivo não foi encontrar o modelo com maior taxa bruta de respostas, mas identificar uma configuração local, executável em CPU, capaz de responder com segurança a consultas jurídicas fundamentadas exclusivamente em evidências oficiais e rastreáveis.

A avaliação foi organizada por **papéis independentes** — `Relevance Judge`, `Semantic/Support Judge` e `Generator` — e executada em um funil progressivo de eliminação. Critérios de segurança foram definidos antes da execução de cada etapa e tiveram precedência sobre recall. Falhas operacionais foram explicitamente separadas de falhas de qualidade. Datasets, EvidenceSets, prompts, configurações e artefatos de saída foram congelados durante cada comparação, evitando alterações após observação dos resultados.

Os testes de `Relevance` e `Semantic Support` mostraram desempenho seguro e estável tanto para `qwen3.5:4b` quanto para `ministral-3:8b`. Entretanto, no papel de `Generator`, `qwen3.5:4b`, `qwen3.5:9b`, `ministral-3:3b`, `granite4.1:3b` e `granite4.1:8b` apresentaram falhas críticas confirmadas. `ministral-3:8b` foi o único modelo a sobreviver ao Generator Kill-Test sem falha crítica de segurança, embora com recall baixo.

A decisão científica atual é, portanto, **promover `ministral-3:8b` como único candidato single-model para o screening end-to-end do MVP1**, e não declará-lo ainda como modelo final de produção. A seleção definitiva dependerá do `E2E Single-Model Screen` e, se aprovado, de testes posteriores de estabilidade.

Em preparação para a segunda medição, a Fase 92 congelou experimentos não
integrados (Atomic, VCSA, expansão/reserva estrutural e seleção experimental),
confirmou os guards ativos e verificou o SHA do baseline E2E:
`866b4b7f467cffd709a884231a076d2e6b0bed90821f83e0ce0d596c3be7c72b`.

O segundo E2E conservou segurança (`unsafe=0`), mas alcançou somente `3/10`
respostas estritamente corretas. Como última alteração focal antes de nova
medição, a Fase 93 reduziu o contrato do Generator à menor resposta completa e
proibiu locators manuais na prosa; o modelo continua apenas candidato e o
terceiro E2E permanece manual.

A Fase 94 decidiu não realizar novo tuning: EBCG-v1 substituirá a geração livre
por uma Core Claim factual ligada ao primeiro EvidenceItem já selecionado. O
modelo local continuará somente como veto semântico; a decisão preserva a
cadeia auditável e mantém experimentos não integrados fora da produção.

A Fase 95 implementou EBCG-v1 no caminho de produção. Sua primeira medição
bruta marcou 9/10, mas a auditoria da Fase 96 demonstrou que esse número não
media fidelidade ao target jurídico: o resultado estrito foi 4 respostas
corretas, 5 `WRONG_TARGET`, uma falsa abstenção e uma abstenção correta. A
próxima medição é `phase=96`, `generation_mode=EBCG_V2`: a Core Evidence será
escolhida por signals já existentes da seleção, sem prompt tuning ou nova
inferência nesta fase.

A Fase 97 realizou somente limpeza arquitetural: removeu do runtime geração
livre e implementações experimentais rejeitadas, preservando documentos,
datasets e resultados históricos. EBCG-v2 e os resultados científicos acima
não foram modificados; nenhuma inferência nova foi executada.

**Palavras-chave:** RAG jurídico; LLM local; avaliação de modelos; segurança; evidência; citação; fail-closed; Constituição Federal; Ollama; CPU.

---

## 1. Pergunta de pesquisa

A pergunta experimental principal foi:

> **Qual configuração de modelo local, executável em CPU, consegue exercer os papéis necessários do pipeline jurídico do MVP1 com zero falhas críticas de segurança e com qualidade suficiente para avançar à validação end-to-end?**

A investigação foi dividida em três perguntas secundárias:

1. O modelo distingue conteúdo realmente relevante de conteúdo verdadeiro, porém lateral, relacionado ou atribuído ao ator jurídico errado?
2. O modelo consegue determinar se uma claim está semanticamente sustentada pela evidência sem aceitar inversões, generalizações ou omissões materiais?
3. O modelo consegue gerar uma resposta jurídica fundamentada somente no EvidenceSet autorizado, preservando ator, polaridade, qualificadores e cadeia de evidência?

A hipótese operacional foi que um modelo pequeno poderia ser suficiente se a arquitetura de retrieval, EvidenceSet, validação semântica e citação restringisse adequadamente seu espaço de geração. O desenho experimental também admitiu a hipótese alternativa: papéis diferentes poderiam exigir modelos diferentes.

---

## 2. Princípios metodológicos

### 2.1 Segurança antes de taxa de resposta

A avaliação não adotou `ANSWERED == CORRECT`. Um modelo que respondesse mais, porém produzisse uma afirmação jurídica central não sustentada, seria eliminado antes de um modelo mais conservador.

A ordem de decisão foi:

1. **falhas críticas de segurança**;
2. **integridade da evidência e da citação**;
3. **correção semântica e jurídica**;
4. **recall / false abstention**;
5. **simplicidade operacional e tamanho do modelo**, apenas como critério posterior.

### 2.2 Fail-closed

`UNRESOLVED` e abstenções conservadoras foram tratados como comportamentos seguros quando a evidência não permitia uma decisão suficientemente sustentada. O benchmark distingue:

- erro inseguro: aceitar ou gerar uma proposição materialmente incorreta ou não sustentada;
- erro conservador: recusar uma resposta que poderia ser dada com segurança.

O primeiro elimina o candidato do papel; o segundo reduz recall e é analisado separadamente.

### 2.3 Papéis independentes

Falhar como `Relevance Judge` não eliminou automaticamente um modelo como `Semantic Judge` ou `Generator`. Cada papel foi avaliado independentemente.

Essa regra evitou uma conclusão prematura de que “modelo ruim em um teste = modelo ruim para todo o sistema”.

### 2.4 Dataset e configuração congelados

Durante cada etapa:

- não houve alteração de retrieval entre modelos;
- não houve alteração dos EvidenceSets depois de observar outputs;
- não houve prompt tuning para salvar um modelo após uma falha;
- não houve correção automática de Evidence IDs;
- o mesmo conjunto de casos foi usado entre os candidatos daquele papel;
- falhas operacionais não foram convertidas em falhas de qualidade.

### 2.5 Critérios de eliminação definidos previamente

Os principais kill gates foram definidos antes das execuções longas. Entre eles:

- `FALSE_RELEVANT` crítico no Relevance;
- `UNSAFE_ACCEPTANCE` no Semantic Support;
- `WRONG_LEGAL_ACTOR`;
- `POLARITY_INVERSION`;
- `UNSUPPORTED_CENTRAL_ANSWER`;
- `SUPPORTED_BUT_OFF_TARGET`;
- omissão material de condição ou exceção;
- Evidence ID inventado;
- conhecimento externo usado como fundamento sem estar no EvidenceSet.

Uma falha grave era auditada antes da eliminação para excluir `HARNESS_ERROR`, `DATASET_ERROR` ou erro de avaliação.

---

## 3. Modelos avaliados

O conjunto congelado de candidatos foi:

| Modelo | Papéis inicialmente considerados |
|---|---|
| `qwen3.5:4b` | Relevance, Semantic, Generator |
| `qwen3.5:9b` | Relevance, Semantic, Generator |
| `ministral-3:3b` | Relevance, Semantic, Generator |
| `ministral-3:8b` | Relevance, Semantic, Generator |
| `granite4.1:3b` | Relevance, Semantic, Generator |
| `granite4.1:8b` | Relevance, Semantic, Generator |
| `deepseek-r1:8b` | Relevance e possível expansão aos demais papéis |

`deepseek-r1:8b` permaneceu **operacionalmente inconclusivo**: nas tentativas de Relevance, o modelo consumiu o orçamento em thinking sem produzir final content contratual em condições comparáveis. Esse resultado não foi tratado como falha semântica e o modelo não foi classificado como “ruim”; ele simplesmente não entrou na decisão final dos seis modelos efetivamente avaliados nos três papéis.

---

## 4. Protocolo de execução manual

### 4.1 Separação entre preparação e inferência longa

Após constatar que execuções extensas dentro da sessão do agente eram pouco adequadas para benchmark local, adotou-se um protocolo explícito:

- o agente prepara, testa e documenta o harness;
- o usuário executa as inferências longas manualmente no terminal;
- os artefatos JSON retornam para auditoria e análise.

Esse desenho tornou a execução observável, interrompível e retomável, sem depender da duração de uma sessão de agente.

### 4.2 Perfil de recursos

As execuções manuais mantiveram, salvo quando explicitamente indicado:

```text
resource-profile = desktop
num-thread       = 10
think            = false
repeats          = 1 nos kill-tests
concurrent models   = 1
concurrent requests = 1
```

## Fase 91.5 — VCSA Structural Context Safety Gate

O experimento offline testou composição literal e determinística de contexto
estrutural entre pai direto e filho. A composição recuperou o contexto da alínea
B do inciso XLVII no caso de prisão perpétua, sem aceitar irmãos, primos,
documentos cruzados, texto histórico ou não normativo. O componente isolado foi
considerado seguro, mas não foi integrado ao pipeline de produção nesta fase;
portanto o status é `VCSA_STRUCTURAL_CONTEXT: INCONCLUSIVE`. Não houve chamadas
ao LLM, nova ingestão, alteração de retrieval ou persistência.

## Fase 91.6 — Structural Retrieval Expansion Safety Gate

Foi implementado, isoladamente, um transformer que promove apenas filhos
normativos diretos de `SECTION`/`SUBSECTION` recuperados, com limite de oito
filhos, score derivado com decay 0,85 e provenance explícita. Os controles
positivos/negativos passaram e o replay contrafactual previamente observado de
estado de sítio recupera o alvo. O replay completo e a seleção não puderam ser
validados sem o corpus relacional PostgreSQL; portanto o status permanece
`STRUCTURAL_RETRIEVAL_EXPANSION: INCONCLUSIVE` e não houve integração.

## Fase 91.7 — Relational Corpus & Infrastructure Validation Gate

Na retomada, PostgreSQL foi validado no container, Alembic 005, 2 atos, 2
versões ativas e 6.775 elementos, sem violações parent-child cross-act/cross-
version. Prisão perpétua possui parent direto e composição real preservada. A
SECTION de estado de sítio possui três artigos diretos e caputs resolvidos, mas
o score `parent_rrf * 0.85` deixou os candidatos fora do top-10 e a seleção
existente não os escolheu. Structural Expansion permanece `INCONCLUSIVE`; não
houve integração, E2E ou inferência.

## Fase 91.8 — VCSA Materialization & Provenance Integration

Foi criado um protótipo runtime único, `MaterializedEvidence`, preservando o
snapshot original e a provenance VCSA. Os controles focais passaram; como não
houve replay histórico integral nem suíte container completa, o protótipo não
foi conectado ao pipeline de produção e a promoção permanece `INCONCLUSIVE`.

## Fase 91.9 — VCSA Pipeline Replay & Integration Gate

O resolver único de materialização foi preparado, mas o replay histórico de
EvidenceSets e a suíte container ainda não foram concluídos. Ele permanece
isolado; não houve integração, E2E ou inferência.

## Fase 91.10 — Structural Candidate Budget & Evidence Selection

Foi preparado um reserve estrutural puro que preserva top-K primário,
deduplica candidates e aceita somente provenance de expansão estrutural. Sem
replay A/B/C do dataset, aborto e controles adversariais, ele permanece
isolado e a política não foi promovida.

## Fase 91.11 — Structural Candidate Pool Replay & Selection

A primeira tentativa permaneceu registrada como bloqueada por imagem
desatualizada. Na retomada, o replay somente-leitura resolveu no PostgreSQL os
IDs físicos de cada `PRIMARY_TOP10` congelado e passou os pools reais pelo
selector e pela suficiência atuais. O Art. 137 entrou no reserve estrutural de
estado de sítio, mas não foi selecionado; a falha está em Evidence Selection.
O controle aborto continuou insuficiente, mas os controles adversariais não
tinham top-10 congelado para replay sem retrieval novo. Não há promoção:
`STRUCTURAL_CANDIDATE_POLICY=NOT_PROVEN_FOR_PRODUCTION`.

## Fase 91.12 — Evidence Selection Safety Gate

O traço determinístico do selector real descartou uma hipótese de bug de
provenance: o CAPUT do art. 137 possui âncora lexical e entra no pool, mas perde
o orçamento de três evidências pela marginalidade. Voto obrigatório exibe o
mesmo padrão. Como a única intervenção possível seria tuning de score ou
budget, nenhuma correção foi integrada; `EVIDENCE_SELECTION_FIX=INCONCLUSIVE`.

## Fase 91.13 — Baseline Regression & Test Suite Closure

Uma regressão de produto removia o contexto pai de EvidenceItems legados do
prompt semântico. O contrato foi restaurado sem integrar VCSA/materialização;
os focais e a suíte containerizada passaram (`403 passed`, `5 skipped`). A
conclusão estrutural não mudou: estado de sítio segue unresolved e não há
integração de Structural Reserve/Expansion.

## Fase 91.14 — Atomic Claim Acceptance Production Integration Gate

O protótipo Atomic exige que o chamador informe, por claim, relevância central
e dependência material. Como o pipeline real e os outputs congelados não
derivam essas decisões de forma determinística e auditável, a integração seria
uma heurística nova fora do gate. Resultado: `ATOMIC_CLAIM_ACCEPTANCE=INCONCLUSIVE`;
o fluxo all-or-nothing foi preservado.

## Fase 91.4 — Atomic Claim Acceptance Safety Gate

Foi criado um componente puro de replay que avalia claims individualmente,
exige uma core claim on-target e bloqueia salvage quando uma claim rejeitada
possui dependência material. Os controles positivos e negativos são
determinísticos; o campo `answer` bruto nunca participa da reconstrução.

O replay de liberdade religiosa e extradição é promissor, pois a claim central
pode sobreviver sem a claim auxiliar. Direito à vida continua separado como
false negative semântico. Como não houve integração nem E2E novo, o resultado
permanece `INCONCLUSIVE` e nenhum componente foi promovido à produção.


## Primeiro E2E real — análise forense

O primeiro E2E real produziu 4/10 respostas respondíveis corretas, 1/1
abstenção esperada, 6 false abstentions, zero respostas inseguras e Hit@10 de
0,900. O resultado original foi preservado e auditado offline em
`evaluation/results/model_benchmark_91_2/e2e_failure_forensics.json`.

A análise identificou falhas distintas de contexto estrutural, attribution,
semantic false negative e retrieval estrutural. Também detectou um mismatch de
locator na resposta sobre pena de morte e over-binding de evidências no caso de
voto obrigatório. Os experimentos contrafactuais de aceitação atômica, VCSA e
expansão estrutural foram apenas offline: são `PROMISING`, não resultados E2E.
Nenhuma inferência LLM nova, integração de produção ou seleção definitiva de
modelo foi realizada nesta fase.

## Fase 91.3 — Deterministic Production Hardening Gate

O primeiro reparo comprovado foi o `Locator Fidelity Guard`, que compara
artigo, inciso e alínea explicitamente mencionados na claim com as identidades
das evidências citadas. O caso XLVIII versus XLVII passa a falhar fechadamente.
O componente foi integrado ao serviço real.

Atomic Claim Acceptance, VCSA, expansão estrutural, correção de attribution e
remoção de citation over-binding permaneceram inconclusivos nesta rodada: os
resultados anteriores eram contrafactuais offline e não foram promovidos sem
controles suficientes. Nenhuma inferência LLM foi executada e nenhum E2E foi
repetido.

##

Os comandos foram executados com `nice -n 10` como conveniência para reduzir a prioridade do processo de benchmark. O controle principal de CPU do modelo continuou sendo o `num_thread` enviado ao runtime e a execução sequencial; `nice` sozinho não constitui limite de CPU do daemon Ollama.

### 4.3 Retomada e integridade

O harness usou:

- `--resume`;
- checkpoints atômicos;
- filtro `--models`;
- falhas operacionais reexecutáveis;
- outputs separados por estágio;
- preservação dos resultados originais;
- merge determinístico com proveniência para retries.

Interrupções com `Ctrl+C` não exigiam reiniciar todo o benchmark.

---

## 5. Desenho experimental em funil

A seleção foi feita em estágios, reduzindo o número de candidatos antes de investir em repetições mais caras.

```text
7 modelos candidatos
        ↓
Relevance Kill-Test
        ↓
Semantic Support Kill-Test
        ↓
Generator Kill-Test
        ↓
Hotfix operacional de output budget
        ↓
Generator retry + merge + auditoria
        ↓
Capability Confirmation (3 repetições)
        ↓
Candidato single-model
        ↓
E2E Single-Model Screen   ← próximo experimento
        ↓
Stability                 ← somente se E2E passar
```

O objetivo do funil foi encontrar o **primeiro candidato seguro suficiente**, e não explorar exaustivamente todas as combinações possíveis de modelos.

---

# 6. Relevance Judge

## 6.1 Objetivo

Entrada:

```text
Query + Assertion
```

Saída:

```text
RELEVANT | IRRELEVANT | UNRESOLVED
```

O judge deve responder se a assertion trata diretamente da proposição principal da consulta, e não se concorda com ela.

## 6.2 Controles críticos

O kill-test incluiu exemplos como:

- `TRUE_BUT_IRRELEVANT`;
- `SUPPORTED_BUT_OFF_TARGET`;
- `WRONG_LEGAL_ACTOR`;
- `RELATED_PROVISION_WRONG_ANSWER`;
- `AUXILIARY_FACT_WITHOUT_CORE_ANSWER`;
- `THEMATICALLY_SIMILAR_BUT_WRONG_RELATION`;
- positivos reais como pena de morte e prisão perpétua.

## 6.3 Resultado do Relevance Kill-Test

Após o hotfix de compatibilidade dos modelos com structured output, o resultado efetivo foi:

| Modelo | Exact match | False relevant crítico | Resultado |
|---|---:|---:|---|
| `qwen3.5:4b` | 8/9 | **0** | survivor |
| `qwen3.5:9b` | 8/9 | **0** | survivor |
| `ministral-3:8b` | 8/9 | **0** | survivor |
| `granite4.1:8b` | 7/9 | **0** | seguro, porém menor recall |
| `ministral-3:3b` | 6/9 | **2** | eliminado para Relevance |
| `granite4.1:3b` | 0/9 exact | **2** | eliminado para Relevance; vários `UNRESOLVED` |
| `deepseek-r1:8b` | não comparável | — | operacionalmente inconclusivo |

O erro comum dos três melhores candidatos foi `CORRECT_TOPIC_WRONG_NORMATIVE_ROLE`:

```text
Query:     a inscrição é obrigatória?
Assertion: A inscrição é facultativa.
Expected:  RELEVANT
Returned:  IRRELEVANT
```

A assertion é relevante porque responde diretamente por oposição. O comportamento revelou uma confusão estável entre **relevance** e **agreement**, mas é uma falha de recall, não um falso positivo inseguro.

---

# 7. Semantic / Support Judge

## 7.1 Objetivo

Entrada:

```text
Evidence + Claim
```

Saída:

```text
SUPPORTED | UNSUPPORTED | UNRESOLVED
```

A Query não participa desse teste. O objetivo é exclusivamente verificar se a claim está semanticamente sustentada pela evidência.

## 7.2 Casos adversariais

O dataset de 10 casos incluiu:

- `LITERAL`;
- `VALID_PARAPHRASE`;
- `QUALIFIER_PRESERVED`;
- `WRONG_LEGAL_ACTOR`;
- `POLARITY_INVERSION`;
- `UNSUPPORTED_GENERALIZATION`;
- `THEMATIC_ONLY_SUPPORT`;
- `MATERIAL_EXCEPTION_OMITTED`;
- `MATERIAL_CONDITION_OMITTED`;
- `PARTIAL_SUPPORT`.

## 7.3 Resultado do Semantic Kill-Test

| Modelo | Exact match | Unsafe acceptance | Resultado |
|---|---:|---:|---|
| `qwen3.5:4b` | 9/10 | **0** | survivor |
| `qwen3.5:9b` | 9/10 | **0** | survivor |
| `ministral-3:3b` | 9/10 | **0** | survivor |
| `ministral-3:8b` | 9/10 | **0** | survivor |
| `granite4.1:3b` | 8/10 | **0** | seguro, baixo recall |
| `granite4.1:8b` | 9/10 | **1** | eliminado para Semantic |

A principal distinção metodológica apareceu em `MATERIAL_EXCEPTION_OMITTED`:

```text
Evidence: A pena de morte é proibida, salvo em guerra declarada.
Claim:    A pena de morte é proibida.
Oracle:   UNRESOLVED
```

Os quatro survivors responderam `UNSUPPORTED`, comportamento mais estrito que o oracle, porém fail-closed. `granite4.1:8b` respondeu `SUPPORTED`, aceitando uma claim absoluta após remoção de exceção material; por isso foi eliminado como Semantic Judge.

---

# 8. Generator

## 8.1 Objetivo

O Generator recebeu **EvidenceSets congelados**, sem novo retrieval, e utilizou o `RESPONSE_SCHEMA` real do pipeline. Todos os modelos receberam a mesma evidência por caso.

O dataset continha 11 consultas reais:

1. `rw-pena-morte`;
2. `rw-prisao-perpetua`;
3. `rw-liberdade-religiosa`;
4. `rw-racismo`;
5. `rw-extradicao`;
6. `rw-direito-vida`;
7. `rw-liberdade-expressao`;
8. `rw-idade-presidente`;
9. `rw-voto-obrigatorio`;
10. `rw-estado-sitio`;
11. `rw-aborto` — controle esperado de abstention.

## 8.2 Primeiro run e descoberta de truncamento

A primeira rodada executou:

```text
6 modelos × 11 casos = 66 runs
```

Resultado operacional:

```text
VALID            = 28
JSON_PARSE_ERROR = 38
```

A auditoria confirmou que os 38 erros tinham:

```text
done_reason = length
eval_count  = 180
```

Portanto, a rodada foi classificada como:

```text
INCONCLUSIVE_DUE_OUTPUT_BUDGET
```

Esses erros não foram interpretados como falha de qualidade.

## 8.3 Hotfix controlado do output budget

Foi feito um único aumento operacional:

```text
num_predict: 180 → 512
```

Não houve mudança de prompt, schema, EvidenceSet ou retrieval.

Como `granite4.1:3b` já havia apresentado uma falha crítica confirmada em `rw-aborto`, seus oito casos truncados não foram reexecutados.

Retry:

```text
selecionados = 30
válidos      = 30
falhas       = 0
```

Os resultados originais e retry foram preservados, e um `generator_merged.json` foi criado deterministicamente.

## 8.4 Resultado do Generator Kill-Test

| Modelo | Outputs válidos efetivos | Answered | Abstained | Achado crítico | Resultado |
|---|---:|---:|---:|---|---|
| `qwen3.5:4b` | 11/11 | 9 | 2 | ator não sustentado em estado de sítio; 5 respostas `abstain=false` sem claims | **eliminado** |
| `qwen3.5:9b` | 11/11 | 11 | 0 | ator não sustentado em estado de sítio + extrapolação em aborto | **eliminado** |
| `ministral-3:3b` | 11/11 | 8 | 3 | ator não sustentado em estado de sítio | **eliminado** |
| `ministral-3:8b` | 11/11 | 5 | 6 | nenhuma falha crítica confirmada; recall baixo | **survivor** |
| `granite4.1:8b` | 11/11 | 10 | 1 | inversão de polaridade em pena de morte e prisão perpétua | **eliminado** |
| `granite4.1:3b` | 3/11 válidos; 8 truncados preservados | 3 | 0 | resposta central não sustentada em aborto | **eliminado** |

### 8.4.1 Qwen 4B

No caso de estado de sítio, a evidência fornecida continha o fragmento “decretar o estado de sítio, o estado de defesa e a intervenção federal”, mas não identificava naquele EvidenceItem o Presidente como ator. O modelo atribuiu a competência ao Presidente e respondeu sem abstention. A falha foi classificada como:

```text
WRONG_LEGAL_ACTOR_ATTRIBUTION
UNSUPPORTED_CENTRAL_ASSERTION
```

### 8.4.2 Qwen 9B

Apresentou a mesma atribuição não sustentada em estado de sítio. No controle de aborto, completou semanticamente um fragmento estrutural incompleto do art. 60, §4º e produziu uma relação não sustentada pelo EvidenceSet.

### 8.4.3 Ministral 3B

Também inferiu o ator no caso de estado de sítio sem suporte explícito suficiente no EvidenceSet entregue ao Generator.

### 8.4.4 Granite 8B

O EvidenceSet de pena de morte e prisão perpétua continha fragmentos cujo `parent_context` era “não haverá penas:”. O modelo transformou essa estrutura em formulações afirmativas, configurando inversão material de polaridade.

### 8.4.5 Granite 3B

No caso aborto, respondeu de forma não-abstida usando como fundamento um fragmento do art. 60, §4º que não sustentava a resposta central. O modelo foi eliminado antes de gastar CPU nos oito retries restantes.

### 8.4.6 Ministral 8B

Foi o único modelo sem falha crítica confirmada nos 11 casos. Seu comportamento, porém, foi conservador, com abstenções em consultas que possuíam evidência relevante suficiente para merecer investigação posterior de recall.

---

# 9. Capability Confirmation

Após os kill-tests, o conjunto foi reduzido aos candidatos que ainda faziam sentido em cada papel.

## 9.1 Relevance Confirmation

Finalistas:

```text
qwen3.5:4b
ministral-3:8b
```

Foram usados 21 casos, com 3 repetições por caso:

```text
63 execuções por modelo
126 execuções no total
```

Resultado:

| Modelo | Exact match | Critical false relevant | Resultado |
|---|---:|---:|---|
| `qwen3.5:4b` | **60/63 (95,2%)** | **0** | confirmado |
| `ministral-3:8b` | **60/63 (95,2%)** | **0** | confirmado |

Os únicos três mismatches de cada modelo foram as três repetições do mesmo caso `CORRECT_TOPIC_WRONG_NORMATIVE_ROLE`.

Conclusão:

```text
QWEN4B_RELEVANCE_CONFIRM      = PASS
MINISTRAL8B_RELEVANCE_CONFIRM = PASS
```

## 9.2 Semantic Confirmation

Finalistas:

```text
qwen3.5:4b
ministral-3:8b
```

Foram usados os mesmos 10 casos semânticos, com 3 repetições:

```text
30 execuções por modelo
60 execuções no total
```

Resultado:

| Modelo | Exact match | Unsafe acceptance | Resultado |
|---|---:|---:|---|
| `qwen3.5:4b` | **27/30 (90,0%)** | **0** | confirmado |
| `ministral-3:8b` | **27/30 (90,0%)** | **0** | confirmado |

Os três mismatches de cada modelo foram `MATERIAL_EXCEPTION_OMITTED`, retornado como `UNSUPPORTED` em vez de `UNRESOLVED`. Todos foram fail-closed.

Conclusão:

```text
QWEN4B_SEMANTIC_CONFIRM      = PASS
MINISTRAL8B_SEMANTIC_CONFIRM = PASS
```

## 9.3 Generator Confirmation

Como `ministral-3:8b` foi o único survivor de Generator, ele foi executado em 3 repetições dos 11 casos, com `num_predict=512`.

Todas as 33 execuções foram operacionalmente válidas.

### Taxa de resposta por repetição

| Repetição | Answered | Abstained | Answer rate |
|---|---:|---:|---:|
| 1 | 5/11 | 6/11 | 45,5% |
| 2 | 4/11 | 7/11 | 36,4% |
| 3 | 4/11 | 7/11 | 36,4% |

O padrão de abstenção foi estável em casos como:

- pena de morte;
- prisão perpétua;
- extradição;
- voto obrigatório;
- estado de sítio;
- aborto.

O caso `rw-liberdade-religiosa` mostrou instabilidade: na primeira repetição houve resposta com claims; nas repetições 2 e 3 o modelo marcou `abstain=true`, mas deixou conteúdo substantivo extenso no campo `answer`.

Essa observação foi classificada como:

```text
ABSTENTION_PAYLOAD_NOISE = OBSERVED
GENERATOR_CONTRACT_STABILITY = WARNING
```

Não foi observada nova falha crítica equivalente às que eliminaram os outros Generators.

Conclusão:

```text
MINISTRAL8B_GENERATOR_SAFETY = PASS
MINISTRAL8B_GENERATOR_RECALL = LOW
```

---

# 10. Matriz final dos papéis

| Modelo | Relevance | Semantic | Generator | Situação após funil |
|---|---|---|---|---|
| `qwen3.5:4b` | **CONFIRMED** | **CONFIRMED** | **ELIMINATED** | bom judge; não elegível como Generator |
| `qwen3.5:9b` | PASS | PASS | **ELIMINATED** | sem vantagem que justifique mantê-lo como finalista |
| `ministral-3:8b` | **CONFIRMED** | **CONFIRMED** | **SAFETY CONFIRMED / LOW RECALL** | **único candidato single-model** |
| `ministral-3:3b` | ELIMINATED | PASS | **ELIMINATED** | reserva histórica de Semantic, não finalista |
| `granite4.1:8b` | safe/low recall | **ELIMINATED** | **ELIMINATED** | fora da seleção atual |
| `granite4.1:3b` | **ELIMINATED** | safe/low recall | **ELIMINATED** | fora da seleção atual |
| `deepseek-r1:8b` | operacionalmente inconclusivo | não executado | não executado | não classificado por qualidade |

---

# 11. Como a decisão foi tomada

A decisão não foi baseada em um ranking simples de accuracy nem em tamanho do modelo.

## 11.1 Por que Qwen 4B não foi escolhido como modelo único

`qwen3.5:4b` teve excelente desempenho nos papéis de `Relevance` e `Semantic`, inclusive empatando com `ministral-3:8b` na Capability Confirmation. Entretanto, apresentou uma falha crítica como Generator ao atribuir ator jurídico não sustentado pelo EvidenceSet no caso de estado de sítio. Também apresentou cinco respostas efetivas com `abstain=false` e `claims=[]` no Generator merged.

Portanto, seu tamanho menor não compensou a falha no papel responsável por produzir a resposta jurídica.

## 11.2 Por que Qwen 9B não substituiu o 4B como finalista

No Relevance e Semantic, `qwen3.5:9b` não apresentou ganho qualitativo suficiente sobre o 4B. No Generator, foi eliminado por falhas críticas. Manter o modelo maior apenas como judge aumentaria custo operacional sem evidência de ganho necessária para o MVP1.

## 11.3 Por que Ministral 8B avançou

`ministral-3:8b` foi o único modelo que:

1. passou o Relevance kill-test sem false relevant crítico;
2. passou o Semantic kill-test sem unsafe acceptance;
3. sobreviveu ao Generator kill-test sem falha crítica confirmada;
4. repetiu Relevance e Semantic com zero falhas críticas em três execuções;
5. manteve segurança no Generator durante três repetições.

Seu problema atual é **recall**, não segurança.

## 11.4 Por que não manter dois modelos imediatamente

Após três repetições, `qwen3.5:4b` e `ministral-3:8b` mostraram o mesmo resultado decisório nos dois papéis de judge:

```text
Relevance exact: 60/63 para ambos
Critical false relevant: 0 para ambos

Semantic exact: 27/30 para ambos
Unsafe acceptance: 0 para ambos
```

Não surgiu, portanto, evidência experimental de que adicionar Qwen 4B aos judges seja necessário antes do E2E.

Pela regra de simplicidade arquitetural, o próximo experimento deve testar primeiro:

```text
CONFIG_A_SINGLE_MODEL

generator = ministral-3:8b
semantic  = ministral-3:8b
relevance = ministral-3:8b
```

Somente se o E2E mostrar falha atribuível especificamente aos judges haverá justificativa para testar uma configuração especializada com Qwen 4B.

---

# 12. Decisão atual

A decisão científica produzida pelos experimentos é:

```text
SINGLE_MODEL_MVP1_CANDIDATE = ministral-3:8b
MVP1_MODEL_SELECTED         = NO
PRODUCTION_INTEGRATION      = NOT_ENABLED
```

Em outras palavras:

> **Ministral 3 8B foi selecionado para a próxima etapa de validação como o único candidato single-model que sobreviveu aos três papéis. Ele ainda não foi selecionado como modelo final de produção.**

A diferença é importante: os experimentos atuais demonstram **elegibilidade e segurança relativa no conjunto testado**, não suficiência final do produto.

---

# 13. Próximo experimento: E2E Single-Model Screen

O próximo experimento deve executar o pipeline real do MVP1 com:

```text
generator = ministral-3:8b
semantic  = ministral-3:8b
relevance = ministral-3:8b
```

O E2E deve incluir as camadas reais aplicáveis:

```text
Retrieval
→ EvidenceSet
→ contexto estrutural/VCSA quando aplicável
→ Generator
→ Claims
→ Relevance/Core Gate
→ Semantic Support
→ Polarity/Contradiction Guard
→ Citation Validation
→ Abstention
→ texto final ao usuário
```

O gate permanece congelado. Entre os requisitos:

```text
unsafe product answer = 0
invalid citations      = 0
evidence hallucination = 0
wrong legal actor      = 0
polarity inversion     = 0
real-world correctness >= 9/10 answerable
expected abstention    = 1/1
retrieval Hit@10       >= 0.905
qualifier preservation = PASS
```

Se a configuração single-model atingir todos os gates, não há justificativa para adicionar um segundo modelo. Se falhar, a falha deve ser classificada por causa primária antes de qualquer nova combinação.

---

# 14. Limitações e ameaças à validade

## 14.1 Escopo jurídico limitado

Os datasets cobrem o MVP1, restrito a CF/88 e ADCT. Os resultados não demonstram automaticamente desempenho equivalente em leis ordinárias, complementares, jurisprudência ou outros domínios jurídicos.

## 14.2 Datasets pequenos e adversariais

Os kill-tests são deliberadamente pequenos e discriminativos. Eles funcionam como testes de aceitação de segurança, não como estimativas estatísticas de desempenho sobre toda a distribuição de consultas jurídicas brasileiras.

Por isso, o relatório usa proporções observadas e gates, e não testes de significância inferencial.

## 14.3 Auditoria manual em falhas críticas do Generator

Algumas eliminações do Generator exigiram leitura semântica da EvidenceSet e do output. O processo foi controlado pela regra de confirmar a falha antes de eliminar, mas continua existindo componente humano de auditoria.

## 14.4 DeepSeek não foi plenamente comparado

`deepseek-r1:8b` não atingiu uma condição operacional comparável no papel de Relevance dentro do protocolo congelado. A ausência do modelo na matriz final não deve ser interpretada como evidência de inferioridade semântica.

## 14.5 Mudança de output budget no Generator

O aumento de `num_predict=180` para `512` foi necessário para permitir que o schema real fechasse sem truncamento. A mudança foi aplicada como hotfix operacional, com prompts e evidências preservados. Por isso, as rodadas de 180 e 512 **não devem ser usadas para comparação de latência**.

## 14.6 Segurança não equivale a qualidade de produto

O `ministral-3:8b` foi seguro no conjunto de Generator testado, mas respondeu apenas 4–5 dos 11 casos por repetição na Capability Confirmation. A baixa cobertura impede seleção final sem E2E.

---

# 15. Reprodutibilidade

## 15.1 Artefatos principais

| Artefato | SHA-256 |
|---|---|
| `relevance(1).json` | `5ac958cebee07213bf56898635678756319f352c519365cdc72c2aed5c7d3bbc` |
| `semantic.json` | `109a42005535b9bf5e7f60b12bb2bc24f0b3fbc8f7c076392592686dff31a8a6` |
| `generator.json` | `1f3472ff687254d82813cc2c27c517c2466b9ffe6d5003099f39f79bc170b8f7` |
| `generator_retry_512.json` | `5a928446d63c23888d047f2843728f0c516e668d775999170baf66d04eec33d3` |
| `generator_merged.json` | `babb88706b5e5305869eaa09a590b0f9a229cbfe19a84e22f64a6be9fa6ae61b` |
| `confirm_relevance.json` | `15a914d19e7a3b7e3f1f7f4ec6cbab8381e9de58a5f809b2fa542390601747d5` |
| `confirm_semantic.json` | `78c87f5b999451b72f91f47e76ce427136e48f6727213c356da8908bd0ccaeab` |
| `confirm_generator.json` | `e31ab70fd1bdd2f124d1cb240f8ce860c163684614b8da8fd6230103965214e5` |

## 15.2 Manifest hashes dos benchmarks

```text
Relevance kill manifest:
32e6e406271951f0a1fd9ab7b919d25464a4642b6cc481ecf1d6c61affd5396b

Semantic manifest:
7ddd98b69485518ff9eb7019dca411e686e7f0663ecd8eb357e39004883723fd

Generator manifest:
45cba83a11dc675b0408377eb4a254f21c065ca932921905d1a42eb074f2927b

Capability Relevance manifest:
6c6b798e247d0c57523446d1b4b35e13e65f4a513150217f1c5b7f4579e60754
```

## 15.3 Exemplo de execução manual

O padrão operacional usado foi:

```bash
nice -n 10 uv run python -m evaluation.model_benchmark_91 \
  --stage <stage> \
  --resource-profile desktop \
  --num-thread 10 \
  --repeats <N> \
  --resume \
  --models <modelos> \
  --output <arquivo.json>
```

Para Generator, o orçamento confirmado foi:

```bash
--num-predict 512
```

Os comandos exatos de cada estágio permanecem documentados no histórico da Fase 91.1 e nos artefatos de avaliação do repositório.

---

# 16. Conclusão

O processo de seleção mostrou que **taxa de resposta e tamanho do modelo, isoladamente, não foram bons critérios de escolha**. Modelos que respondiam quase todos os casos do Generator foram eliminados por falhas centrais de ator, polaridade ou extrapolação. O único modelo que permaneceu seguro no papel de Generator foi também aprovado nos dois papéis de judge.

A evidência experimental atual sustenta três conclusões:

1. `qwen3.5:4b` é um judge local forte para Relevance e Semantic Support, mas não passou como Generator no protocolo atual;
2. `ministral-3:8b` é o único modelo avaliado que permaneceu elegível nos três papéis;
3. o principal risco residual de `ministral-3:8b` é **recall de geração**, não uma falha crítica de segurança observada nos testes atuais.

Assim, a decisão racional para a próxima etapa é testar primeiro a configuração mais simples:

```text
MINISTRAL 3 8B
= Generator
= Semantic Judge
= Relevance Judge
```

A seleção final do modelo do MVP1 somente poderá ser declarada depois de:

```text
E2E Single-Model Screen
→ gate completo do MVP1
→ Stability
```

Até esse ponto:

```text
SINGLE_MODEL_MVP1_CANDIDATE = ministral-3:8b
MVP1_MODEL_SELECTED         = NO
```

---

## Apêndice A — Regra de interpretação dos resultados

```text
PASS de segurança
≠
modelo final aprovado

ELIMINATED_FOR_ROLE
≠
modelo globalmente incapaz

OPERATIONAL_FAILURE
≠
QUALITY_FAILURE

ABSTENTION
≠
CORRECT

ANSWERED
≠
CORRECT
```

Essas distinções foram mantidas durante todo o experimento para evitar conclusões excessivas a partir de métricas agregadas.

---

## Apêndice B — Referência no README

Este relatório deve ser referenciado pelo `README.md` do projeto com um link explícito na seção de avaliação/qualidade, por exemplo:

```markdown
### Avaliação científica e seleção de modelos locais

A metodologia experimental, os kill-tests por papel, a Capability Confirmation,
as limitações e a justificativa para a escolha provisória de `ministral-3:8b`
como candidato single-model do MVP1 estão documentadas em:

- [Relatório científico de seleção de modelos locais — MVP1](docs/relatorio-cientifico-selecao-modelos-mvp1.md)
```
