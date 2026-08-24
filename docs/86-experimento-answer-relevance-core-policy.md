# Experimento offline — Answer Relevance e Core Answer Policy

## Objetivo

Este experimento testa uma boundary de adequação da resposta sobre as saídas
congeladas da Fase 12. Não houve nova chamada a Generator, Semantic Judge,
retrieval ou banco; não há integração no `ConsultationService`.

A hipótese é que uma claim só pode originar uma resposta quando já for
validada pelos gates anteriores e também for relevante e central para a
pergunta. Uma claim auxiliar pode complementar uma claim central, mas nunca
produz `ANSWERED` isoladamente.

```text
validated claim
    + relevance to query
    + central role
    -> eligible to originate ANSWERED
```

## Desenho

O harness [`evaluation/relevance_core_86.py`](../evaluation/relevance_core_86.py)
consome exclusivamente:

- `evaluation/results/evidence_bound_12_ab.json`;
- `evaluation/results/evidence_bound_12_frozen_evidence_sets.json`.

Cada claim já aprovada recebe uma decisão transitória e auditável:

- `RELEVANT` — os termos materiais da pergunta são cobertos pela claim e/ou
  pelos fragmentos autorizados;
- `IRRELEVANT` — falta cobertura material explícita;
- `UNRESOLVED` — há introdução de sujeito institucional capitalizado em uma
  construção deôntica, mas esse sujeito não aparece nos fragmentos.

O papel é `CENTRAL`, `AUXILIARY` ou `UNRESOLVED`. Apenas `RELEVANT + CENTRAL`
pode originar resposta. A camada não valida suporte, não promove claim, não
substitui Citation/Qualifier/Polarity/Semantic Validation e não conhece
`case_id`, artigo, provision esperada ou corpus.

Os únicos sinais negativos aplicados são deliberadamente estreitos:

1. cobertura explícita dos termos materiais, com tolerância apenas para flexão
   terminal regular;
2. sujeito capitalizado que recebe poder/dever explícito, porém está ausente do
   fragmento autorizado;
3. tópico aparecendo só em oração temporal/subordinada;
4. claim de localização documental sem proposição normativa central.

Não há dicionário de sinônimos, regra por artigo ou regra por consulta.

## Resultado A/B

| Métrica | A — Fase 12 | B — relevance + core |
|---|---:|---:|
| respostas inseguras/off-target | 2 | 0 |
| regressões históricas corretas | — | 0 |
| prisão perpétua off-target | sim | não; abstenção |
| estado de sítio off-target | sim | não; abstenção |
| pena de morte | abstenção | mesma abstenção |

Os sete casos historicamente corretos permaneceram respondidos. Em particular,
o termo `religiosa` é encontrado no fragmento autorizado de liberdade de
consciência e de crença; isso é cobertura factual do slot, não um sinônimo
introduzido pelo algoritmo.

### Prisão perpétua

As claims sobreviventes mencionavam prisão, comunicação ao juiz e imunidade
parlamentar, mas não cobriam `perpétua`. Ambas foram `IRRELEVANT + AUXILIARY`;
a ausência da claim central válida agora leva a `ABSTAINED`.

### Estado de sítio

A claim que atribuía competência ao Congresso foi `UNRESOLVED`, pois o ator
capitalizado não constava nos fragmentos do slot. A claim sobre relatório após
o término foi `RELEVANT + AUXILIARY`, e a claim sobre capítulo/título foi
também auxiliar. Sem claim central, o resultado é abstenção. Isso corrige a
segurança da saída, mas não recupera o caso: a causa primária continua sendo
retrieval insuficiente dos arts. 137/138.

### Pena de morte

O experimento não altera o diagnóstico da Fase 12: a falha permanece um falso
negativo de entailment/validação semântica para uma claim que preservava a
exceção de guerra declarada.

## Controles

Passaram dez controles sintéticos:

- `TRUE_BUT_IRRELEVANT`;
- `SUPPORTED_BUT_OFF_TARGET`;
- `WRONG_LEGAL_ACTOR`;
- `RELATED_PROVISION_WRONG_ANSWER`;
- `PARTIAL_TRUE_ANSWER_TO_BINARY_QUERY`;
- `AUXILIARY_FACT_WITHOUT_CORE_ANSWER`;
- `CENTRAL_CLAIM_REJECTED_AUXILIARY_SURVIVES`;
- `VALID_ALTERNATIVE_PROVISION`;
- `RELEVANT_BUT_UNSUPPORTED`;
- `SUPPORTED_AND_RELEVANT`.

Os dois últimos deixam explícito que esta boundary não é um validador de
suporte: uma claim relevante ainda precisa passar pelos gates anteriores.

## Limites

O resultado demonstra uma boundary segura para os traces congelados; não prova
entendimento semântico geral. Casos de paráfrase que não preservem termos no
slot podem resultar em `IRRELEVANT` ou `UNRESOLVED`, de forma fail-closed. A
classificação de centralidade também não repara retrieval ausente, nem torna
uma claim semanticamente correta.

Logo, esta fase valida a separação conceitual `Evidence -> Claim` versus
`Query -> Claim`, mas não autoriza integração em produção por si só.

## Recomendações para o working tree

| Componente | Recomendação |
|---|---|
| SupportSlot | `KEEP_FOUNDATION` |
| Evidence-Bound Generation | `KEEP_EXPERIMENTAL` |
| parent provenance | `KEEP_FOUNDATION` |
| qualifier preservation | `KEEP_FOUNDATION` |
| completeness policy | `REWORK` |
| marginal selection | `KEEP_EXPERIMENTAL` |
| clause attribution | `LEGACY_ONLY` |
| semantic adaptations | `KEEP_FOUNDATION` |
| evaluation harness | `REWORK` |

Nenhum revert foi executado. Antes de qualquer integração futura, a direção
recomendada é congelar o contrato de adequação e testar uma
`VERIFIED_CORE_SUPPORT_ASSERTION`, capaz de formar uma afirmação central a
partir dos fragmentos já verificados, sem geração livre nem expansão de corpus.

## Artefato

O resultado bruto reproduzível está em
`evaluation/results/relevance_core_86.json`.

## Decisão

`ANSWER_RELEVANCE_DIRECTION: VALIDATED` para uso experimental. Produção segue
`NOT_ENABLED`.
