# Plano do MVP2

## MVP2-F1 — Fundação Arquitetural

**COMPLETE.** Clean Architecture, contratos tipados, workflow LangGraph,
interrupt/resume, rotas e limites com fakes.

## MVP2-F2 — Core Funcional

**IMPLEMENTATION COMPLETE; MANUAL ACCEPTANCE PENDING.**

- Gate A — Corpus contextual: complete.
- Gate B — Retrieval FTS/vector/RRF: complete.
- Gate C — Consultation Model (`ANSWER | CLARIFY | ABSTAIN`): complete.
- Gate D — fluxo CPU-first com uma inferência direta: complete.
- Gate E — Citation/CLI vertical: complete.
- Gate F — Manual Acceptance: preparado, pendente do usuário.

As cinco regressões manuais mínimas são voto facultativo, alistamento militar,
alistamento ambíguo, promulgação e inviolabilidade da casa. O evaluator
`basic_direct_v1` mede o retrieval antes da avaliação científica da próxima
fase.

A aceitação manual da MVP2-F2 permanece aberta. A geração de candidatas passa a
fundir pools lexical/vetorial mais profundos e a priorizar diversidade de
famílias antes do top-10. Como essa mudança isolada não trouxe ganho material
no reteste, a auditoria causal levou à projeção contextual v2: CAPUT regente,
metadata rotulada e deduplicação exata ARTICLE/CAPUT. O rebuild e o benchmark
real dessa projeção ainda devem ser executados pelo usuário. A MVP2-F3 não foi
iniciada. O comando explícito de reprojeção por SHA de `SourceSnapshot` já está
disponível e não faz aquisição HTTP; o rebuild real continua pendente e não foi
executado pelo agente.

## MVP2-F3 — Validação e Release

**FUTURE.** Começa somente após aceitação explícita da MVP2-F2. Gates internos,
modelos, prompts, bugs e reruns não criam novas fases.
