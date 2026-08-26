# Fase 91.1 — Staged Model Elimination Benchmark

## Resultado da execução

O benchmark staged não pôde iniciar uma matriz válida nesta sessão. O serviço
Ollama Docker está saudável e os sete modelos exigidos estão disponíveis, mas a
execução de chamadas prolongadas ao daemon requer aprovação elevada que expirou
antes da conclusão do primeiro estágio.

Nenhum modelo foi eliminado. A ausência de uma resposta não é evidência de
falha de relevance, semantic support ou generator.

O harness resumível permanece em
`evaluation/model_benchmark_91.py`. O resultado parcial anterior da Fase 91
continua apenas diagnóstico e não foi reutilizado como classificação.

## Hotfix de compatibilidade Qwen/DeepSeek

O harness foi corrigido sem alterar prompt, dataset ou gate:

- envia `think=false` por padrão;
- separa `message.content` de `message.thinking`;
- não persiste conteúdo de thinking;
- classifica falhas como `EMPTY_FINAL_CONTENT`,
  `THINKING_WITHOUT_FINAL_CONTENT`, `JSON_PARSE_ERROR`,
  `INVALID_STRUCTURED_OUTPUT`, `OLLAMA_TIMEOUT` ou `OLLAMA_HTTP_ERROR`;
- preserva somente metadados seguros de observabilidade;
- permite filtrar modelos com `--models`;
- falhas operacionais são reexecutáveis no resume.

O probe único do `qwen3.5:4b` retornou `message.content` JSON válido, sem
thinking exposto, mas classificou o par de prisão perpétua incorretamente. Isso
é observação de qualidade do probe, não eliminação. Os probes de `qwen3.5:9b` e
`deepseek-r1:8b` não produziram evidência suficiente nesta sessão para uma
classificação de causa.

Rerun manual restrito aos três modelos com falha operacional:

```bash
uv run python -m evaluation.model_benchmark_91 \
  --stage relevance-kill --resource-profile desktop --num-thread 10 \
  --repeats 1 --resume \
  --models qwen3.5:4b,qwen3.5:9b,deepseek-r1:8b
```

## Semantic Support Kill-Test

O harness agora possui um subconjunto congelado de suporte semântico, separado
de relevance e sem query. Ele grava em arquivo próprio e aceita os mesmos
checkpoints:

```bash
nice -n 10 uv run python -m evaluation.model_benchmark_91 \
  --stage semantic-kill --resource-profile desktop --num-thread 10 \
  --repeats 1 --resume \
  --output evaluation/results/model_benchmark_91_1/semantic.json \
  --models qwen3.5:4b,ministral-3:3b,qwen3.5:9b,ministral-3:8b,granite4.1:3b,granite4.1:8b
```

DeepSeek só deve ser incluído se o probe de orçamento 512 produzir conteúdo
final contratual.

Estado conhecido:

- modelos disponíveis: qwen3.5:4b, ministral-3:3b, qwen3.5:9b,
  ministral-3:8b, granite4.1:3b, granite4.1:8b e deepseek-r1:8b;
- Ollama: `0.32.15`;
- PostgreSQL/Compose: saudável;
- nenhum benchmark staged concluído;
- nenhuma eliminação por papel;
- nenhuma matriz end-to-end;
- nenhuma integração de produção.

Próxima execução autorizada deve começar exclusivamente pelo
`relevance-kill`, com uma repetição por modelo, e persistir cada chamada antes
de continuar. Depois disso devem seguir semantic kill-test, generator kill-test,
confirmação e somente então end-to-end.

## Preparação manual

O harness usa execução sequencial (`MAX_CONCURRENT_MODELS=1` e
`MAX_CONCURRENT_REQUESTS=1`), perfil `desktop`, persistência atômica e unload
do modelo ao trocar de bloco. O número de threads padrão é metade dos CPUs
detectados, preservando capacidade para o desktop; pode ser sobrescrito por
`--num-thread N`.

Primeira execução recomendada, somente relevance kill-test:

```bash
uv run python -m evaluation.model_benchmark_91 \
  --stage relevance-kill \
  --resource-profile desktop \
  --num-thread 8 \
  --repeats 1 \
  --resume
```

O argumento `--resume` é aceito como parte do protocolo manual; resultados
existentes são identificados por modelo, par e repetição. O arquivo padrão é
`evaluation/results/model_benchmark_91_1/relevance.json` e o log é
`evaluation/results/model_benchmark_91_1/benchmark.log`.

Para reduzir prioridade sem root:

```bash
nice -n 10 uv run python -m evaluation.model_benchmark_91 \
  --stage relevance-kill --resource-profile desktop --num-thread 8 --repeats 1
```

Para execução longa, recomenda-se:

```bash
tmux new -s benchmark-mvp1
# executar o comando acima
# Ctrl+B, D para destacar
tmux attach -t benchmark-mvp1
```

`Ctrl+C` registra o checkpoint e preserva o JSON; repetir o mesmo comando
retoma a execução. Nesta preparação, apenas o estágio `relevance-kill` está
implementado no harness; semantic, generator, confirm, e2e e stability devem
ser adicionados antes da execução desses estágios.

