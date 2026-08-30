# Avaliação funcional do MVP2-F2

O dataset `evaluation/datasets/basic_direct_v1.json` contém 18 perguntas de
desenvolvimento, incluindo os cinco casos obrigatórios. Ele mede localização,
não qualidade jurídica geral do produto.

SHA-256 congelado: `71d8305a45b81d156e1583c613fa7b12d4980e29f3186ac7532425ae2870f4e5`.

Métricas: Hit@1, Hit@3, Hit@10 e MRR. Um caso `AMBIGUOUS` só é sucesso quando
todos os alvos conceitualmente distintos aparecem no pool. Falhas registram a
pergunta, targets e top candidates.

Antes da primeira execução real, os targets devem ser auditados e o SHA-256 do
arquivo registrado. Depois do freeze, correções exigem novo dataset versionado.

Execução manual:

```bash
consultor-juridico eval retrieval \
  --dataset evaluation/datasets/basic_direct_v1.json \
  --output evaluation/results/mvp2_retrieval_baseline.json
```

O agente não executou embeddings, Judges ou Generator reais nesta fase. Tests
de adapters usam respostas HTTP mockadas e o teste PostgreSQL opt-in usa
vetores falsos de 768 dimensões.

## Baseline real inicial

A aceitação manual executada pelo usuário sobre o dataset congelado produziu:

| Métrica | Resultado |
|---|---:|
| Casos | 18 |
| Hit@1 | 0,333 |
| Hit@3 | 0,444 |
| Hit@10 | 0,500 |
| MRR | 0,391 |

`RETRIEVAL_BASELINE: FAIL`.

## Análise de causa raiz do retrieval

`RETRIEVAL_ROOT_CAUSE_ANALYSIS` confirmou duas limitações gerais na geração do
pool: os fetches lexical e vetorial eram truncados em `10`, o mesmo tamanho do
resultado final, antes do RRF; e várias SearchUnits da mesma família de artigo
podiam consumir posições distintas do top-10. Os traces preservados mostram
esse crowding nos arts. 14 e 142. RRF, identidade entre modalidades, FTS em
português, cosine exato e matching exato do evaluator não apresentaram erro.

As três SearchUnits `DOCUMENT_METADATA` participam de FTS e vector e possuem
embedding. No caso de promulgação, a consulta lexical observada não encontra a
unidade factual porque `websearch_to_tsquery` exige termos ausentes de seu texto
oficial; nenhum boost, sinônimo ou regra para metadata foi introduzido. Pools
mais profundos e diversidade determinística permitem que unidades recuperadas
fora do antigo cutoff concorram pelo top-10 sem alterar o corpus.

O arquivo detalhado `evaluation/results/mvp2_retrieval_baseline.json`, citado
na execução manual inicial, não estava presente no workspace durante esta
auditoria. Por isso, os ranks não preservados dos nove failures não foram
reconstruídos por inferência. O evaluator agora grava resultados dos 18 casos,
ranks lexical/vetorial/final, tipo, família e contagem de slots duplicados para
que o reteste seja integralmente auditável.

Correção aplicada:

```text
FTS top-30 + vector top-30
  -> RRF k=60
  -> primeira passagem por família jurídica
  -> preenchimento na ordem híbrida
  -> top-10 final
```

`POOL_DIVERSITY_RETEST: NO_MATERIAL_IMPROVEMENT`.

## Auditoria causal das SearchUnits e decisão

O reteste posterior aos pools mais profundos e à diversidade por família não
produziu melhora material. A inspeção da captura materializada separou três
causas que não devem ser tratadas como um único problema de ranking:

1. **representação:** ARTICLEs extensos acumulam toda a subárvore, descendentes
   podem perder o CAPUT regente e 100 de 410 pares ARTICLE/CAPUT possuíam
   `search_text` idêntico;
2. **FTS estrito:** `websearch_to_tsquery` pode exigir todos os lexemas da
   pergunta conversacional, inclusive formas que não aparecem literalmente na
   norma;
3. **régua:** vários targets de `basic_direct_v1` apontam para ARTICLE quando a
   unidade juridicamente determinante é um parágrafo, inciso ou alínea.

As três opções avaliadas foram:

| Opção | Benefício | Limite | Decisão |
|---|---|---|---|
| dataset v2 | corrige a medição com baixo risco | não melhora o produto | necessária antes do gate final, não adotada como correção runtime |
| SearchUnit v2 | melhora a entrada comum a FTS, vetor e modelo | exige rebuild dos embeddings | **adotada em escopo cirúrgico** |
| ablação completa | maior poder causal | várias reconstruções e fragmentação da F2 | reservada se o resultado da v2 for misto |

A implementação escolhida não compacta ARTICLE e não altera FTS, embedding,
RRF ou ranking. Ela aplica somente três regras gerais:

