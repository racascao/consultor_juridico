# Seleção do modelo

## Comparação Gold Evidence

| Modelo | Automatic pass | Correção | Groundedness | Completude | Human all-pass | Strict | Veredito |
|---|---:|---:|---:|---:|---:|---:|---|
| Qwen3 4B | 25/32 | 29/32 | 29/32 | 25/32 | 25/32 | 22/32 | REJECT |
| Qwen3.5 9B | 27/32 | 29/32 | 29/32 | 26/32 | 26/32 | 25/32 | REJECT |
| Phi-4 Mini 3.8B | 21/32 | 26/32 | 28/32 | 18/32 | 17/32 | 16/32 | REJECT |
| Gemma3 4B | 1/32 | 23/32 | 28/32 | 19/32 | 18/32 | 1/32 | REJECT |
| Gemma4 12B baseline | 12/32 | 32/32 | 32/32 | 29/32 | 29/32 | 12/32 | RECONSIDER |

Gemma4 não venceu pelo maior score automático inicial. Foi escolhido pela
melhor combinação de correção jurídica, groundedness, completude, prudência,
estabilidade e resistência a erros de polaridade.

## Reconsideração controlada

A única variável alterada foi `format=json`. JSON válido passou de 13/32 para
32/32, schema/payload de 12/32 para 31/32, passe automático de 12/32 para 30/32,
cobertura de citação de 18/32 para 32/32 e estabilidade de 5/12 para 12/12.
Correção e groundedness permaneceram 32/32; completude e all-pass, 29/32.

O bloqueio era principalmente de interface, não de conhecimento jurídico.
Consulte o [runbook preservado](../evaluation/gemma4-format-json-reconsideration-v1.md).

## Freeze

Modelo `gemma4:12b`, digest
`4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`,
prompt `gold-evidence-answering/2`, temperatura 0,7, `top_p=0.8`, `top_k=20`,
`repeat_penalty=1.0`, `num_predict=1024`, `num_ctx=8192`, `stream=false`.
