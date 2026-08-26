# Fase 95 — Implementação consolidada do EBCG-v1

## Implementação

EBCG-v1 está no caminho real de consulta. `EvidenceBoundControlledGenerator` é
puro, não possui I/O e substitui o Generator LLM no CLI, na CLI interativa, nas
avaliações de consulta e no harness E2E.

Sua única regra é:

```text
EV001 validado e com text_snapshot não vazio
  -> C1.text = EV001.text_snapshot
  -> C1.evidence_codes = (EV001,)
```

Sem `EV001`, com snapshot vazio/whitespace ou EvidenceItem não validado, o
resultado é a abstenção canônica. Não existe fallback para `EV002`, composição
com `parent_context`, geração de claims auxiliares, união de evidências ou
chamada ao Ollama Generator.

## Pipeline preservado

Após EBCG-v1, o fluxo ainda executa Attribution, Locator Fidelity, Citation
Validation, Polarity e Semantic Support. A attribution não é ignorada apesar
da claim ser extrativa. O Semantic Judge `ministral-3:8b` permanece como veto
fail-closed; `OLLAMA_MODEL` continua disponível por compatibilidade e para
dependências históricas, mas não gera claims no pipeline MVP1.

Atomic, VCSA, Structural Expansion/Reserve e tuning experimental de seleção
permanecem fora da produção.

## Harness E2E

`evaluation.e2e_single_model_91` registra para futuras execuções:

```json
{
  "phase": "95",
  "configuration": {
    "generation_mode": "EBCG_V1",
    "generator_model": null
  }
}
```

O parâmetro `--output` continua obrigatório e a sobrescrita continua recusada.
O primeiro E2E EBCG-v1 deve ser executado manualmente em:

```text
evaluation/results/model_benchmark_95_ebcg_e2e_1/e2e_ebcg_run_1.json
```

Nenhuma inferência, embedding real ou E2E foi executado nesta fase.

## Validação

Os testes unitários cobrem Core Evidence, snapshot exato, vínculo exclusivo,
ausência de composição pai-filho, ausência de fallback, abstention, ausência
de HTTP/Ollama e compatibilidade com Attribution/Locator/Polarity. O harness
também possui teste que confirma a instanciação de EBCG-v1 sem Generator
Ollama.

As limitações da ADR 105 permanecem intencionais: fragmentos estruturalmente
incompletos são exibidos como snapshot ou abstidos pelos validators; EBCG-v1
não os completa.
