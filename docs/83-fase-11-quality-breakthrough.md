# Fase 11 — Quality Breakthrough

## 1. Objetivo e protocolo

A fase tratou o pipeline como um sistema de decisão e procurou reduzir falsos
negativos por regras gerais, sem trocar modelos, embeddings, dataset ou
thresholds. Foram executadas exatamente duas matrizes `real-world-short-v1`:
uma baseline anterior às mudanças e uma avaliação final após o plano fechado.
Não houve ajuste adaptativo depois da medição final.

Meta congelada: pelo menos 8/10 respostas corretas, no máximo duas falsas
abstenções, 1/1 abstenção correta, zero respostas inseguras, zero cadeias de
citação inválidas e MVP1 Hybrid Hit@10 de pelo menos 0,905.

## 2. Baseline e oracle causal

A baseline reproduziu 4/10 respostas corretas, seis falsas abstenções, 1/1
abstenção correta, zero unsafe e real-world Hit@10 0,900.

| Caso | Stage reportado | Primeiro erro causal |
|---|---|---|
| pena de morte | selection | `SELECTION_FALSE_NEGATIVE` |
| prisão perpétua | sufficiency | `SUFFICIENCY_FALSE_NEGATIVE` |
| racismo | generator abstention | `ATTRIBUTION_FALSE_NEGATIVE` |
| direito à vida | generator abstention | `POLARITY_FALSE_NEGATIVE` |
| liberdade de expressão | selection | `SELECTION_FALSE_NEGATIVE` |
| estado de sítio | retrieval | `ATTRIBUTION_FALSE_NEGATIVE` |

No último caso, a provision esperada não estava no top-10, mas o EvidenceSet
selecionado continha material para a claim; o trace morreu depois em “Claim C2
sem atribuição inequívoca”. Por isso o oracle causal não replica cegamente o
stage agregado do avaliador.

## 3. Plano fechado antes da implementação

As quatro intervenções definidas antes de modificar produção foram:

1. normalizar flexões simples de modo uniforme em selection e attribution;
2. preservar evidência determinante na selection por cobertura textual
   normalizada;
3. permitir sufficiency com scores fracos quando houver âncora textual material;
4. restringir a gramática de exceção a locuções realmente exceptivas.

Não foram adicionadas intervenções após observar a avaliação final.

## 4. Implementação

### Selection

Tokens agora removem plural final simples e usam prefixo conservador de seis
caracteres. Isso aproxima `pena/penas` e outras flexões sem dicionário jurídico,
case ID, artigo ou resposta esperada. `raw_text`, EvidenceItem e provenance não
são alterados.

### Sufficiency

Scores lexical e vetorial abaixo dos thresholds continuam insuficientes quando
não existe âncora textual. Quando a pergunta e ao menos um candidato/contexto
compartilham token substantivo normalizado, o conjunto pode avançar para os
gates que verificam attribution, citação, polaridade e suporte semântico. A
sufficiency continua rejeitando ausência de candidatos e escopo externo; ela
não tenta substituir o Semantic Validator.

### Attribution

A normalização passou a cobrir flexões nominais e verbais simples, mantendo a
ponderação IDF local, a combinação multi-evidence já existente e a proibição
absoluta de selecionar códigos fora do EvidenceSet autorizado.

### Polarity e exceções

O detector deixou de tratar `a salvo` como exceção, preservando marcadores como
`salvo em caso de`, `exceto`, `ressalvado` e `à exceção de`. O reconhecimento de
obrigação passou a cobrir formas de `deve`. Também foi corrigido o diagnóstico:
`EXCEPTION_SCOPE_AMBIGUITY` só é emitido quando a evidência realmente contém
marcador de exceção.

## 5. Responsabilidade final dos gates

