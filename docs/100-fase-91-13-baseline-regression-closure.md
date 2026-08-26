# Fase 91.13 — Baseline Regression & Test Suite Closure

## Diagnóstico

A falha `test_semantic_prompt_preserves_structural_parent_context` protegia o
contrato de que uma evidência legada cujo texto depende do pai direto envia esse
contexto ao Semantic Judge. A regressão removia a informação de
`build_semantic_support_prompt`, embora `_authorized_evidence_text` ainda a
usasse na âncora lexical interna.

Classificação: `PRODUCT_REGRESSION`.

## Correção mínima

O prompt voltou a usar uma projeção autorizada: EvidenceItem legado inclui
`text_snapshot` e `Contexto estrutural`; MaterializedEvidence usa somente
`effective_text`, sem duplicação. VCSA/materialização continuam experimentais.

## Validação

- focais: `60 passed`;
- suíte containerizada: `403 passed, 5 skipped, 0 failed, 0 errors`;
- Locator Guard preservado;
- sem alteração de retrieval, seleção, orçamento, RRF ou expansão estrutural.

Estado de sítio continua unresolved; `STRUCTURAL_RETRIEVAL_PATH=INCONCLUSIVE`
e `EVIDENCE_SELECTION_FIX=INCONCLUSIVE`.
