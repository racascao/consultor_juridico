# TASKS — Consultor Jurídico

## MVP2 — Fase 0: Fundação e Corpus

- [x] Aprovar a Lei nº 9.784/1999 como ato piloto.
- [x] Isolar fisicamente o PostgreSQL v0.2 do banco legado.
- [x] Registrar a governança futura do HOLDOUT.
- [x] Investigar e documentar a fonte oficial.
- [x] Implementar baseline Alembic e schema mínimo v0.2.
- [x] Implementar aquisição condicional e snapshots imutáveis.
- [x] Implementar parser determinístico, cobertura fail-closed e fixtures.
- [x] Implementar projeção, materialização, reprojeção e auditoria.
- [x] Validar automaticamente o corpus real e a proveniência mecânica.
- [x] Concluir a validação manual de proveniência das cinco amostras.

Estado: concluída e aceita após validação manual de proveniência.

## MVP2 — Fase 1: Retrieval isolado

- [x] Criar, validar e congelar o DEV lexical com 40 casos.
- [x] Implementar o baseline PostgreSQL FTS com ActVersion explícita.
- [x] Executar uma única medição e congelar seu artefato.
- [x] Classificar genericamente as 40 falhas observadas.
- [x] Validar o strict com controle positivo 3/3.
- [x] Implementar e medir uma única vez a variante RELAXED_OR.
- [x] Classificar os oito misses restantes como diluição de ranking.
- [x] Diagnosticar os oito misses com lexemas PostgreSQL e cobertura lexical.
- [x] Implementar e medir uma única vez `RELAXED_OR_COVERAGE`.
- [x] Revisar o baseline e selecionar `RELAXED_OR_COVERAGE` para o piloto.

Estado: strict `Hit@10=0,000`/`MRR=0,000`; RELAXED_OR
`Hit@10=0,800`/`MRR=0,549`; RELAXED_OR_COVERAGE
`Hit@10=0,875`/`MRR=0,661`. Coverage recuperou três misses, não perdeu hits
top-10 e teve uma regressão de rank 5 para 6. Runtime, dataset e projeção estão
congelados após a medição. Fase concluída e commitada.

## MVP2 — Fase 2: Capacidade do modelo com Gold Evidence

