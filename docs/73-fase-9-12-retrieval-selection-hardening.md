# Fase 9.12 — Retrieval e seleção de evidências

## Objetivo

Eliminar os misses residuais de retrieval/seleção sem alterar o gerador, juiz
semântico, guard de polaridade, corpus, embeddings ou schema.

## Baseline

O `real_world_short_v1` tinha Hit@10 híbrido de 0,800. Os quatro diagnósticos
foram: idade para Presidente (miss de retrieval), e pena de morte, prisão
perpétua e voto obrigatório (evidência relevante fora da seleção final).

## Diagnóstico e experimentos

1. A classificação de consulta curta contava palavras funcionais. Assim,
   `idade para ser presidente` não recebia o tratamento de consulta curta,
   embora seus termos substantivos sejam apenas `idade` e `presidente`.
2. O serviço solicitava oito candidatos apesar de a estratégia de consulta
   curta poder produzir dez; a alínea relevante de pena de morte ficava fora
   desse pool.
3. A seleção observava somente o texto do chunk. Contexto factual do pai,
   como `não haverá penas:`, não participava do score.

Foram adotadas regras gerais e determinísticas: tokens substantivos para
classificação curta, carregamento em lote do contexto pai e seleção por
cobertura lexical, presença de contexto e posição híbrida. O limite de
evidências persistidas permanece o configurado (`3`); contexto é apenas sinal
de ranking e não altera snapshot, Chunk ou alvo de citação.

## Resultado de retrieval

| Dataset | Hybrid Hit@10 antes | Hybrid Hit@10 depois |
|---|---:|---:|
| real-world-short-v1 | 0,800 | 0,900 |
| mvp1-v1 | 0,905 | 0,905 |

O caso de idade passa a recuperar a alínea de elegibilidade. Pena de morte e
prisão perpétua passam a ter as alíneas corretas no conjunto selecionável; voto
obrigatório ainda depende de cobertura da alínea filha, que não aparece entre
os candidatos híbridos nesta rodada.

## Segurança e limites

Não houve mudança em retrieval vetorial, embeddings, datasets, thresholds,
attribution, validação de citações, guard de polaridade ou LLM. Não há
hardcode por artigo, consulta ou case id. A reavaliação end-to-end permanece o
critério de release; se ela ficar abaixo de 9/10, o release continua bloqueado
sem novo tuning nesta fase.

