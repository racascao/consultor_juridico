# Fase 91.11 — Structural Candidate Pool Replay & Selection Gate

O gate requer replay fiel de cada `PRIMARY_TOP10` histórico contra o corpus
relacional e a Evidence Selection real. A preparação confirmou que os artefatos
congelados preservam identidades/ranks, mas não os `chunk_id` necessários para
reconstruir os `RetrievalCandidate` sem consulta ao corpus. O container com
PostgreSQL existe, porém a imagem não contém os módulos experimentais mais
recentes e sua reconstrução foi bloqueada pelo filesystem do builder.

Nenhuma política foi integrada, nenhuma seleção foi alterada e não houve LLM,
E2E, Ollama ou alteração de dados. A fase permanece bloqueada até um build de
imagem funcional permitir o replay A/B/C completo.

## Retomada com corpus PostgreSQL real

A retomada preservou o registro acima como a primeira tentativa. A imagem
reconstruída confirmou os imports de `structural_expansion` e
`structural_budget`; `consultor-juridico db status` confirmou a revisão
`005_normative_identity_occurrences` no PostgreSQL Compose.

O harness somente-leitura
`evaluation/structural_pool_replay_91_11.py` reconstruiu os `PRIMARY_TOP10`
do artefato congelado da Fase 91.1 por `identity_key`, resolvendo no banco os
`chunk_id`, `legal_element_id` e `legal_provision_id` reais. Ele executou
somente as políticas congeladas: `BASELINE`, `STRUCTURAL_RESERVE_1` e
`STRUCTURAL_RESERVE_2`, com SECTION/SUBSECTION, até oito filhos e decay 0,85.

Para `rw-estado-sitio`, a SECTION II recuperada gerou CAPUTs reais para os
arts. 137, 138 e 139. O Art. 137 entrou em `STRUCTURAL_RESERVE_1` com score
`0.042578261845946555`; o Art. 138 entrou no reserve de tamanho 2. O selector
real, porém, não selecionou nenhum dos dois. A classificação é, portanto,
`STATE_SIEGE_FAILURE_LAYER=EVIDENCE_SELECTION`, não uma falha de expansão ou
de suficiência.

Em todas as políticas, os alvos selecionados permaneceram `8/10` e o controle
`rw-aborto` permaneceu `INSUFFICIENT`. O reserve 1 não alterou nenhuma seleção
final; o reserve 2 alterou uma seleção, sem recuperar o alvo de estado de
sítio. Os controles adversariais exigidos não possuem `PRIMARY_TOP10` congelado
no artefato histórico, portanto não foram reconstituídos sem executar novo
retrieval — o que seria metodologicamente inválido nesta fase.

Resultado: `STRUCTURAL_CANDIDATE_POLICY=NOT_PROVEN_FOR_PRODUCTION`,
`SELECTED_POLICY=NONE` e `STRUCTURAL_RETRIEVAL_PATH=NOT_READY_FOR_INTEGRATION`.
Não houve integração de Structural Expansion/Reserve, VCSA ou Atomic.
