# Fase 93 — MVP1 Generator Contract Closure

## Baseline

O segundo E2E, preservado em
`evaluation/results/model_benchmark_92_e2e_2/e2e_second_run.json`, tem SHA-256
`e404079ac15c8d0df1d262530994edf21af2c2d32e217afc4b665bd330088f90` e
registrou `3/10` respostas estritamente corretas, `1/1` abstenção esperada,
`0` respostas inseguras e retrieval Hit@10 de `0.900`.

## Alteração única

O contrato do Generator agora exige uma **menor resposta completa**: para uma
pergunta sobre uma regra única, a preferência explícita é uma única claim
curta, direta e fiel. Claims de contexto, histórico, competência, comentário
geral ou norma lateral não devem ser criadas se não forem indispensáveis para
responder à pergunta.

A claim contém somente a proposição jurídica. Artigo, parágrafo, inciso, alínea
e item não devem ser inventados ou incluídos manualmente pelo Generator: a
localização factual continua sendo responsabilidade das citations/EvidenceItems.
O Locator Fidelity Guard não foi relaxado; locator explícito espontâneo e
incorreto continua bloqueado.

## Contexto estrutural

`build_evidence_prompt` já entregava `validation_metadata.parent_context` de
EvidenceItems legados. Esse dado autorizado segue apresentado como `Contexto
estrutural`, sem novo lookup, VCSA, materialização, união semântica ou alteração
de snapshot.

## Proteções preservadas

Attribution, Locator Fidelity Guard, Citation Validation, Polarity Guard e
Semantic Support Validator não foram alterados. Atomic, VCSA, Structural
Expansion/Reserve e a correção experimental de Evidence Selection seguem
congelados e não integrados. O prompt mantém a instrução de abster-se quando a
evidência não suporta resposta direta e completa.

## Harness E2E

`evaluation.e2e_single_model_91` passou a exigir `--output`. Ele cria o
diretório pai e recusa, antes de qualquer inferência, sobrescrever um arquivo
existente com `OUTPUT_ALREADY_EXISTS`.

O terceiro E2E deve ser executado manualmente:

```bash
mkdir -p evaluation/results/model_benchmark_93_e2e_3

OLLAMA_MODEL=ministral-3:8b \\
SEMANTIC_JUDGE_MODEL=ministral-3:8b \\
uv run python -m evaluation.e2e_single_model_91 \\
  --output evaluation/results/model_benchmark_93_e2e_3/e2e_third_run.json \\
  2>&1 | tee evaluation/results/model_benchmark_93_e2e_3/e2e_third_run.log
```

Nenhuma inferência LLM foi executada nesta fase. Estado de sítio continua
`KNOWN_REMAINING_FAILURE`; a próxima medição, e não diagnósticos históricos,
determinará os casos residuais.

## Validação

- testes focais: `42 passed`;
- suíte completa em container somente leitura: `407 passed, 5 skipped, 0 failed, 0 errors`;
- contrato e harness cobertos por testes determinísticos; nenhuma sobrescrita
  do baseline original é permitida.