- [x] Criar e validar o dataset DEV com 32 casos.
- [x] Materializar Gold Evidence a partir de `Provision` e `version_hash`.
- [x] Criar um prompt genérico e versionado sem vazamento de labels.
- [x] Exportar prompts provider-neutral em JSONL.
- [x] Implementar evaluator estrutural sem LLM judge.
- [x] Gerar template vazio de revisão humana.
- [x] Recusar consolidação enquanto houver revisão pendente.
- [x] Documentar o protocolo e os comandos de execução manual.
- [x] Selecionar `Qwen3-4B-Instruct-2507 Q4_K_M` como primeiro candidato.
- [x] Preparar o runner manual Ollama de avaliação.
- [x] Isolar Ollama no Docker Compose com volume persistente e profile `llm`.
- [x] Executar diagnóstico read-only das consultas sem evidência suficiente.
- [x] Usuário disponibilizar localmente o primeiro modelo.
- [x] Executar o primeiro run manual com o prompt v1.
- [x] Executar a avaliação automática estrutural v1.
- [x] Auditar em modo read-only o contrato de output v1.
- [x] Criar o prompt v2 limitado à clarificação do contrato de output.
- [x] Exportar o bundle provider-neutral do prompt v2 sem inferência.
- [x] Usuário executar o run manual com o prompt v2.
- [x] Executar a avaliação automática estrutural v2.
- [x] Auditar a regressão de prefixo de citation após o run v2.
- [x] Criar o prompt v3 limitado à clarificação do valor de citation.
- [x] Exportar e auditar o bundle provider-neutral do prompt v3 sem inferência.
- [x] Usuário executar o run manual com o prompt v3.
- [x] Executar a avaliação automática estrutural v3.
- [x] Classificar comparações single-seed de prompt como exploratórias.
- [x] Congelar prompt engineering e selecionar v2 para medir estabilidade.
- [x] Preparar o subset de estabilidade sem alterar a seleção predefinida.
- [x] Implementar seed configurável e sumário estrutural de estabilidade.
- [x] Usuário executar os três runs manuais do prompt v2.
- [x] Validar os três runs e gerar o sumário de estabilidade.
- [x] Confirmar o v2 como candidato final atual após a estabilidade.
- [x] Executar a revisão humana do candidato confirmado.
- [x] Definir o protocolo determinístico de estabilidade.
- [x] Executar o protocolo de estabilidade.
- [x] Documentar a rubrica e o procedimento auditável de revisão humana.
- [x] Auditar e separar as três classes de falha de citação observadas.
- [x] Preparar o diagnóstico pós-hoc de reprodutibilidade do `GOLD-012`.
- [x] Usuário executar `GOLD-012` nas seeds 42, 43 e 44.
- [x] Classificar `RISK-02` sem alterar o protocolo histórico.
- [ ] Usuário gerar as três avaliações automáticas pós-hoc de `GOLD-012` do primeiro Qwen.
- [x] Congelar o scorecard comparativo `RISK-01..RISK-08`.
- [x] Confirmar hardware e os quatro modelos no Ollama do Compose.
- [x] Congelar identidades, digests, quantizações e ordem dos candidatos.
- [x] Criar o manifest cross-model e verificar hashes dos inputs canônicos.
- [x] Preparar controle genérico de thinking e timeout de 180 segundos.
- [x] Preparar runbook manual para full, stability, GOLD-012 e human review.
- [x] Restaurar o isolamento PostgreSQL v0.2 após regressão não commitada do Compose.
- [x] Auditar replay isolado do bundle contra o oracle histórico (`32/32`).
- [x] Implementar `FrozenGoldBundleRepository` com validação de integridade.
- [x] Implementar namespace parcial de citações com política fail-closed.
- [x] Desacoplar o modo offline da criação de engine/sessão PostgreSQL.
- [x] Avaliar automaticamente o full run Qwen3.5 preservado, sem nova inferência.
- [ ] Recuperar o snapshot histórico `face6f55...` sem substituir o corpus congelado.
- [ ] Materializar e auditar o corpus no volume v0.2 reconstruído.
- [x] Executar estabilidade e probe `GOLD-012` do Qwen3.5.
- [x] Avaliar offline as três seeds de estabilidade e gerar seu sumário.
- [x] Confirmar `RISK-01` reproduzível e `RISK-02` correto em `3/3` no Qwen3.5.
- [x] Preparar o template Qwen3.5 de revisão humana com 32 casos e rubrica congelada.
- [x] Usuário concluir a revisão humana dos 32 casos full do Qwen3.5.
- [x] Consolidar a revisão Qwen3.5 sem LLM judge (`25/32` automático+humano).
- [x] Consolidar o scorecard `RISK-01..RISK-08` e rejeitar o Qwen3.5 como answerer final.
- [x] Verificar identidade e preparar o full run manual do Phi-4-mini.
- [x] Usuário executar e avaliar automaticamente o full run do Phi-4-mini (`21/32`).
- [x] Preparar stability e probe `GOLD-012` do Phi-4-mini nas seeds 42/43/44.
- [x] Usuário executar stability e probe `GOLD-012` do Phi-4-mini nas seeds 42/43/44.
- [x] Avaliar offline os seis runs e consolidar a estabilidade Phi (`7/12`).
- [x] Preparar a revisão humana do full Phi-4-mini e a ficha material separada de `GOLD-012`.
- [x] Usuário concluir e consolidar a revisão humana full do Phi-4-mini (`16/32` estrito).
- [x] Usuário concluir a ficha material dos três probes `GOLD-012` (`2/3`; falha de polaridade na seed 43).
- [x] Consolidar o scorecard e rejeitar o Phi-4-mini como answerer jurídico final.
- [x] Validar modelo, digest, inputs e comandos do início controlado do Gemma3.
- [x] Usuário executar full, stability e probes `GOLD-012` do Gemma3.
- [x] Avaliar offline os sete runs Gemma3 e consolidar a estabilidade (`11/12`).
- [x] Usuário concluir a revisão humana full e material do `GOLD-012` do Gemma3.
- [x] Consolidar o scorecard e rejeitar o Gemma3 como answerer jurídico final.
- [x] Validar modelo, digest, inputs e comandos do início controlado do Gemma4.
- [x] Usuário executar o Gemma4, último candidato restante, no protocolo cross-model v2.
- [x] Avaliar offline os sete runs Gemma4 e consolidar a estabilidade (`5/12` formal).
- [x] Usuário concluir a revisão humana full e material do `GOLD-012` do Gemma4.
- [x] Usuário preencher a revisão humana de cada candidato.
- [x] Consolidar o scorecard e classificar cada candidato.
- [x] Preparar suporte genérico e opt-in a `format=json` para reconsideração do Gemma4.
- [x] Congelar os sete comandos e artifacts de `GEMMA4_FORMAT_JSON_RECONSIDERATION_V1`.
- [x] Usuário executar manualmente os sete runs de reconsideração com `format=json`.
- [x] Validar hashes `7/7` e avaliar offline full, stability e `GOLD-012`.
- [x] Comparar formalmente baseline versus `format=json` sem emitir novo veredito.
- [x] Usuário preencher a revisão humana full e material de `GOLD-012` da reconsideração.
- [x] Consolidar scorecard, comparação final e aceitar Gemma4 com `format=json`.
- [x] Congelar a configuração selecionada e o runtime antes de RAG ou HOLDOUT.
- [x] Concluir revisão final da Fase 2.

