# Fase 11.1 — Composite Support

## 1. Objetivo e baseline

A fase implementou somente selection por contribuição marginal e attribution
determinística por cláusula. Retrieval, modelos, prompts, thresholds, limite de
EvidenceItems, Polarity Guard, Citation Validator, SEU, corpus e schema
permaneceram congelados.

Baseline Fase 11: 7/10 respostas corretas, três falsas abstenções, 1/1
abstenção correta, zero unsafe, MVP1 Hit@10 0,905 e real-world Hit@10 0,900.

## 2. Marginal Evidence Selection

Após deduplicar por provision, cada candidato com âncora substantiva recebe:

```text
base = 0,65 × query_coverage
     + 0,20 × rank_relevance
     + 0,15 × parent_context_signal

final = 0,45 × base
      + 0,40 × marginal_query_coverage
      + 0,15 × (1 - redundancy)
```

O primeiro item maximiza relevância-base. Os seguintes precisam ser elegíveis
pela query e acrescentar cobertura ou manter relevância suficiente sem alta
redundância. Novidade lexical isolada não promove candidato. Desempates usam
posição híbrida e identidade estável. O limite continua três.

O diagnóstico em memória registra relevância-base, cobertura, contribuição
marginal, redundância, score, posição e motivo. `parent_context` participa
somente do scoring; snapshot, alvo de citação e provenance não mudam.

Resultado focal: o inciso IX passou a ser selecionado para liberdade de
expressão, comprovando a correção do blocker de selection. A resposta, porém,
continuou abstida na attribution simples por `liberdade` versus `livre`.

## 3. Clause Attribution

Claims simples preservam o algoritmo anterior. Claims compostas são separadas
somente quando ponto e vírgula, enumeração ou coordenação introduzem
predicações completas em todos os segmentos.

Não são separados:

- negação e complemento;
- regra e exceção;
- condições com `se`, `quando`, `desde que`, `salvo`, `exceto` ou `ressalvado`;
- listas nominais;
- referências jurídicas;
- ocorrências de `e` sem duas predicações.

Cada cláusula recebe attribution apenas contra EvidenceItems autorizados. Além
da cobertura morfológica/IDF, clauses independentes exigem cobertura literal
mínima de 0,60, impedindo colisões como `autoridade` versus `autorizar`. Se uma
cláusula falha, a claim inteira fica `UNRESOLVED`. A união remove duplicatas e
preserva a ordem original do EvidenceSet.

Os tipos imutáveis `ClaimClause`, `ClauseAttribution` e
`ClaimAttributionDiagnostic` registram spans, modo `SIMPLE/CLAUSE`, scores,
Evidence IDs e motivos sem migration ou persistência adicional.

## 4. Testes e controles negativos

Foram adicionados vinte testes específicos cobrindo:

- determinante de rank alto;
- redundância e complemento intermediário;
- candidato novo irrelevante;
- contexto pai, dedup, limite e determinismo;
- claims simples, duas/três clauses e multi-evidence;
- clause sem suporte, evidência temática e ID externo;
- negação, exceção, condição, lista nominal e coordenação real;
- ordem de Evidence IDs e fail-closed parcial.

A suíte completa passou com 323 testes e cinco skips. Controles de inversão,
obrigação, permissão, exceção, suporte temático, IDs inválidos, fora do corpus e
aborto permaneceram verdes. Unsafe e cadeias inválidas ficaram em zero.

## 5. Avaliação real-world única

| Métrica | Fase 11 | Fase 11.1 |
|---|---:|---:|
| respostas corretas | 7/10 | 7/10 |
| falsas abstenções | 3 | 3 |
| abstenção correta | 1/1 | 1/1 |
| unsafe | 0 | 0 |
| real-world Hit@10 | 0,900 | 0,900 |
| MVP1 Hit@10 | 0,905 | 0,905 |

Não houve regressão, mas também não houve caso recuperado.

### Liberdade de expressão

Marginal selection recuperou o inciso IX e o colocou na segunda posição. A
claim gerada permaneceu simples; attribution falhou porque a abordagem lexical
não demonstra de modo inequívoco a paráfrase `liberdade` → `livre`.

### Estado de sítio

Não houve claim composta utilizável na execução final, portanto clause
attribution não pôde atuar. A provision esperada também permaneceu fora do
top-10, embora elementos relacionados tenham sido selecionados.

### Pena de morte

A alínea determinante continuou selecionada, mas o Generator absteve nas
tentativas desta execução. A adjudicação regra/exceção permaneceu corretamente
fora do escopo.

## 6. Gate e interpretação

`COMPOSITE_SUPPORT_GATE: BLOCKED`. O threshold exigia pelo menos 9/10 e no
máximo uma falsa abstenção.

As duas intervenções passam isoladamente e preservam segurança, porém seus
pressupostos não coincidiram com os resíduos finais: uma paráfrase lexical em
claim simples, ausência de claim composta utilizável e variância/abstenção do
Generator. Isso confirma limite da atual composição de gates heurísticos para
esse caminho específico. A contribuição isolada do modelo permanece
inconclusiva com uma única matriz.

Pelo protocolo, nenhuma heurística adicional foi adicionada. A recomendação é
`ARCHITECTURAL_REVIEW`, avaliando uma representação explícita e auditável de
necessidades de suporte antes da geração, em vez de ampliar splitters, listas
de sinônimos ou regras por caso.

## 7. Artefatos

- `composite_support_11_1_baseline.json`;
- `composite_support_11_1_negative_controls.json`;
- `composite_support_11_1_final.json`;
- `composite_support_11_1_mvp1_retrieval.json`;
- `composite_support_11_1_summary.json`.

Não houve migration, ingestão, alteração de corpus/raw bytes, troca de modelos,
integração da SEU, commit ou push.
