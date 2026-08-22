# Fase 9.6 — Estabilidade de Evidence Attribution

## Escopo e controles

Foram avaliados somente `rw-pena-morte`, `rw-prisao-perpetua` e
`rw-voto-obrigatorio`, os casos instáveis apontados na Fase 9.4. Cada caso teve
as evidências recuperadas uma vez e congeladas. Foram feitas cinco execuções
por caso, com o mesmo modelo `granite4.1:3b`, temperatura zero e o juiz atual.

Não foram alterados retrieval, selection, sufficiency, embeddings, dataset,
thresholds, schema ou semantic judge.

Artefatos brutos:

- `evaluation/results/variance_9_5_after.json` — baseline da Fase 9.5;
- `evaluation/results/variance_9_6_attribution_v1.json` — experimento 1;
- `evaluation/results/variance_9_6_attribution_v2.json` — experimento 2;

## Causa investigada

Em `voto obrigatório`, `EV004` é o dispositivo determinante:
`obrigatórios para os maiores de dezoito anos`, com o contexto estrutural do
parágrafo. `EV003` contém somente o caput do art. 14, e `EV001` trata de voto em
organização sindical. O gerador tinha todos os blocos disponíveis, mas escolhia
IDs por associação temática/lexical e não pelo trecho que sustentava a claim.

O formato anterior colocava referência, fonte, texto e contexto no mesmo bloco,
sem uma instrução suficientemente forte de que o ID deveria apontar somente para
o conteúdo que sustentava especificamente a claim. Claims também misturavam
fragmentos de assuntos diferentes.

## Experimentos

### Experimento 1 — atribuição estrita

Prompt novo no harness, com instrução de abster-se caso nenhuma claim direta
pudesse ser formada e formato explícito `EVIDENCE_ID`/`TEXTO VINCULADO`.

Resultado: 5/5 abstenções nos três casos. Segurança preservada, mas attribution
útil não foi produzida. Rejeitado.

### Experimento 2 — instrução mínima + ID adjacente

Prompt original preservado, acrescido de uma instrução curta para citar somente
IDs diretamente sustentadores e usar o menor conjunto suficiente. Os blocos
foram exibidos como `[EVxxx] texto: ... | contexto: ...`.

Resultado:

| Caso | Attribution correta | Respostas aceitas pelo juiz |
|---|---:|---:|
| pena de morte | 5/5 | 5/5 |
| prisão perpétua | 4/5 | 4/5 |
| voto obrigatório | 0/5 | 0/5 |

No voto, o modelo passou a produzir a claim, mas continuou citando `EV003` em
vez de `EV004`. Em uma execução de prisão houve claims sem IDs, corretamente
recusadas. O experimento não atingiu 80% nos casos-alvo e foi rejeitado.

## Gate

```text
EVIDENCE_ATTRIBUTION_GATE: BLOCKED
```

Motivos:

- attribution agregada dos três casos: 9/15 = 60%;
- `voto obrigatório`: 0/5 atribuições corretas;
- não há correção geral comprovada que preserve o comportamento sem introduzir
  novo tuning ou alterar componentes proibidos.

As validações fail-closed continuaram preservando `unsafe_answers = 0` nos
ensaios, e cadeias inválidas não foram aceitas. O `MVP1 Hit@10 = 0,905` e os
9/9 casos históricos de abstenção permanecem preservados por não haver alteração
de produção.

## Decisão

Nenhuma alteração de produção foi adotada na Fase 9.6. O problema residual é
atribuição instável entre claim e evidence ID, especialmente quando o conteúdo
normativo está dividido entre caput, pai estrutural e ocorrência filha. A etapa
seguinte deve investigar uma validação determinística de atribuição ou uma
representação explícita de contexto, sem ajustar thresholds para fechar o gate.
