# Fase 9.7 — Attribution determinística pós-geração

## Escopo

Foi implementado e avaliado um protótipo puro de atribuição posterior à
geração. Ele não foi conectado ao `ConsultationService`.

O protótipo recebe somente `GeneratedResponse` e `EvidenceItems` do mesmo
`EvidenceSet`. Não consulta o corpus, não cria IDs, não usa LLM e preserva os
snapshots/proveniência.

## Algoritmo

Para cada claim:

1. normaliza Unicode, caixa e inflexões por prefixo curto;
2. remove palavras funcionais, sem lista de sinônimos jurídicos;
3. combina `text_snapshot`, `parent_context` e identidade estrutural já presente
   no metadata do item;
4. calcula cobertura lexical ponderada pela raridade do token no próprio
   EvidenceSet;
5. seleciona somente IDs com cobertura e margem suficientes;
6. se não houver atribuição inequívoca, retorna claims vazias com abstention.

O algoritmo nunca escolhe um item arbitrariamente. Claims compostas podem usar
mais de um item quando cada item acrescenta cobertura material suficiente.

## Testes sintéticos

Foram cobertos:

- evidência claramente sustentadora;
- evidências tematicamente próximas;
- claim composta;
- ausência de evidência suficiente;
- uso de `parent_context`;
- preservação de abstention.

Os cinco testes focais passaram.

## Benchmark real

As evidências foram congeladas uma vez por caso e o gerador foi executado cinco
vezes para cada:

- `rw-pena-morte`;
- `rw-prisao-perpetua`;
- `rw-voto-obrigatorio`.

O juiz atual recebeu a resposta após a atribuição determinística. Resultado:

| Caso | Atribuição direta | Resultado combinado |
|---|---:|---:|
| pena de morte | 4/5 | 4 respondidas, 1 abstention |
| prisão perpétua | 4/5 | 4 respondidas, 1 abstention |
| voto obrigatório | 5/5 | 5 respondidas |

Artefato completo com saídas brutas:

`evaluation/results/variance_9_7_deterministic.json`

## Falha decisiva

Em `prisão perpétua`, a atribuição determinística selecionou corretamente o
fragmento da alínea B, mas o juiz semântico aceitou a claim incorreta de que a
prisão perpétua seria permitida. O algoritmo resolveu a identidade da evidência,
mas não resolve polaridade, negação ou verdade material da claim.

Logo, attribution correta não é suficiente para cumprir `unsafe_answers = 0`.
Alterar o protótipo para inferir proibição/perm​​issão seria implementar lógica
semântica fora do escopo desta fase e duplicaria o juiz.

## Gate

```text
DETERMINISTIC_ATTRIBUTION_GATE: BLOCKED
```

Embora os limiares de attribution por caso tenham sido atingidos, o requisito
de segurança não foi demonstrado. O protótipo não foi adotado em produção.

Retrieval, selection, sufficiency, embeddings, semantic judge, thresholds,
dataset e schema permanecem inalterados. O MVP1 Hit@10 histórico permanece
0,905 e as abstenções históricas não foram reexecutadas nem alteradas.

## Próxima intervenção única recomendada

Investigar uma validação semântica fail-closed específica para polaridade e
negação entre claim e evidência, mantendo o juiz atual como componente separado.
Não promover o protótipo de attribution isoladamente.