```text
descendente normativo -> inclui CAPUT regente quando existente
metadata -> inclui rótulo factual determinístico
ARTICLE/CAPUT -> remove somente projeção exatamente duplicada
```

O corpus passa de `constitutional-corpus-v2` para
`constitutional-corpus-v3`. Essa versão identifica o contrato completo de
parsing/projeção. O bootstrap detecta automaticamente uma versão ativa antiga,
cria novas ActVersions e embeddings e preserva snapshots/versões anteriores.
O resultado permanece `PENDING_USER_REBUILD_AND_RETEST`; nenhuma melhora de
métrica é declarada antes dessa medição.

Nas quatro consultas E2E iniciais houve `0/4` respostas e `4/4` abstenções,
com latência aproximada de 2–3 minutos por pergunta em CPU. O resultado é
`NOT_ACCEPTABLE_FOR_RELEASE`. O modo `consultar --verbose` foi adicionado para
medir tempos, rota, decisões estruturadas, tamanhos de entrada e causas de
abstenção sem modificar prompts, modelos, retrieval ou decisões.

Comando prioritário para o próximo diagnóstico manual:

```bash
consultor-juridico consultar "Alistamento militar é obrigatório?" --verbose
```

## Diagnóstico do Evidence Relevance Judge

Na pergunta `Alistamento militar é obrigatório?`, o target
`CF88/ARTICLE:143` apareceu em rank 1 lexical, vetorial e fundido. O retrieval
levou aproximadamente `0,7 s`; portanto ele não explica a abstenção desse caso.

O Evidence Relevance Judge levou aproximadamente `179,9 s` e tentou produzir
`CLEAR`, mas a seleção não passou no contrato de candidate IDs. A aplicação
classificou corretamente `RELEVANCE_OUTPUT_INVALID` e se absteve. O trace
anterior não preservou os IDs brutos, portanto o formato exato retornado naquela
execução permanece desconhecido; o modo verbose agora registra de forma segura
`raw_decision`, `raw_selected_candidate_ids` e os IDs permitidos.

O contrato passou a enumerar dinamicamente os candidate IDs da requisição e
mantém validação determinística posterior. `CLEAR` exige seleção não vazia,
`UNSUPPORTED` proíbe seleção e `AMBIGUOUS` exige interpretações válidas. Uma
stable reference não é aceita como identidade alternativa.

A auditoria confirmou que a entrada já continha apenas uma representação
textual por candidata: `search_text`. `citation_text` não era enviado; aparecia
somente como métrica. Assim, nenhum conteúdo jurídico foi removido. A serialização
JSON compacta reduziu o caso real auditado de `12.095` para `12.033` caracteres
de user payload (`0,513%`); incluindo o system prompt, a estimativa passa de
`12.382` para aproximadamente `12.320` caracteres.

Essa primeira correção usou limite de 384 tokens e uma `reason` curta; o segundo
reteste abaixo motivou a simplificação estrutural definitiva do contrato.

`RELEVANCE_CORRECTNESS: NOT_YET_VALIDATED`  
`RELEVANCE_LATENCY: FAIL`

## Primeiro reteste do Consultation Model

Para `Alistamento militar é obrigatório?`, o retrieval preservou E1 como
`CF88/ARTICLE:143` e levou aproximadamente `0,42 s`. A chamada do Consultation
Model terminou após cerca de `3,89 s` com `PROVIDER_ERROR`, output inválido e
sem métricas nativas do Ollama. Esse tempo não representa latência de
inferência.

Os logs do provider registraram HTTP 400 antes da inferência: a conversão do
JSON Schema para gramática falhou porque a repetição limitada de até 2.000
caracteres da resposta, combinada à união discriminada e arrays, excedeu os
limites internos do parser de gramática. O schema continua discriminado e
request-scoped, mas a resposta deixa de emitir `maxLength`; o limite operacional
de 512 tokens permanece inalterado e as invariantes continuam validadas.

O client agora preserva categoria, status HTTP e mensagem sanitizada do
provider. A rota distingue `CONSULTATION:PROVIDER_FAILURE` e
`CONSULTATION:OUTPUT_INVALID` de uma decisão semântica
`CONSULTATION:ABSTAIN`.

`CONSULTATION_OUTPUT: INVALID`  
`FAILURE: PROVIDER_ERROR / HTTP 400`  
`OLLAMA_NATIVE_METRICS: UNAVAILABLE`  
`NO_REAL_CONSULTATION_INFERENCE_OCCURRED: YES`  
`CONSULTATION_REAL_INFERENCE_LATENCY: NOT_MEASURED`  
`PROVIDER_FIX_REAL_RETEST: PENDING`

## Decisão arquitetural CPU-first