STAGED_MODEL_ELIMINATION_BENCHMARK:
INCONCLUSIVE

MODELS_AVAILABLE:
qwen3.5:4b, ministral-3:3b, qwen3.5:9b, ministral-3:8b, granite4.1:3b, granite4.1:8b, deepseek-r1:8b

RELEVANCE_SURVIVORS:
NONE

SEMANTIC_SURVIVORS:
NONE

GENERATOR_SURVIVORS:
NONE

RELEVANCE_ELIMINATED:
NONE

SEMANTIC_ELIMINATED:
NONE

GENERATOR_ELIMINATED:
NONE

FINALISTS:
NONE

PROVISIONAL_WINNER:
NONE

STABILITY_RUNS_COMPLETED:
0

REAL_WORLD_CORRECT_MEAN:
N/A

REAL_WORLD_CORRECT_MIN:
N/A

REAL_WORLD_CORRECT_MAX:
N/A

FALSE_ABSTENTION_MEAN:
N/A

UNSAFE_PRODUCT_ANSWERS:
N/A

FALSE_RELEVANT:
N/A

FALSE_SUPPORT:
N/A

WRONG_LEGAL_ACTOR:
N/A

TRUE_BUT_IRRELEVANT:
N/A

SUPPORTED_BUT_OFF_TARGET:
N/A

QUALIFIER_PRESERVATION:
N/A

CORRECT_ABSTENTION:
N/A

INVALID_CITATION_CHAINS:
N/A

MVP1_HIT_AT_10:
0.905 (baseline histórico, não reavaliado)

BEST_GENERATOR:
NONE

BEST_SEMANTIC_JUDGE:
NONE

BEST_RELEVANCE_JUDGE:
NONE

MVP1_GENERATOR_MODEL:
NONE

MVP1_SEMANTIC_JUDGE_MODEL:
NONE

MVP1_RELEVANCE_JUDGE_MODEL:
NONE

BEST_CONFIG_LATENCY_MEAN:
N/A

BEST_CONFIG_LATENCY_P95:
N/A

SELECTION_STRATEGY:
FIRST_SAFE_MVP1_WINNER

MODEL_SELECTION:
INCONCLUSIVE

MVP1_QUALITY_GATE:
NOT_EVALUATED

MODEL_TOPIC:
OPEN

NEXT_STEP:
CONTINUE_BENCHMARK

PRODUCTION_INTEGRATION:
NOT_ENABLED

COMMIT:
DO_NOT_COMMIT_YET

## Fechamento do semantic kill-test e preparação do generator kill-test

O artefato `evaluation/results/model_benchmark_91_1/semantic.json` contém as
60 execuções manuais (6 modelos × 10 fixtures). Os survivors semânticos são
`qwen3.5:4b`, `ministral-3:3b`, `qwen3.5:9b` e `ministral-3:8b`; `granite4.1:3b`
permanece backup seguro porém com baixa recall e `granite4.1:8b` foi eliminado
como judge por uma aceitação insegura. A exceção material omitida foi tratada
de forma fail-closed pelos modelos seguros.

O harness agora possui o estágio independente `generator-kill`. Ele usa o
contrato real `consultor_juridico.consultation.llm.RESPONSE_SCHEMA`, EvidenceSets
congelados de `evidence_bound_12_frozen_evidence_sets.json`, sem retrieval ou
correção automática de Evidence IDs. Nenhuma inferência foi executada nesta
etapa. O comando manual é:

```bash
nice -n 10 uv run python -m evaluation.model_benchmark_91 \
  --stage generator-kill --resource-profile desktop --num-thread 10 \
  --repeats 1 --resume \
  --output evaluation/results/model_benchmark_91_1/generator.json \
  --models qwen3.5:4b,ministral-3:3b,qwen3.5:9b,ministral-3:8b,granite4.1:3b,granite4.1:8b
```

DeepSeek não integra a matriz inicial; seu probe opcional continua limitado a
um único teste com `--models deepseek-r1:8b`.

## Hotfix do output budget

A auditoria dos 66 resultados confirmou 28 `VALID` e 38 `JSON_PARSE_ERROR`. Os
38 casos terminaram com `done_reason=length` e `eval_count=180`, demonstrando
exaustão do orçamento de saída. Isso mantém o estágio inicial inconclusivo por
razão operacional, sem eliminar modelos por qualidade.

O harness agora aceita `--num-predict`, `--retry-from` e `--retry-status`. O
retry usa 512 apenas para o Generator e preserva o arquivo original. Também há
mesclagem determinística com proveniência.

O caso `granite4.1:3b / rw-aborto` foi auditado separadamente: a resposta não
abstida usa a evidência do art. 60 para uma pergunta sobre aborto, uma falha
grave `UNSUPPORTED_CENTRAL_ANSWER`/`SUPPORTED_BUT_OFF_TARGET`. O modelo foi
eliminado somente do papel Generator.

Retry manual dos cinco modelos ainda elegíveis:

