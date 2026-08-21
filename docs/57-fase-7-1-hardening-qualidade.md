# Fase 7.1 — hardening de qualidade

## 1. Objetivo e gate

A Fase 7.1 separou suficiência, integridade estrutural e suporte semântico. O
gate permanece **`MVP1_QUALITY_BLOCKED`** porque Hybrid Hit@10 = 0,810, abaixo
do mínimo congelado de 0,90. A segurança de abstenção foi corrigida: os nove
casos de abstenção do dataset foram barrados antes do LLM, sem false abstention
no gate determinístico.

## 2. Blockers herdados

- Hybrid Hit@10 da Fase 7: 0,714;
- resposta indevida em 1/3 dos casos claramente fora do corpus;
- Citation Validator provava a cadeia física, mas não entailment.

## 3. Diagnóstico dos misses

Foram executados os 21 casos respondíveis antes de alterar retrieval. A
provision esperada aparecia, em diversos casos, forte em apenas um retriever;
o RRF com `k=60` privilegiava resultados medianos concordantes. Aumentar o pool
de 50 para 200 corrigiu dois misses sem alterar corpus ou benchmark.

Misses restantes após a rodada única:

| caso | classificação | evidência |
|---|---|---|
| `cf-equality` | `RRF_FUSION_MISS` + contexto de artigo | lexical rank 21; outro inciso do art. 5º em rank 2 |
| `cf-expression` | `BOTH_RETRIEVERS_MISS` | esperado lexical > 200 e vetorial 87 |
| `cf-amendment` | `RRF_FUSION_MISS` + contexto de artigo | lexical rank 22; § 1º do mesmo artigo em rank 8 |
| `cf-education` | `RRF_FUSION_MISS` | esperado vetorial rank 6, ausente no top-10 fundido |

Os padrões apontam para contextual retrieval/reranking ou revisão futura de
chunking. Não foram criadas regras por `case_id`, expansões de sinônimos do
dataset ou redução do threshold.

## 4. Retrieval before × after

| fase/modo | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR | Recall@10 |
|---|---:|---:|---:|---:|---:|---:|
| Fase 7 lexical | 0,476 | 0,571 | 0,667 | 0,667 | 0,548 | 0,667 |
| Fase 7 vector | 0,476 | 0,571 | 0,619 | 0,667 | 0,544 | 0,643 |
| Fase 7 hybrid | 0,524 | 0,667 | 0,714 | 0,714 | 0,591 | 0,690 |
| Fase 7.1 lexical | 0,476 | 0,571 | 0,667 | 0,667 | 0,548 | 0,667 |
| Fase 7.1 vector | 0,476 | 0,571 | 0,619 | 0,667 | 0,544 | 0,643 |
| Fase 7.1 hybrid | 0,524 | 0,667 | 0,714 | **0,810** | 0,603 | 0,786 |

Tempos dos 21 casos: lexical 0,19 s, vector 1,65 s e hybrid 1,96 s.

## 5. Evidence selection

Uma etapa determinística agora:

- preserva a ordem/ranks e a occurrence factual;
- deduplica por `LegalProvision`;
- usa overlap lexical apenas para remover ruído evidente;
- preserva sempre o primeiro resultado híbrido;
- limita o snapshot a três itens por default configurável.

Ela não declara entailment e não substitui os validators.

## 6. Evidence Sufficiency Gate

O gate ocorre antes da geração. Ele combina política explícita do escopo
CF/88 + ADCT, presença de candidatos e sinais lexical/vetorial observáveis.
Os limiares default (`vector >= 0,64` ou `lexical >= 0,30`) foram medidos no
dataset e permanecem conservadores; escopos explicitamente externos,
prompt-injection e perguntas pessoais subespecificadas falham fechados.

Resultado nos 30 casos: correct abstention 1,000; unsafe answer 0; false
abstention 0. Os três casos de culinária, futebol e Python terminaram em menos
de um segundo de decisão CLI cada, sem chamada generativa.

Na seleção final, a média caiu de 8 para 2,7 EvidenceItems; 0,667 das queries
respondíveis mantiveram a provision esperada no conjunto selecionado. Essa
queda confirma que selection depende da correção prévia do retrieval e não pode
compensar os quatro misses remanescentes.

## 7. Semantic Support Validator

O `Citation Validator` continua determinístico e estrutural. O novo validator
recebe somente cada Claim e suas evidências citadas e retorna:

- `SUPPORTED`;
- `PARTIALLY_SUPPORTED`;
- `UNSUPPORTED`.

Somente `SUPPORTED` pode ser persistido/entregue. O juiz local usa temperatura
zero e JSON Schema; timeout, contrato inválido, claim omitida ou evidence code
incompatível falham fechados. O schema de geração também restringe citations
aos códigos EV autorizados. Após no máximo duas tentativas, qualquer falha gera
abstenção e nenhuma Claim/Citation é persistida.

## 8. Testes adversariais

Os testes cobrem suporte integral, parcial, ausente, evidence code inventado,
claim omitida, erro técnico, evidência estruturalmente válida mas irrelevante,
selection determinística, provenance e os três domínios externos. Unsafe
claims delivered = 0 nos testes.

## 9. Artefatos

- `mvp1_v1_retrieval_7_1.json`;
- `mvp1_v1_quality_7_1.json`;
- `mvp1_v1_consultation_7_1.json`;
- `mvp1_v1_consultation_answerable_7_1.json`.

Os resultados da Fase 7 foram preservados.

## 10. Limitações e próxima decisão

O `llama3.2` como juiz semântico é conservador e adiciona latência. Uma
execução respondível foi abstida por classificação semântica excessivamente
restritiva, confirmando que o gate de segurança funciona, mas o answer rate
generativo ainda precisa de calibração humana. A integração opt-in de consulta
falhou por esse false abstention; evaluation e retrieval opt-in passaram. Como
retrieval segue abaixo de
0,90, a próxima revisão deve decidir entre contextual retrieval, reranker local
ou revisão do chunking. Nenhuma dessas arquiteturas foi iniciada aqui.

## 11. Gate final

`MVP1_QUALITY_BLOCKED`: segurança corrigida, qualidade de retrieval insuficiente.