Histórico consolidado da Fase 2: os runs v1/v2/v3 permanecem congelados em `19/32`,
`25/32` e `24/32`; as comparações single-seed continuam exploratórias. O
protocolo v2 observou decisão estável em `12/12`, variação de cobertura composta
em dois casos e de conjunto de citações em três. A revisão humana dos 32 outputs
foi concluída. `GOLD-029`/`GOLD-030` mantiveram clarificação perdida nas três
seeds; `GOLD-012` permaneceu fora do subset histórico. Seu diagnóstico pós-hoc
separado retornou `ABSTAIN` nas três seeds, portanto
`RISK-02` é reproduzível sob o prompt v2; as avaliações automáticas derivadas
ainda aguardam execução pelo usuário. O comportamento cross-prompt permanece
sensível porque v1 respondeu corretamente. O prompt canônico para comparar um
novo modelo permanece o v2, o scorecard `RISK-01..RISK-08` está congelado e
os candidatos `qwen3.5:9b`, `phi4-mini:3.8b-q4_K_M`, `gemma3:4b` e
`gemma4:12b` foram congelados nessa ordem, todos em Q4_K_M. Hardware, digests,
thinking, timeout, configuração e hashes estão no manifest; os comandos
manuais cobrem todos os pilares sem early stop. Ollama é provider somente da
avaliação; retrieval não participa do Gold Evidence e o HOLDOUT continua
fechado e não lido. O isolamento do Compose foi restaurado, mas a reconstrução
do corpus segue bloqueada porque a captura oficial de 3 de setembro de 2026
produziu SHA `c69120fb...`, diferente do snapshot histórico `face6f55...`. A
avaliação Gold congelada foi desacoplada desse bloqueio: o replay histórico
passou `32/32` e o full Qwen3.5 foi avaliado offline em `27/32`, sem nova
inferência. A estabilidade Qwen3.5 ficou em `11/12` decisões estáveis: a única
instabilidade foi o JSON inválido de `GOLD-032` na seed 43. `GOLD-029` e
`GOLD-030` responderam prematuramente nas três seeds (`RISK-01` reproduzível),
enquanto o probe `GOLD-012` respondeu corretamente com a citação
`ARTICLE:67/CAPUT` em `3/3`. A revisão humana foi consolidada em `25/32` passes
conjuntos. O scorecard final classificou o Qwen3.5 como `PARTIALLY_CAPABLE` e o
rejeitou como answerer jurídico final devido ao `RISK-01` reproduzível e de
severidade alta. O Phi-4-mini concluiu full automático (`21/32`), stability
(`7/12` decisões oficiais estáveis) e revisão humana full: correção jurídica
`26/32`, groundedness `28/32`, completude `18/32`, all-pass humano `17/32` e
interseção estrita automático+humano `16/32`. O probe `GOLD-012` teve `3/3`
passes formais, mas a revisão material confirmou somente `2/3`: a seed 43
inverteu a polaridade da norma. O scorecard classificou `RISK-01` como
`SAMPLING_SENSITIVE`, `RISK-02` como `OBSERVED` e rejeitou o Phi como answerer
jurídico final. Gemma3 completou os sete raw runs manuais. A avaliação offline registrou full em
`1/32`, `31/32` JSONs inválidos por Markdown fences preservados, estabilidade
formal de decisão em `11/12`, passes de `2/12`, `1/12` e `1/12`, e probe
`GOLD-012` formalmente inválido em `3/3`. A revisão humana ficou em `23/32`
para correção jurídica, `28/32` para groundedness, `19/32` para completude,
`18/32` all-pass e `1/32` estrito. O `GOLD-012` material passou em `3/3`.
O scorecard classificou o Gemma3 como `PARTIALLY_CAPABLE` e o rejeitou por
`RISK-01` reproduzível; a falha de contrato `31/32` também é desqualificante.
Gemma4, último candidato obrigatório, concluiu os sete raw runs manuais com
integridade `7/7`. A avaliação offline registrou full em `12/32`, JSON válido
em `13/32`, schema/decision payload em `12/32`, estabilidade formal em `5/12`
e passes por seed de `6/12`, `8/12` e `6/12`. A leitura de estabilidade é
limitada pelos outputs inválidos e decisões nulas. O probe `GOLD-012` passou
formal e materialmente em `3/3`. A revisão humana registrou `32/32` em correção
jurídica, `32/32` em groundedness, `29/32` em completude e `29/32` all-pass; a
interseção estrita automática+humana ficou em `12/32`. O scorecard não
reproduziu `RISK-01` ou `RISK-02`, observou `RISK-05` e classificou o candidato
como `RECONSIDER`: é o melhor resultado material, mas ainda não foi aceito como
answerer final devido a `20/32` falhas do contrato de output. Os quatro
candidatos foram caracterizados; naquele checkpoint, a Fase 2 seguiu aberta
para comparação final e seleção do modelo. Antes dessa decisão, foi preparado um único experimento
pós-cross-model: `GEMMA4_FORMAT_JSON_RECONSIDERATION_V1`. Ele mantém todo o
baseline congelado e acrescenta somente `format=json` ao request do Ollama. O
runner oferece a opção genérica `--ollama-format`, preserva o payload anterior
quando ela não é usada. Os sete runs foram executados manualmente pelo usuário e
avaliados offline: JSON válido `32/32`, schema/payload `31/32`, passe automático
`30/32`, cobertura obrigatória `32/32` e estabilidade formal `12/12`. Falharam
somente `GOLD-027` e `GOLD-031`; nenhum output foi reparado. O probe `GOLD-012`
passou em `3/3`. Naquele checkpoint automático, a revisão humana permanecia
pendente, sem conclusão sobre regressão material ou novo veredito. A revisão foi posteriormente
consolidada em `32/32` para correção jurídica, `32/32` para groundedness,
`29/32` para completude, `29/32` all-pass e `29/32` na interseção estrita. Sem
regressão material agregada, com estabilidade `12/12` e sem `RISK-01` ou
`RISK-02`, a configuração genérica `gemma4:12b + ollama_format=json` foi
`ACCEPTED`. Permanecem `RISK-05`, a falha de schema de `GOLD-027` e a decisão
de clarificação de `GOLD-031`. O freeze `gold-evidence-selected-answerer/1` foi
então concluído para `gemma4:12b`, digest exato, prompt v2, configuração de
geração, thinking desabilitado, `ollama_format=json`, contrato fail-closed e
artifacts de seleção. A validação é local e determinística. A Fase 2 continua
aberta para revisão final; o HOLDOUT permanece fechado e RAG não foi iniciado.