```bash
nice -n 10 uv run python -m evaluation.model_benchmark_91 \
  --stage generator-kill --resource-profile desktop --num-thread 10 \
  --num-predict 512 --repeats 1 --retry-from \
  evaluation/results/model_benchmark_91_1/generator.json \
  --retry-status JSON_PARSE_ERROR \
  --output evaluation/results/model_benchmark_91_1/generator_retry_512.json \
  --models qwen3.5:4b,ministral-3:3b,qwen3.5:9b,ministral-3:8b,granite4.1:8b
```

Merge posterior:

```bash
uv run python -m evaluation.model_benchmark_91 \
  --merge-original evaluation/results/model_benchmark_91_1/generator.json \
  --merge-retry evaluation/results/model_benchmark_91_1/generator_retry_512.json \
  --merge-output evaluation/results/model_benchmark_91_1/generator_merged.json
```

## Fechamento do Generator Kill-Test

O retry manual contém 30/30 resultados `VALID`, todos com `done_reason=stop` e
`num_predict=512`. O merge determinístico contém 66 registros efetivos; 30
vieram do retry e os demais foram reutilizados da execução original. Oito
registros continuam operacionais (`granite4.1:3b`, já eliminado como Generator)
e não são reexecutados.

Auditoria do merged confirmou cinco respostas Qwen 4B com `abstain=false` e
`claims=[]`. Também confirmou falhas críticas de ator/escopo em estado de sítio
para Qwen 4B, Qwen 9B e Ministral 3B, e inversões de polaridade para Granite 8B.
Ministral 8B não apresentou falha crítica nos 11 casos, mas permanece
`SAFE_BUT_LOW_RECALL`, não um modelo de produção selecionado.

Resultado provisório por papel:

- Generator survivor: `ministral-3:8b` (seguro, baixa recall).
- Relevance finalists: `qwen3.5:4b`, `ministral-3:8b`.
- Semantic finalists: `qwen3.5:4b`, `ministral-3:8b`.
- Single-model candidate: `ministral-3:8b`, ainda sem seleção final.

O harness aceita os estágios de confirmação `confirm-relevance`,
`confirm-semantic` e `confirm-generator`. Nenhuma inferência foi executada.

## Capability Confirmation

Os artefatos confirmam:

- Relevance: Qwen 4B e Ministral 8B aprovados, sem false-relevant crítico.
- Semantic: ambos aprovados, sem unsafe acceptance; exceção material permanece
  fail-closed como `UNSUPPORTED`.
- Generator Ministral 8B: 33/33 contratos válidos, sem IDs inválidos, ator
  crítico incorreto ou inversão de polaridade.
- Recall do Generator: 5/11, 4/11 e 4/11 respostas nas três repetições;
  classificação `SAFE_BUT_LOW_RECALL`.
- Liberdade religiosa apresentou ruído de payload em abstenções (`answer`
  substantivo junto de `abstain=true`), que deve ser verificado no E2E.

O próximo experimento é somente o screen E2E da configuração single-model:
`ministral-3:8b` como generator, semantic judge e relevance judge. Não foi
executado nem foi criado resultado E2E. A execução deve usar o pipeline real
(`evaluation.evidence_bound_12`) e registrar o resultado em
`evaluation/results/model_benchmark_91_1/e2e_single_model_screen.json`.

### Auditoria pré-E2E

O módulo `evaluation.evidence_bound_12` reutiliza componentes reais de
retrieval, EvidenceSet, Generator, attribution, Citation Validator, Polarity e
Semantic Validator, mas é um harness experimental da Fase 12: persiste
EvidenceSets e não é a CLI final de consulta. Portanto, sua cobertura é
`PARTIAL`, não um E2E de produto apto para o gate.

Também não existe um `relevance_judge_model` configurável no pipeline atual.
Relevance é tratado por retrieval/selection/sufficiency determinísticos; não é
possível declarar honestamente `ministral-3:8b` como relevance judge sem alterar
arquitetura. Além disso, o Generator real usa `settings.consultation_max_tokens`
(default 800), não 512, e o Semantic Validator envia `num_predict=500`.

A política de abstenção retorna `response.answer` quando `abstain=true` e o
campo não está vazio. Logo, o comportamento atual é `RAW_MODEL_ANSWER`, e o
screen E2E fica bloqueado até essa política ser explicitamente corrigida ou
aprovada.

### Pre-E2E hardening concluído

O serviço agora canonicaliza toda abstenção para a mensagem controlada
`ABSTENTION`; o texto bruto do modelo não é usado como resposta jurídica.
Generator e Semantic Judge enviam `think=false` explicitamente. Foi criado o
entrypoint `evaluation.e2e_single_model_91`, que chama
`consultor_juridico.evaluation.real_world.evaluate_real_world`, portanto usa o
serviço real, retrieval real e validators reais. Relevance permanece
determinístico; não há relevance LLM.

O E2E ainda não foi executado. O comando manual é:

```bash
OLLAMA_MODEL=ministral-3:8b \
SEMANTIC_JUDGE_MODEL=ministral-3:8b \
uv run python -m evaluation.e2e_single_model_91
```
