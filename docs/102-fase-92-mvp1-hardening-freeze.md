# Fase 92 — MVP1 Hardening Freeze & Second E2E Readiness

## Objetivo

Encerrar os experimentos de hardening não integrados e preparar uma segunda
medição E2E manual, sem modificar o pipeline de produção.

## SHA do baseline

O SHA-256 verificado de
`evaluation/results/model_benchmark_91_1/e2e_single_model_screen.json` é:

```text
866b4b7f467cffd709a884231a076d2e6b0bed90821f83e0ce0d596c3be7c72b
```

O artefato da Fase 91.14 já registra esse valor. O valor alternativo reportado
na comunicação anterior não corresponde ao arquivo original e não alterou o
baseline.

## Pipeline de produção auditado

O serviço real aplica, nesta ordem relevante: attribution determinística,
Locator Fidelity Guard, Citation Validator, Polarity Guard e Semantic Support
Validator. O contexto estrutural do pai de EvidenceItems legados é incluído no
prompt semântico; EvidenceItems materializados continuam usando apenas seu
texto efetivo, sem duplicação.

Estão ativos:

- `LOCATOR_FIDELITY_GUARD`;
- correção de regressão de `SEMANTIC_PARENT_CONTEXT`.

Permanecem fora do pipeline:

- Atomic Claim Acceptance;
- materialização VCSA;
- Structural Expansion;
- Structural Reserve;
- correção experimental de Evidence Selection.

## Congelamento

Os cinco componentes experimentais acima ficam congelados como inconclusivos
para esta medição. A segunda execução não deve ativá-los nem usar diagnósticos
históricos como substituto de sua própria medição.

## Baseline técnico

- PostgreSQL e Ollama: saudáveis;
- Alembic: `005_normative_identity_occurrences`;
- suíte em container somente leitura: `403 passed, 5 skipped, 0 failed, 0 errors`;
- Ruff format/check e `git diff --check`: aprovados.

## Comando manual do segundo E2E

```bash
OLLAMA_MODEL=ministral-3:8b \\
SEMANTIC_JUDGE_MODEL=ministral-3:8b \\
uv run python -m evaluation.e2e_single_model_91 \\
  2>&1 | tee evaluation/results/model_benchmark_91_1/e2e_single_model_screen.log
```

O harness usa `run_consultation`/`evaluate_real_world`, portanto mede o
pipeline real vigente. Mantém relevância determinística, embedding
`nomic-embed-text:latest`, `think=false`, `num_predict=800` para geração e
`num_predict=500` para validação semântica.

## Limite desta fase

Nenhuma inferência Ollama, E2E, teste de estabilidade ou nova ingestão foi
executada nesta fase. A seleção final de modelo permanece pendente da segunda
medição E2E e de estabilidade subsequente.