| Componente | Papel | Pode bloquear? |
|---|---|---|
| Selection | `EVIDENCE_QUALITY_GATE` | Sim, se não preservar candidato material |
| Sufficiency | `ROUTING_SIGNAL` conservador | Sim para ausência/fora do escopo; não duplica julgamento semântico |
| Attribution | `EVIDENCE_QUALITY_GATE` | Sim, quando não há vínculo inequívoco autorizado |
| Citation Validator | `HARD_SAFETY_GATE` | Sim |
| Polarity | `HARD_SAFETY_GATE` para contradição; routing nos demais estados | Sim conforme boundary congelada |
| Semantic Validator | `HARD_SAFETY_GATE` | Sim |

Nenhuma fronteira foi relaxada para aceitar contradições ou citações inválidas.

## 6. Testes e controles negativos

Foram acrescentados testes para singular/plural na seleção, âncora textual na
sufficiency, flexão morfológica na attribution e `a salvo` como controle
negativo de exceção. A suíte completa passou com 303 testes e cinco skips.

Os controles negativos cobriram prisão perpétua invertida, voto facultativo
diante de obrigação, permissão versus proibição, exceção material da pena de
morte, evidência apenas temática, Evidence ID inexistente, claim sem suporte,
pergunta fora do corpus e aborto. Resultado: `PASS`, zero unsafe e zero cadeias
inválidas.

## 7. Avaliação final

| Métrica | Produção baseline | SEU 10.1 | Fase 11 |
|---|---:|---:|---:|
| respostas corretas | 4/10 | 5/10 | **7/10** |
| falsas abstenções | 6 | 5 | **3** |
| abstenção correta | 1/1 | 1/1 | **1/1** |
| unsafe | 0 | 0 | **0** |
| real-world Hit@10 | 0,900 | 0,900 | **0,900** |
| MVP1 Hit@10 | 0,905 | 0,905 | **0,905** (preservado) |

Casos recuperados: prisão perpétua, racismo e direito à vida. Não houve
regressão de caso anteriormente correto.

Falhas residuais:

- `pena de morte`: a evidência determinante foi selecionada, attribution e
  polarity avançaram, mas o Semantic Judge classificou a claim como apenas
  parcialmente suportada por interpretar que a exceção não estava coberta;
- `liberdade de expressão`: a evidência determinante ainda não sobreviveu à
  selection;
- `estado de sítio`: o conjunto contém material constitucional relacionado,
  mas uma claim composta continua sem attribution inequívoca.

O tempo end-to-end observado foi 822,6 s para os onze casos (média 74,8 s por
caso, incluindo a abstenção determinística). As regras novas são locais e
determinísticas; o custo continua dominado por Generator e Semantic Judge.

## 8. Resultado arquitetural

`QUALITY_BREAKTHROUGH_GATE: PARTIAL`. O ganho foi transversal (+3 sobre
produção e +2 sobre SEU 10.1) e preservou segurança, mas não atingiu 8/10 nem
o limite de duas falsas abstenções.

A SEU permanece `PROMISING_BUT_INSUFFICIENT` e não foi integrada. Os resíduos
atravessam três fronteiras diferentes, portanto ainda não há evidência para
confirmar teto da arquitetura ou limitação isolada do Granite 3B.

A única próxima intervenção recomendada é experimentar um adjudicador
determinístico de suporte composto, com um veredito auditável entre attribution,
semântica de exceção e Semantic Validator. O objetivo é eliminar decisões
inconsistentes entre gates, sem aumentar retrieval/contexto e sem microtuning
por pergunta.

## 9. Artefatos

- `evaluation/results/quality_breakthrough_11_baseline.json`;
- `evaluation/results/quality_breakthrough_11_diagnosis.json`;
- `evaluation/results/quality_breakthrough_11_final.json`;
- `evaluation/results/quality_breakthrough_11_negative_controls.json`;
- `evaluation/results/quality_breakthrough_11_summary.json`.

Nenhuma migration, ingestão, alteração de raw bytes, troca de modelo ou
integração da SEU foi realizada.
