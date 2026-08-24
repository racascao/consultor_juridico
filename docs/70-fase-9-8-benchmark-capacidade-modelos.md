# Fase 9.8 — Benchmark de capacidade dos modelos locais

## Resultado

`MODEL_CAPABILITY_GATE: INCONCLUSIVE`

`INCONCLUSIVE`

O pipeline de produção não foi alterado. Retrieval, selection, sufficiency,
embeddings, Semantic Judge, thresholds, datasets, schema e `attribution.py`
permanecem inalterados.

## Baseline e bloqueio

Ruff format/check passaram e os cinco testes focais de attribution passaram.
Os três modelos foram posteriormente disponibilizados no container. Um erro
mecânico no harness foi identificado: generator e Semantic Judge compartilhavam
a mesma variável. O harness foi corrigido separando explicitamente os modelos e
as matrizes Granite 3B e Granite 8B foram reiniciadas integralmente.

O Semantic Judge permaneceu congelado em `granite4.1:3b`.

Resultados válidos parciais:

| Modelo | Pena | Prisão perpétua | Voto | Observação |
|---|---:|---:|---:|---|
| Granite 3B | 5/5, mas unsafe aceito | 0/5 | 5/5 | Judge aceitou inversão em prisão |
| Granite 8B | 5/5 | 0/5, abstention determinística | 1/5 | voto facultativo em 4/5 |

Latência do generator (15 execuções): Granite 3B média 26,27 s, p50 22,07 s,
p95 45,05 s; Granite 8B média 58,40 s, p50 50,46 s, p95 118,36 s.

No Granite 3B, o Semantic Judge aceitou a inversão de polaridade da claim de
prisão perpétua em 5/5 execuções (`SUPPORTED`). No Granite 8B, quatro claims de
voto facultativo foram aceitas pelo judge como respondíveis, embora incorretas;
o protótipo determinístico absteve-se no caso de prisão perpétua.

O generator attribution do Granite 3B foi correto apenas no dispositivo de
prisão (5/15 no conjunto dos três casos); a attribution determinística
reatribuiu corretamente os casos de pena e voto. O Granite 8B melhorou a
atribuição direta em pena e prisão, mas ainda errou quatro das cinco execuções
de voto.

O Gemma 12B foi iniciado com o protocolo congelado, mas a primeira consulta
excedeu o timeout configurado. No complemento controlado, o timeout exclusivo
do harness foi elevado de 180 s para 600 s, sem alterar `CONSULTATION_TIMEOUT`
de produção. Mesmo assim, a execução permaneceu impraticável no ambiente CPU
(aproximadamente 1,9 tokens/s observado) e foi encerrada antes da primeira
consulta completar. Como não houve as 15 execuções completas, o benchmark
principal permanece inconclusivo.

## Protocolo preservado

O protocolo planejado continua sendo cinco repetições por caso (`rw-pena-morte`,
`rw-prisao-perpetua`, `rw-voto-obrigatorio`), com evidências congeladas da Fase
9.7 e Semantic Judge fixo. Os resultados da Fase 9.7 continuam apenas como
baseline histórico, não como resultado deste benchmark.

## Decisão

Os dados parciais já mostram que Granite 3B mantém uma aceitação insegura de
polaridade e que Granite 8B reduz a exposição por abstention, mas ainda erra o
caso do voto. Não é possível escolher modelo default nem fechar a comparação
8B→12B. A próxima ação única é repetir somente a matriz Gemma 12B com o mesmo
timeout ou, se o timeout for estruturalmente insuficiente para esse modelo,
registrar formalmente a incapacidade operacional. Não implementar Polarity
Guard com base em uma comparação incompleta.

O erro do harness e a reinicialização integral das matrizes estão registrados
nos artefatos JSON; nenhum resultado da execução inválida foi usado nas métricas.

O complemento Gemma não produziu novas métricas válidas nem alterou os dados
brutos anteriores.

## Complemento Edge E2B/E4B

O teste `gemma4:e2b` foi iniciado, mas falhou antes da primeira matriz
completar porque o Semantic Judge congelado (`granite4.1:3b`) não estava
presente no volume Ollama atual; `/api/chat` retornou HTTP 404. O teste
`gemma4:e4b` não foi iniciado pelo mesmo motivo. Não foi utilizado outro judge
e não houve download automático. Portanto, não existem resultados válidos para
os modelos Edge.

Na continuação, o Granite 3B foi disponibilizado e as duas configurações Edge
foram executadas separadamente:

| Configuração | Pena | Prisão perpétua | Voto | Observação |
|---|---:|---:|---:|---|
| E2B generator + Granite judge | 4/5 | 1/5 | 4/5 | quatro false abstentions em prisão; uma claim extra nos demais casos |
| E4B generator + E2B judge | 0/5 | 5/5 | 0/5 | contratos inválidos/JSON inválido em pena e voto |

O E2B como judge marcou a claim correta de prisão como `SUPPORTED`, mas não foi
executado um benchmark semântico independente `semantic_support_v1`. A
configuração completa E4B+E2B não atende ao gate por taxa de contrato inválido,
mesmo sem unsafe acceptance observada.

O harness recebeu apenas correções mecânicas para registrar respostas JSON ou
contratos inválidos como falhas, invalidar a execução correspondente e permitir
que a matriz continue. As matrizes afetadas foram reiniciadas integralmente.

## Fase 9.9 — Granite 8B + Granite 8B

Foram executadas 15 repetições com `granite4.1:8b` simultaneamente como
generator e Semantic Judge.

| Caso | Claims corretas | Deterministic attribution | Judge | Resultado |
|---|---:|---:|---:|---|
| Pena de morte | 4/5 | 4/5 não abstidas | SUPPORTED 5/5 | 4 respondidas |
| Prisão perpétua | 0/5 | abstention 5/5 | não chamado | 5 abstentions |
| Voto obrigatório | 0/5 | 4 respostas atribuídas | UNSUPPORTED 5/5 | 4 rejeitadas |

O judge 8B rejeitou corretamente as claims de voto facultativo (`UNSUPPORTED`)
e não aceitou unsafe answers. Porém, a claim de prisão permaneceu semanticamente
insuficiente e houve false abstention determinística em 5/5. A inversão de
voto continuou sendo produzida em 4/5, embora rejeitada pelo judge.

Latência total da matriz: 2.351,56 s. O ganho de segurança do judge não elimina
o problema de geração nem satisfaz o gate.

Artefatos:

- `evaluation/results/model_capability_9_8_granite41_3b.json`
- `evaluation/results/model_capability_9_8_granite41_8b.json`
- `evaluation/results/model_capability_9_8_gemma4_12b.json` (execução técnica
  incompleta por timeout; não usado como benchmark válido)
- `evaluation/results/model_capability_9_8_summary.json`

Nenhum commit ou push foi criado.
