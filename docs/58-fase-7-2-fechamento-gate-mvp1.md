# Fase 7.2 — fechamento do gate do MVP1

## 1. Objetivo e resultado

A Fase 7.2 executou uma rodada corretiva final sobre retrieval e validação
semântica. O retrieval superou o limiar: Hybrid Hit@10 passou de 0,810 para
0,905. A segurança permaneceu fail-closed, com zero aceitações inseguras no
dataset semântico e zero respostas nos nove casos de abstenção.

O gate global permanece **`MVP1_QUALITY_BLOCKED`**. Embora a integração de
consulta conhecida passe, uma amostra adicional com três perguntas diretas
resultou em três abstenções. O `llama3.2` local continua excessivamente
conservador/inconsistente como gerador e juiz para o aceite técnico final.

## 2. Baseline e artefatos

- dataset jurídico congelado: `mvp1-v1`, 30 casos (21 respondíveis e 9 de
  abstenção);
- corpus: CF/88 + ADCT, 3.389 chunks e 3.389 embeddings;
- embeddings: `nomic-embed-text:latest`, 768 dimensões;
- geração e juiz semântico: `llama3.2:latest`;
- Granite 4.1 3B não estava instalado e não foi baixado;
- Alembic: `005_normative_identity_occurrences`;
- captura preservada: 1.839.482 bytes, SHA-256
  `25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d`.

Resultados novos foram gravados sem sobrescrever os históricos:

- `evaluation/results/mvp1_v1_retrieval_7_2.json`;
- `evaluation/results/mvp1_v1_quality_7_2.json`;
- `evaluation/results/semantic_judge_llama3_2_before_7_2.json`;
- `evaluation/results/semantic_judge_7_2.json`;
- `evaluation/results/mvp1_v1_consultation_7_2.json`.

## 3. Diagnóstico dos quatro misses

| caso | provision esperada | causa raiz na 7.1 | alteração geral | resultado 7.2 |
|---|---|---|---|---|
| `cf-equality` | art. 5º, caput | CAPUT lexical 21; inciso XXIV do mesmo artigo vetorial 1 | expansão lexical disjuntiva, pool 200 e promoção contextual de CAPUT | híbrido rank 3 |
| `cf-expression` | art. 5º, IV | “expressar opiniões” não coincide com “manifestação do pensamento”; ambos os retrievers falham | nenhuma expansão jurídica ad hoc | permanece miss |
| `cf-amendment` | art. 60, caput | § 1º do mesmo artigo vetorial 13; CAPUT fora do top-10 | promoção contextual limitada a CAPUT já recuperado no top-30 de um componente | híbrido rank 9 |
| `cf-education` | art. 205, caput | vetorial rank 6, mas sinais concordantes de outros dispositivos passam à frente no RRF | pool ampliado e fusão contextual | permanece fora do top-10 |

As occurrences esperadas têm texto factual preservado: igualdade (“Todos são
iguais perante a lei…”), expressão (“é livre a manifestação do pensamento…”),
emenda (“A Constituição poderá ser emendada mediante proposta:”) e educação
(“A educação, direito de todos…”). Os chunks mantêm ato, `identity_key` e texto
autoritativo; não houve alteração de conteúdo nem duplicação ARTICLE/CAPUT.

O candidate pool já é deduplicado por chunk e a seleção de evidência é
deduplicada por `LegalProvision`. A causa dos dois casos corrigidos não era
duplicação de provision, mas a perda do CAPUT relevante quando somente um
descendente do mesmo artigo tinha sinal forte. O reranking registra
`contextual_score`, preserva o RRF original e somente promove um CAPUT que já
aparece até a posição 30 lexical ou vetorial. Não há regra por `case_id`, artigo
ou texto constitucional.

## 4. Retrieval antes e depois

| métrica hybrid | 7.0 | 7.1 | 7.2 |
|---|---:|---:|---:|
| Hit@1 | 0,524 | 0,524 | 0,524 |
| Hit@3 | 0,667 | 0,667 | 0,714 |
| Hit@5 | 0,714 | 0,714 | 0,810 |
| Hit@10 | 0,714 | 0,810 | **0,905** |
| MRR | 0,591 | 0,603 | 0,627 |
| Recall@10 | 0,690 | 0,786 | 0,881 |