Revisão final: todos os gates canônicos da capacidade com Gold Evidence foram
confirmados e a Fase 2 foi encerrada. O corpus vivo `UNRESOLVED` não invalida o
experimento congelado e será tratado pelos gates do próximo estágio. Próximo
bloco: implementar o RAG end-to-end com retrieval, evidence assembly, answerer
congelado, Citation Validation e resposta rastreável; depois avaliar em DEV e
congelar o runtime integrado antes de abrir o HOLDOUT.

## MVP2 — Integração RAG

- [x] Integrar o retrieval `RELAXED_OR_COVERAGE` selecionado.
- [x] Montar Gold Evidence preservando ordem e `stable_key`.
- [x] Integrar e validar o freeze do answerer `gemma4:12b`.
- [x] Validar estritamente o contrato `ANSWER|ABSTAIN|CLARIFY`.
- [x] Rejeitar citações inválidas ou fora da evidência.
- [x] Expor resposta rastreável e trace opcional na CLI.
- [x] Criar diagnóstico read-only de readiness.
- [x] Cobrir o pipeline ponta a ponta com answerer mockado.
- [x] Preparar o corpus local versionado para smoke tests manuais.
- [x] Confirmar idempotência da materialização (`322` provisions; `242` SearchUnits).
- [x] Preparar cinco comandos de smoke test sem executar inferência.
- [x] Diagnosticar os primeiros smoke tests sem nova inferência.
- [x] Ponderar cobertura lexical pela raridade documental da `ActVersion`.
- [x] Expandir filhos normativos diretos com limites determinísticos.
- [x] Melhorar a categoria de erro do answerer sem retry automático.
- [x] Invalidar o smoke original de CLARIFY e preparar substituto apropriado.
- [x] Inspecionar GPU NVIDIA, driver e NVIDIA Container Toolkit do host.
- [x] Expor a GPU ao Ollama com `gpus: all`, preservando profile, porta e volume.
- [x] Confirmar acesso à GPU no container e detecção do backend CUDA pelo Ollama.
- [x] Revalidar tag/digest, freeze do answerer e readiness após a mudança de infraestrutura.
- [x] Usuário repetir os cinco smoke tests RAG manuais.
- [x] Executar a primeira medição Integrated DEV, sem Gold Evidence como input.
- [x] Congelar raw, avaliação automática, diagnóstico e template de revisão.
- [x] Concluir a revisão material humana do Integrated DEV (`24/32` all pass).
- [x] Analisar classes gerais de falha sem tuning oportunista.
- [x] Rejeitar a fusão lexical experimental por regressão global sem recuperar os misses.
- [x] Concluir que o gate factual determinístico não é justificável com o input atual.
- [x] Reconsiderar a arquitetura de factual sufficiency antes do freeze.
- [x] Selecionar `TWO_MODE_CONTRACT` como limite explícito e fail-closed do MVP2.
- [x] Implementar `LEGAL_RULE | CASE_APPLICATION` sem alterar o answerer congelado.
- [x] Validar `GOLD-027..032` como `CLARIFY` determinístico, sem retrieval/LLM.
- [x] Executar os dois smoke tests manuais do contrato de modos.
- [x] Preparar evaluator e mapping externo do Integrated DEV v2.
- [x] Usuário executar a campanha Integrated DEV v2 uma única vez.
- [x] Concluir a revisão humana v2 (`30/32` all pass).
- [x] Congelar o runtime integrado antes de abrir o HOLDOUT.
- [ ] Executar Blind Holdout contra o runtime integrado congelado.

