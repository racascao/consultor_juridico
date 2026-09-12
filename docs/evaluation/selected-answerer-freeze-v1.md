# Freeze do answerer selecionado — v1

## Identidade congelada

O answerer selecionado pela Fase 2 não é apenas um modelo. Sua identidade
canônica é `gold-evidence-selected-answerer/1` e reúne:

```text
model: gemma4:12b
model_digest: 4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c
prompt: gold-evidence-answering/2
prompt_sha256: 700999a44c81d6c4625b238d3ddb0be33f8d3a069c3e3107cefd8a4d02ef8c00
thinking_mode: disabled
ollama_format: json
temperature: 0.7
top_p: 0.8
top_k: 20
repeat_penalty: 1.0
num_predict: 1024
num_ctx: 8192
stream: false
timeout_seconds: 180
```

O artifact canônico é
`evaluation/model_selection/gold_evidence_selected_answerer_freeze_v1.json`.
Seu SHA-256 é
`d07d5b3ca9feb9c16193a400609215c55ecd5e04f8e26429a035ee51f950e12a`.
Ele registra também dataset, bundles, manifest cross-model e quatro artifacts
do baseline e quatro artifacts de seleção com seus hashes SHA-256.

## Contrato e runtime

O output deve ser exclusivamente um objeto JSON com os campos `decision`,
`answer` e `citations`. As decisões permitidas são `ANSWER`, `ABSTAIN` e
`CLARIFY`; `citations` contém somente `stable_key` autorizadas. Markdown fences,
texto circundante, campos adicionais, reparo pós-geração, renomeação automática
e retry específico por formato não são permitidos. Violações falham fechadas.

O runtime aceito é o Ollama do Docker Compose. A URL interna é
`http://ollama:11434`; `http://localhost:11435` existe somente para CLI no host.
O Ollama nativo do host não é permitido.

## Evidência da seleção

O baseline sem structured output permanece `RECONSIDER`. A reconsideração com
`format=json` obteve `30/32` passes automáticos, `12/12` decisões formalmente
estáveis, `29/32` na interseção automática+humana e preservou `32/32` em
correção jurídica, `32/32` em groundedness e `29/32` em completude. Seu veredito
é `ACCEPT`, sem reescrever o histórico experimental.

As limitações residuais são:

- `GOLD-027_OUTPUT_SCHEMA_FAILURE_CITATIONS_IDS`;
- `GOLD-031_CLARIFICATION_DECISION_FAILURE`;
- `RISK-05_CLARIFICATION_CONTENT_INCOMPLETENESS`.

## Validação e política de mudança

O comando abaixo valida somente código e arquivos locais; ele não consulta
Ollama, rede ou banco e não executa inferência:

```bash
.venv/bin/consultor-juridico eval gold selected-answerer-status
```

Qualquer mudança em modelo, digest, prompt, configuração de geração, thinking,
`ollama_format`, contrato de output ou mecanismo de structured output invalida
o freeze e exige reavaliação apropriada antes do HOLDOUT. Mudanças silenciosas
são proibidas.

O HOLDOUT permanece fechado e não lido, o corpus vivo permanece `UNRESOLVED` e
a integração RAG não foi iniciada. O próximo estágio canônico após a Fase 2 é a
integração RAG, seguida de DEV integrado, freeze do runtime integrado e somente
então HOLDOUT cego.

## Revisão final da Fase 2

O freeze foi revalidado com `STATUS=VALID`, todos os gates canônicos da Fase 2
foram confirmados e não restou blocker metodológico nesse escopo. A Fase 2 foi
formalmente encerrada. O próximo bloco é `RAG_INTEGRATION_END_TO_END`, sem abrir
o HOLDOUT e sem alterar esta identidade congelada.