Na 7.2, lexical e vector mantiveram Hit@10 = 0,667. Tempos totais nos 21 casos:
lexical 0,18 s, vector 1,72 s e hybrid 2,01 s. O ganho é da fusão contextual,
não de novo embedding, alteração de corpus ou ajuste do threshold.

## 5. Evidence selection e abstenção

Nos 30 casos, a seleção manteve média de 2,67 EvidenceItems, duplicação média
por provision igual a zero e a provision esperada em 0,762 das seleções
respondíveis (0,667 na 7.1). Os nove casos de abstenção foram corretamente
recusados antes da geração: correct abstention = 1,000, unsafe answer = 0 e
false abstention do gate determinístico = 0.

## 6. Dataset e contrato do juiz semântico

Foi criado `semantic-support-v1` com 20 casos manuais: literal, paráfrase,
inferência direta, múltiplas evidências, claim ampla, detalhe inventado,
irrelevância, contradição, negação e quantificador absoluto. O juiz recebe
somente Claim e EvidenceItems citados.

O contrato passou a decompor a decisão em três booleanos — existência de
material sustentado, suporte integral e contradição — e a aplicação deriva
`SUPPORTED`, `PARTIALLY_SUPPORTED` ou `UNSUPPORTED`. Combinações inválidas,
timeout, JSON inválido e evidence IDs incompatíveis falham fechados. Uma
aprovação do modelo sem nenhuma âncora lexical material é somente vetada; esse
sinal determinístico nunca promove uma claim.

| execução `llama3.2` | accuracy | precision SUPPORTED | recall SUPPORTED | unsafe acceptance | falsos bloqueios potenciais | contrato inválido | média | p50 | p95 observado |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| antes | 0,450 | 1,000 | 0,375 | 0 | 5 | 0 | 10,93 s | 9,42 s | 17,11 s |
| depois | 0,700 | 1,000 | 0,750 | 0 | 2 | 0 | 11,07 s | 12,28 s | 14,99 s |

Granite não foi comparado porque somente `llama3.2:latest` e
`nomic-embed-text:latest` estavam instalados. O gerador continua configurável
por `OLLAMA_MODEL`; o juiz, por `SEMANTIC_JUDGE_MODEL`, com fallback explícito
ao gerador.

## 7. Consulta real local e false abstention

A integração opt-in original com a pergunta “O que a Constituição estabelece
sobre a manifestação do pensamento?” passou de ponta a ponta, persistindo
cadeia validada. O teste preservou a pergunta histórica de regressão; não foi
substituído por um caso mais fácil.

Uma amostra adicional, estratificada por categoria `direct`, executou
`cf-equality`, `cf-objectives` e `cf-principles-international`. Resultado:
0/3 respondidas, 3 false abstentions e 0 unsafe answers. As causas observadas
foram abstenção explícita do gerador e decisões `PARTIALLY_SUPPORTED`
inconsistentes do juiz. O contrato de geração foi limitado a quatro claims,
textos curtos e evidências diretamente relacionadas, eliminando truncamentos
observados numa execução anterior, mas não o conservadorismo residual.

## 8. Segurança, regressões e limitações

- unsafe answers nos nove casos de abstenção: 0;
- unsafe claims delivered nos testes adversariais: 0;
- citações estruturalmente inválidas aceitas: 0;
- claims semânticas incompatíveis aceitas no benchmark: 0;
- Citation Validator e Semantic Support Validator permanecem obrigatórios;
- a avaliação local não prova segurança absoluta;
- `cf-expression` sugere necessidade futura de embedding melhor, query
  expansion controlada ou reranker local;
- o principal blocker é a taxa de false abstention generativa/semântica do
  `llama3.2`, não latência do retrieval.

## 9. Gate final

O gate de retrieval foi aprovado, mas o gate global não. A rodada coerente de
calibração terminou sem aceitação insegura e sem enfraquecer o fail-closed;
prosseguir com tuning ilimitado ou baixar outro modelo contrariaria o escopo.

**`MVP1_QUALITY_BLOCKED`**: recomenda-se, sob revisão humana, disponibilizar e
comparar outro juiz semântico local (Granite 4.1 3B foi o candidato previsto)
antes de iniciar a Fase 8.
