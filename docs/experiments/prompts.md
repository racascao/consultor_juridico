# Experimentos de prompts

O prompt v1 deixava ambígua a justificativa em abstenções. O v2 explicitou o
objeto JSON com `decision`, `answer` e `citations` e tornou-se
`gold-evidence-answering/2`. Um v3 testou o rótulo `EVIDENCE_ID`, não apresentou
ganho global e foi rejeitado.

Thinking foi desabilitado e `format=json` foi adotado como structured output do
Ollama. Não há stripping de Markdown, parser tolerante, reparo de JSON ou retry
semântico: contrato inválido falha fechado.

O prompt congelado não pode ser ajustado contra o Blind HOLDOUT. Uma nova
iteração exige novo DEV e novo freeze em versão posterior.