O reteste manual com `ministral-3:3b` também retornou `UNSUPPORTED` com output
válido, apesar de `CF88/ARTICLE:143` permanecer como E1. A chamada levou
`71.259,4 ms`, dos quais `65.954,7 ms` foram prompt evaluation de `3.886`
tokens (`58,92 tokens/s`); load foi `3.726,8 ms` e a geração de 14 tokens,
`1.522,2 ms`.

Os resultados preservados sustentam a decisão:

- relevance 8B: aproximadamente `154,7 s` e decisão semanticamente incorreta;
- relevance 3B: aproximadamente `71,3 s` e decisão semanticamente incorreta;
- contrato estruturado: válido no último reteste de ambos;
- target militar: rank 1 lexical, vetorial e fundido.

`MULTI_LLM_WORKFLOW: REJECTED_FOR_CPU_MVP`.

O runtime passa a executar `retrieval -> Consultation Model -> Citation
Validator`, com apenas uma inferência de chat em pergunta direta. O modelo
retorna `ANSWER`, `CLARIFY` ou `ABSTAIN`; somente clarificação seguida de nova
entrada humana permite outra inferência. Retrieval, RRF, pool de dez candidatas
e dataset permanecem inalterados.

`SIMPLIFIED_WORKFLOW_REAL_RETEST: PENDING`

### Terceiro reteste real e correção semântica

O terceiro reteste validou o contrato discriminado, mas o Judge devolveu
`UNSUPPORTED`. A inspeção somente leitura do PostgreSQL confirmou que E1 era
`CF88/ARTICLE:143`, em primeiro lugar lexical, vetorial e fundido, com o texto
factual “O serviço militar é obrigatório nos termos da lei.” A decisão foi,
portanto, uma falha semântica do classificador, não do retrieval ou do contrato.

As métricas observadas foram:

- retrieval: `731,7 ms`;
- chamada total do Judge: `154.707,9 ms`;
- carregamento do modelo: `7.264,4 ms`;
- prompt eval: `144.322,7 ms` para `3.803` tokens (`26,35 tokens/s`);
- geração: `3.044,2 ms` para `15` tokens.

O prompt anterior aproximava relevância de “responder” ou “sustentar a
resposta”, confundindo o gate inicial com suficiência e correção finais. A
política agora classifica apenas relevância jurídica material: `CLEAR` permite
prosseguir quando há relação material e específica, mesmo se forem necessárias
qualificação ou distinção terminológica; `UNSUPPORTED` exige ausência dessa
relação; `AMBIGUOUS` exige ambiguidade real da pergunta. Sufficiency e Answer
Judge continuam responsáveis pelos gates posteriores.

Para reduzir o custo em CPU sem alterar Generator ou Answer Judge, os papéis
passaram a ter modelos configuráveis separadamente:

- Evidence Relevance Judge: `ministral-3:3b`;
- Generator e Answer Judge: `ministral-3:8b`;
- embeddings: `nomic-embed-text`.

O bootstrap provisiona os três modelos e o modo verbose identifica o modelo de
cada chamada. Essa mudança não altera o contrato discriminado, o pool de dez
candidatos, retrieval, RRF, LangGraph ou conteúdo enviado ao Judge. A validação
real do comportamento e da latência do modelo 3B permanece pendente de reteste
manual.

`RELEVANCE_CONTRACT: PASS`  
`RELEVANCE_SEMANTICS_BASELINE: FAIL`  
`RELEVANCE_PERFORMANCE_BASELINE: FAIL`  
`RELEVANCE_3B_MANUAL_RETEST: PENDING`

### Segundo reteste real

O segundo reteste manteve `CF88/ARTICLE:143` como E1 e confirmou:

- retrieval: aproximadamente `0,72 s`;
- Evidence Relevance Judge: aproximadamente `176,44 s`;
- raw decision: `CLEAR`;
- selected candidate IDs: vazio;
- output: `INVALID_STRUCTURED_OUTPUT`;
- abstenção: `RELEVANCE_OUTPUT_INVALID`.

Isso demonstrou que o enum request-scoped restringia valores presentes, mas a
variante monolítica ainda permitia estruturalmente uma lista vazia. O contrato
foi substituído por variantes discriminadas: `CLEAR` exige o campo singular
`selected_candidate_id`; `UNSUPPORTED` não possui campo de seleção; e
`AMBIGUOUS` exige ao menos duas interpretações, cada uma com candidate IDs do
pool. O campo discursivo `reason` foi removido desse classificador e seu output
foi limitado a 256 tokens.

O modo verbose passa a registrar, quando fornecidos pelo Ollama,
`total_duration`, `load_duration`, `prompt_eval_count`,
`prompt_eval_duration`, `eval_count` e `eval_duration`, além das taxas derivadas
de tokens por segundo. Ausência dessas métricas é exibida como `N/A` e não altera
o workflow.

`RELEVANCE_CORRECTNESS: NOT_YET_VALIDATED`  
`RELEVANCE_LATENCY: FAIL`
