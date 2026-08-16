# Correção dos blockers estruturais e revalidação

## 1. Resultado

A Fase 4B.3.2 corrigiu os reconhecedores compatíveis com o modelo congelado e
reexecutou a auditoria da Fase 4B.3.1. O resultado formal permanece:

```text
GATE 4B.4: BLOCKED_FOR_MATERIALIZATION
MOTIVO: SCHEMA_MODEL_GAP
```

Nenhuma árvore foi persistida. Docs/41–42, migration 004, modelos SQLAlchemy e
banco permaneceram inalterados.

## 2. Blockers originais e causa raiz

Havia 65 grupos de `ARTICLE` com a mesma chave estrutural (49 CF e 16 ADCT) e 66
blocos classificados como `PARSER_MISSED_STRUCTURE` (64 CF e 2 ADCT). Os primeiros
decorrem principalmente da forma editorial do Planalto: cada redação histórica e
a redação corrente reapresentam o rótulo e o texto do mesmo dispositivo. O parser
factualmente preservava cada ocorrência como `ARTICLE` independente.

Art. 6º da CF aparece quatro vezes nos blocos 156–159; Art. 60 do ADCT aparece
quatro vezes nos blocos 3668, 3670, 3678 e 3715. Art. 117 do ADCT aparece nos
blocos 4185 (`HISTORICAL`) e 4186 (`CURRENT`). Notas de Emenda conectam as redações,
e strike marca apresentação histórica, mas não autoriza inferência externa.

## 3. Lacuna do modelo congelado

Docs/41–42 exigem `ARTICLE` como identidade/container e exatamente um `CAPUT` por
`ARTICLE`. A taxonomia não possui um nó normativo para uma redação alternativa do
mesmo caput ou da subárvore inteira. Assim, consolidar as ocorrências exigiria uma
das opções proibidas: múltiplos CAPUTs, uso indevido de NOTE, perda de texto/status/
proveniência ou novo tipo de elemento.

Os 65 grupos foram preservados e passaram a produzir finding explícito
`SCHEMA_MODEL_GAP`. Não houve colapso, descarte ou reclassificação como NOTE. Quatro
rubricas substitutivas (`Dos Servidores Públicos`, `Dos Militares...`, `Da
Advocacia Pública` e `Da Família...`) também permanecem fora da árvore com o
diagnóstico `HISTORICAL_RUBRIC_MODEL_GAP`, pois o modelo não representa redações
alternativas de um mesmo heading sem duplicação estrutural.

## 4. Correções implementadas

Os reconhecedores passaram a aceitar, somente em contexto jurídico compatível:

- alíneas `a)`, `a )` e variantes com whitespace, preservando `raw_text`;
- incisos romanos sem hífen, exigindo token maiúsculo e corpo textual;
- inciso alfanumérico factual `VIIIA`, sem convertê-lo em `VIII-A`;
- labels de divisões com sufixo, inclusive `SEÇÃO V-A`;
- série contínua de incisos sem hífen;
- notas editoriais entre marker de divisão e sua rubrica, sem confundir a nota
  com o título descritivo.

Não existe regra por `block_index`. Os 62 blocos numerados corrigíveis passaram a
ser consumidos. `PARSER_MISSED_STRUCTURE` caiu de 66 para zero; os quatro restantes
foram explicitamente reclassificados como lacuna do modelo.

## 5. FULLY_STRUCK + CURRENT

Os dois casos eram o `ARTICLE 83` e seu `CAPUT`, ambos derivados do bloco 3860 do
ADCT (ordens 750 e 751 antes da reenumeração diagnóstica). O texto começa por “Lei
federal definirá os produtos e serviços supérfluos...”. O `<p>` estava dentro de
um ancestral `<strike>`: `fully_struck` detectava os nós riscados, mas
`contains_strike` procurava apenas descendentes. A inconsistência técnica fazia o
status cair em `CURRENT`.

A projeção factual agora considera nós textuais com ancestral `<strike>`. Nenhuma
inferência de revogação foi feita: sem marcador conclusivo, o status conservador é
`UNRESOLVED`. A matriz final contém zero `FULLY_STRUCK + CURRENT`.

## 6. Golden fixtures e regressões

Foram adicionadas dez fixtures mínimas para: múltiplas redações; histórico versus
corrente; duplicidade corrente ambígua; alínea espaçada; inciso sem hífen; `VIIIA`;
`SEÇÃO V-A`; rubrica histórica; série de incisos; e strike ancestral no ADCT.
Testes negativos impedem que prosa comum em minúsculas seja promovida a inciso.

## 7. Métricas antes e depois

| Métrica | Antes | Depois |
|---|---:|---:|
| ARTICLE CF / ADCT | 339 / 175 | 339 / 175 |
| CAPUT CF / ADCT | 339 / 175 | 339 / 175 |
| Labels únicos CF / ADCT | 276 / 148 | 276 / 148 |
| Grupos duplicados CF / ADCT | 49 / 16 | 49 / 16 |
| Elementos totais | 6.651 | 6.771 |
| NOTE | 2.012 | 2.072 |
| CURRENT | 3.743 | 3.803 |
| HISTORICAL | 392 | 394 |
| REVOKED | 109 | 109 |
| UNRESOLVED | 395 | 393 |
| `PARSER_MISSED_STRUCTURE` | 66 | 0 |
| Lacunas de rubrica | 0 explícitas | 4 |
| Cobertura CF | 98,12% | 99,88% |
| Cobertura ADCT | 99,78% | 100% |
| INFO / WARNING / BLOCKER | 4 / 2 / 131 | 4 / 2 / 69 |
| Profundidade máxima | 10 | 10 |

Os 69 blockers finais são 65 grupos normativos históricos (`SCHEMA_MODEL_GAP`) e
quatro rubricas históricas alternativas. `blocks_without_audit_record=0` nos dois
atos. ARTICLE/CAPUT, pré-ordem contínua, hierarquia, proveniência, cobertura
contábil e determinismo permaneceram válidos.

## 8. Fingerprints e performance

Fingerprints finais determinísticos:

```text
árvore CF:   0dbd2eb0cd5e2afc675772b84d2790f40edb283c75d25b186ec6a98f5fabdf3a
árvore ADCT: 79453de87cf0e569b77462c114eacbb95b7b4ae230d2430e1488ed83297d8450
auditoria:   b1d5262d2902309b1cf810f961e8ff319155dade899bfecd10d307968437c9c0
```

Na execução final: decode 3,3 ms, DOM 299,6 ms, blocos 175,1 ms,
segmentação 2,2 ms, parsing 115,4 ms, auditoria 28,4 ms e pipeline 660,6 ms.
Esses tempos são apenas diagnósticos.

## 9. Limitações e decisão sobre 4B.4

O reconhecimento numérico não possui blocker remanescente, mas a representação
histórica exige revisão humana do modelo. A Fase 4B.4 não pode começar enquanto
não houver uma decisão normativa que permita preservar redações alternativas e
rubricas históricas sem violar ARTICLE/CAPUT ou transformar texto normativo em
NOTE.