Estado: implementação end-to-end concluída sem inferência real. O artifact
local versionado `b4abab2e...9261` foi materializado como `ActVersion`
`bfa031c3...8cc6`, com 322 provisions e 242 SearchUnits. A repetição foi
idempotente e o runtime reporta `RAG_READINESS=READY`. A identidade do snapshot
histórico perdido `face6f55...` permanece não verificada. Smoke tests, Integrated
DEV e HOLDOUT ainda não foram executados; o HOLDOUT continua fechado e não lido.
Nos primeiros smokes, delegação passou após uma falha transitória, a pergunta
fora do corpus absteve corretamente e o trace passou. O caso composto expôs
CAPUT sem incisos e termo discriminativo fora do top-10; o recurso intempestivo
expôs a mesma diluição lexical. A correção geral elevou o DEV lexical conhecido
para `Hit@10=0,900` e `MRR=0,740625`, sem LLM. O reteste permanece pendente.

O host NVIDIA e o NVIDIA Container Toolkit foram validados, e o serviço Ollama
agora recebe a GPU por `gpus: all`. O container detectou CUDA sem geração. O
timeout permaneceu em 180 segundos, sem retry; antes do reteste, o novo smoke de
clarificação estava `INCONCLUSIVE_DUE_TO_TIMEOUT`.

Com CUDA ativo, os smokes ficaram suficientes para o próximo gate. A primeira
campanha Integrated DEV executou os 32 casos uma vez: `24/32` automatic pass,
`25/32` decisões esperadas, zero citação inválida, zero citação fora da evidência
e zero resposta insegura nos casos insuficientes. Foram isolados dois
`RETRIEVAL_MISS` e seis `ANSWERER_DECISION_FAILURE` nos casos ambíguos. Naquele
checkpoint, a revisão material humana e o freeze ainda estavam pendentes.

A revisão humana confirmou `30/32` em correção jurídica, `32/32` em grounding,
`24/32` em completude e `24/32` all pass. A análise causal mostrou um mismatch
lexical em `GOLD-003` e diluição multipart em `GOLD-016`. A fusão lexical geral
testada piorou Hit@10/MRR e não recuperou os alvos. Para clarificação, não há no
input atual um modelo estrutural de fatos necessários/ausentes; nenhuma
heurística frágil foi adicionada. O runtime permanece sem fix e sem freeze.

A tag `v0.1.0` permanece congelada, e a primeira tentativa do MVP2 está
preservada somente no histórico Git.
