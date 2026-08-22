# Diagnóstico de variância do gerador e do juiz semântico

## 1. Escopo

Este diagnóstico selecionou somente os três casos classificados como
intermitentes na Fase 9.4:

- `rw-pena-morte`;
- `rw-prisao-perpetua`;
- `rw-voto-obrigatorio`.

Não houve alteração de retrieval, dataset, thresholds, embeddings ou ranking.
Cada caso teve seu conjunto de evidências recuperado uma única vez e congelado
em memória. Sobre esse mesmo snapshot foram executados:

1. cinco ciclos do gerador;
2. cinco ciclos do juiz sobre a mesma resposta canônica do gerador;
3. cinco ciclos combinados, julgando individualmente cada saída do gerador.

Os payloads completos, conteúdos brutos e metadados de tempo do Ollama estão em:

- `evaluation/results/variance_9_5_before.json`;
- `evaluation/results/variance_9_5_after.json`.

O harness reproduz os prompts, schemas, modelos e opções usados em produção,
inclusive `temperature=0`. O `EvidenceSet` temporário usado para formar o
snapshot sofre rollback; o diagnóstico não persiste consultas.

## 2. Definição da taxa de flip

A taxa registrada é a discordância entre todos os pares de execuções:

```text
pares com assinaturas diferentes / C(N, 2)
```

Para o gerador, a assinatura exata contém texto das claims e evidence IDs. Para
o juiz, contém os status por claim. Para o pipeline combinado, contém o desfecho
`ANSWERABLE`, `REJECTED_BY_JUDGE` ou `ABSTAINED_BY_GENERATOR`.

Uma diferença apenas de maiúsculas/minúsculas conta como variação textual do
gerador, mas é indicada separadamente quando não altera claims ou citações.

## 3. Resultado antes da correção

| Caso | Gerador | Juiz isolado | Combinado | Observação |
|---|---:|---:|---:|---|
| pena de morte | 40% | 0% | 0% | duas formas de claims/citações; 5/5 recusadas |
| prisão perpétua | 40% | 0% | 40% | 4/5 aceitas e 1/5 recusada |
| voto obrigatório | 0% | não executado | 0% | 5/5 abstenções do gerador |

### Comparação de texto, claims e citações

- `pena de morte`: duas assinaturas distintas. O gerador acrescentou sempre uma
  segunda claim irrelevante ou não sustentada e variou os evidence IDs.
- `prisão perpétua`: duas assinaturas distintas. Em quatro execuções afirmou
  incorretamente que a prisão **pode** ser perpétua e citou o fragmento
  `de caráter perpétuo;`; em uma execução produziu outra síntese, recusada.
- `voto obrigatório`: nenhuma claim ou citação foi produzida nas cinco
  execuções.

O juiz isolado foi estável para as claims canônicas escolhidas nessa primeira
rodada. Isso não significava correção: sem o contexto do pai, ele aceitou 5/5 a
claim incorreta sobre prisão perpétua.

## 4. Causa reproduzível identificada

O contexto hierárquico era encaminhado de forma assimétrica:

- ALINEA/ITEM recebiam `parent_context` no prompt do gerador;
- INCISO não recebia o texto do pai;
- o juiz semântico recebia somente `text_snapshot`, nunca `parent_context`.

Isso foi comprovado nos snapshots:

- prisão: `de caráter perpétuo;` sem `não haverá penas:` permitiu ao juiz aceitar
  a inversão do sentido normativo;
- voto: `obrigatórios para os maiores de dezoito anos;` precisava do pai
  `O alistamento eleitoral e o voto são:` para formar uma proposição completa.

A causa é geral, reproduzível e corrigível sem tocar retrieval. Foi implementada
a correção mínima:

1. `parent_context` também é capturado para INCISO;
2. o juiz recebe o mesmo contexto estrutural factual disponível ao gerador.

O snapshot citável (`text_snapshot`) permanece inalterado.

## 5. Revalidação após a correção

| Caso | Gerador | Juiz isolado | Combinado | Distribuição combinada |
|---|---:|---:|---:|---|
| pena de morte | 40% | 0% | 40% | 1 aceita / 4 recusadas |
| prisão perpétua | 40% | 40% | 40% | 4 aceitas / 1 abstenção |
| voto obrigatório | 40% textual | 0% | 0% | 5 recusadas |

Em `voto obrigatório`, a variação de 40% do gerador foi apenas capitalização de
`inciso/artigo`; claims e evidence IDs foram semanticamente idênticos. A mudança
relevante foi a geração deixar de se abster: 5/5 execuções produziram a claim
correta após receber o contexto do INCISO.

## 6. Causa residual

A revalidação revelou duas causas residuais distintas:

1. **Mapeamento instável claim → evidence ID pelo gerador.** Em `voto`, a claim
   foi derivada de `EV004`, mas o modelo citou `EV003` e `EV001` nas cinco
   execuções. O juiz recusou corretamente 5/5. Em `pena`, textos e evidence IDs
   também variaram e misturaram dispositivos não responsivos.
2. **Variância real do juiz em claim fixa.** Em `prisão`, a mesma resposta
   canônica recebeu `SUPPORTED+SUPPORTED+SUPPORTED` em 4/5 execuções e
   `PARTIALLY_SUPPORTED+SUPPORTED+PARTIALLY_SUPPORTED` em 1/5, taxa de flip de
   40%.

Essas causas não têm, neste ponto, correção mecânica comprovada que respeite as
restrições da fase. Alterar prompt, seleção de evidências, limite, threshold ou
ranking apenas para obter o gate seria tuning sobre três casos. Nenhuma segunda
correção foi implementada.

## 7. Conclusão

O diagnóstico refuta a hipótese de que toda a oscilação vinha apenas do juiz.
Há três fenômenos:

- composição estrutural incompleta de evidências, corrigida de forma geral;
- geração variável e atribuição incorreta de evidence IDs;
- julgamento semântico variável para uma claim fixa em `prisão`.

A segurança fail-closed continuou operante nos casos em que as citações ou o
suporte foram recusados. Os resultados não justificam alterar thresholds nem
aprovar o release gate com base nesta amostra.
