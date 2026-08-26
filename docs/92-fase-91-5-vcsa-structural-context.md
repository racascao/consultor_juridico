# Fase 91.5 — VCSA Structural Context Safety Gate

Esta fase avaliou offline uma composição estrutural mínima para recuperar contexto
entre um elemento normativo pai e seu filho direto. Nenhuma inferência LLM, consulta
ao corpus, persistência ou alteração de retrieval foi executada.

## Algoritmo

`compose(parent, child)` só é aplicável quando há relação direta permitida
(`CAPUT/PARAGRAPH → INCISO`, `INCISO → ALINEA` ou `ALINEA → ITEM`), mesma fonte
jurídica e versão, ambos `CURRENT` e `NORMATIVE`, e o texto do pai termina em `:`.
O resultado é a concatenação literal dos dois textos e um SHA-256 determinístico
derivado dos IDs e do texto. Os dataclasses são imutáveis.

## Evidência e controles

Na captura de referência, a evidência da prisão perpétua foi recuperada e
selecionada. O pai direto é o inciso XLVII e a alínea B é o alvo. A composição
offline foi: `não haverá penas: b) de caráter perpétuo`.

Três controles positivos e sete classes de controles negativos (irmão, primo,
versão/ato diferentes, não vigente, não normativo e composição apenas semântica)
passaram sem aceitação indevida. Locator guard e proveniência permanecem preservados.

## Decisão

O componente é seguro nos testes isolados, mas a integração de produção não foi
habilitada nesta etapa: não existe ainda um ponto de materialização de contexto
cuja integração pudesse ser validada sem reabrir seleção, attribution ou o fluxo
E2E. Portanto o resultado é `INCONCLUSIVE`, e nenhuma inferência nova foi feita.

Artefato bruto: `evaluation/results/model_benchmark_91_5/vcsa_safety_gate.json`.
