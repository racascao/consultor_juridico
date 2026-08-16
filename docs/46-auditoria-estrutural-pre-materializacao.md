# Auditoria estrutural pré-materialização

## 1. Objetivo e decisão

A Fase 4B.3.1 auditou, sem alterar o parser nem o banco, a projeção jurídica em
memória da captura constitucional aceita. O resultado formal é:

```text
BLOCKED_FOR_MATERIALIZATION
```

Persistir exatamente a árvore atual não é seguro. Foram comprovados dois blockers:

1. 65 chaves estruturais de ARTICLE repetidas, em sua maioria porque redações
   históricas do mesmo dispositivo viraram ARTICLEs irmãos independentes;
2. todos os 66 blocos ignorados contêm estrutura ou texto jurídico que deveria
   participar da árvore, incluindo incisos sem hífen, alíneas grafadas com espaço e
   rubricas estruturais.

Não houve correção do parser nesta fase.

## 2. Metodologia

A auditoria recebe `ParsedLegalAct` e os segmentos factuais correspondentes. Ela
percorre cada árvore em pré-ordem, deriva uma chave diagnóstica composta por ato,
ancestralidade, tipo e label, cruza elementos com `DocumentBlock`, produz findings
ordenados e calcula SHA-256 sobre serialização canônica. O fingerprint não substitui
o hash do SourceDocument.

Severidades:

- `INFO`: fato explicado e seguro;
- `WARNING`: incerteza explicitamente preservada e auditável;
- `BLOCKER`: estrutura que não deve ser materializada sem correção.

O gate é `BLOCKED_FOR_MATERIALIZATION` quando existe ao menos um blocker.

## 3. ARTICLE e duplicidades

| Métrica | CF/88 | ADCT |
|---|---:|---:|
| ARTICLEs | 339 | 175 |
| Labels únicos | 276 | 148 |
| Labels duplicados | 49 | 16 |
| Ocorrências dentro dos grupos duplicados | 112 | 43 |

Labels CF repetidos:

```text
6, 16, 28, 29-A, 37, 38, 39, 40, 41, 42, 50, 53, 57, 62, 75, 77,
82, 88, 100, 101, 103, 103-B, 107, 111-A, 112, 113, 114, 115, 116,
126, 132, 134, 135, 149-A, 155, 168, 169, 178, 192, 201, 202, 214,
218, 222, 227, 239, 241, 243, 246
```

Labels ADCT repetidos:

```text
42, 52, 60, 71, 76, 76-A, 76-B, 83, 89, 101, 107-A, 109, 111,
115, 116, 117
```

Na CF, os 49 grupos foram classificados como
`SAME_LEGAL_DEVICE_HISTORICAL_REDACTION`. No ADCT, 15 receberam essa classificação
e um grupo permaneceu `STRUCTURAL_AMBIGUITY`.

Exemplo real: o Art. 6º da CF aparece quatro vezes nos blocos 156–159, com CAPUTs
`UNRESOLVED`, `HISTORICAL`, `HISTORICAL` e `CURRENT`. O Art. 60 do ADCT também
possui ocorrências históricas e corrente sob a mesma ancestralidade. A migration
004 aceitaria UUIDs distintos, mas retrieval e citation não teriam um ARTICLE
semântico inequívoco para o dispositivo. Isso contraria a intenção congelada de
ARTICLE como contêiner estrutural do dispositivo.

CF88/ARTICLE 1 e ADCT/ARTICLE 1 permanecem inequivocamente distintos pelo
`ParsedLegalAct`; essa homonímia entre atos não é duplicidade.

## 4. ARTICLE e CAPUT

Foram confirmados:

- `ARTICLE count == CAPUT count`: 339/339 na CF e 175/175 no ADCT;
- exatamente um CAPUT por ARTICLE;
- zero CAPUTs órfãos;
- zero CAPUTs vazios;
- zero CAPUTs sintéticos sem `synthetic_structure=true`;
- zero incompatibilidades de `block_index` entre ARTICLE e CAPUT;
- ARTICLE preserva somente o rótulo factual, sem duplicar o texto do CAPUT.

O contrato ARTICLE/CAPUT isoladamente está correto.

## 5. Os 66 blocos ignorados

Todos foram inspecionados. A categorização diagnóstica final é:

| Ato | Total | `PARSER_MISSED_STRUCTURE` |
|---|---:|---:|
| CF/88 | 64 | 64 |
| ADCT | 2 | 2 |

Blocos CF:

```text
227, 346, 683, 725, 778, 779, 780, 844, 962, 1363, 1364, 1374,
1375, 1377, 1380, 1381, 1382, 1383, 1384, 1385, 1386, 1583, 1601,
1602, 1603, 1699, 1715, 1716, 1719, 1720, 1729, 1730, 1731, 1732,
1733, 1734, 1735, 1736, 1737, 1751, 1752, 1880, 1881, 1882, 1883,
1884, 1885, 1888, 1889, 1890, 1892, 1893, 1895, 1896, 1897, 1902,
2291, 2293, 3174, 3175, 3176, 3177, 3178, 3305
```

Blocos ADCT: `3828` e `3829`.

Padrões comprovados:

- alíneas `c )`, `a )` e `b )`, não aceitas pelo regex estrito atual;
- incisos romanos sem hífen, como `IV as ilhas...`;
- inciso alfanumérico `VIIIA`;
- rubrica `SEÇÃO V-A` e títulos descritivos como “Dos Servidores Públicos”;
- séries normativas completas de incisos nos arts. 93, 103-B, 111-A, 114, 130-A,
  216-A e outros.

Não são artefatos de navegação, assinatura ou espaçamento. Como representam perda
estrutural silenciosa caso a árvore seja persistida, todos são blockers.

## 6. Status, histórico, revogação e strike

### UNRESOLVED

| Causa | CF/88 | ADCT |
|---|---:|---:|
| `FULL_STRIKE_WITHOUT_DECISIVE_MARKER` | 355 | 10 |
| `PARTIAL_STRIKE` | 28 | 2 |

Por tipo, a CF contém 44 ARTICLE, 44 CAPUT, 128 PARAGRAPH, 120 INCISO, 42 ALINEA
e 5 divisões estruturais unresolved. O ADCT contém 4 ARTICLE, 4 CAPUT, 2 PARAGRAPH
e 2 INCISO. Esses casos são warnings: a incerteza foi preservada com proveniência
e não foi convertida silenciosamente.

### HISTORICAL

CF: 20 ARTICLE, 20 CAPUT, 93 PARAGRAPH, 59 INCISO e 11 ALINEA. ADCT: 23 ARTICLE,
23 CAPUT, 59 PARAGRAPH, 64 INCISO e 20 ALINEA. O conteúdo histórico não desapareceu,
mas parte dele gerou os ARTICLEs independentes que bloqueiam a materialização.

### REVOKED

CF: 3 ARTICLE, 3 CAPUT, 20 PARAGRAPH, 26 INCISO e 12 ALINEA. ADCT: 11 ARTICLE,
11 CAPUT, 13 PARAGRAPH e 10 INCISO. A auditoria encontrou zero casos de REVOKED
sem marcador textual `Revogado/Revogada` no bloco de origem. Strike isolado não foi
usado como prova de revogação.

### Matriz strike × status

CF:

| Strike | CURRENT | HISTORICAL | REVOKED | UNRESOLVED | N/A |
|---|---:|---:|---:|---:|---:|
| Nenhum | 2917 | 0 | 29 | 0 | 1134 |
| Completo | 0 | 196 | 2 | 355 | 200 |
| Parcial | 0 | 7 | 33 | 28 | 42 |

ADCT:

| Strike | CURRENT | HISTORICAL | REVOKED | UNRESOLVED | N/A |
|---|---:|---:|---:|---:|---:|
| Nenhum | 824 | 0 | 11 | 0 | 450 |
| Completo | 2 | 182 | 3 | 10 | 142 |
| Parcial | 0 | 7 | 31 | 2 | 44 |

Os dois CURRENT completamente riscados no ADCT merecem revisão na fase corretiva,
mas não foram promovidos isoladamente a blocker porque a auditoria preserva o fato
e não demonstrou, por si só, classificação jurídica contrária à evidência textual.

## 7. NOTE

| Role | CF/88 | ADCT |
|---|---:|---:|
| AMENDMENT_NOTE | 1203 | 614 |
| REFERENCE_NOTE | 133 | 21 |
| EDITORIAL_NOTE | 40 | 1 |

Pais CF: PARAGRAPH 604, INCISO 526, ALINEA 140, CAPUT 105 e ARTICLE 1. Pais ADCT:
INCISO 239, PARAGRAPH 215, CAPUT 116, ALINEA 65 e DOCUMENT_ROOT 1.

Maiores outliers CF: arts. 100 (67), 156-A (63), 40 (63), 166 (53), 155 (50) e
37 (47). ADCT: arts. 60 (65), 97 (53), 101 (31), 130 (31), 107 (29) e 116 (29).
As quantidades decorrem da preservação de notas editoriais próximas às várias
redações.

Quatro blocos repetem literalmente texto de NOTE: 2552, 3289, 3299 e 4089. A
captura também repete esses textos; nos três casos CF existem links distintos para
o mesmo rótulo “Vide/Regulamento”, e no ADCT a anotação e href se repetem no HTML.
Foram registrados como INFO, não como duplicação artificial.

Zero NOTE vazia, normativa, com status diferente de NOT_APPLICABLE ou sem
proveniência foi encontrada.

## 8. Reutilização de bloco e ordem

| Elementos por bloco | CF/88 | ADCT |
|---|---:|---:|
| 1 | 1767 | 233 |
| 2 | 1280 | 541 |
| 3 | 163 | 106 |
| 4+ | 28 | 18 |

Combinações ARTICLE+CAPUT e elemento normativo+NOTE explicam a reutilização. Zero
combinações incomuns foram detectadas.

Em ambos os atos: mínimo 1, máximo igual ao total de elementos, contagem distinta
igual ao total, zero gaps e correspondência exata com a pré-ordem da árvore.

## 9. Hierarquia e profundidade

Todas as arestas observadas são compatíveis com o modelo congelado. Não foram
encontrados órfãos, ciclos, roots adicionais, ARTICLE sob ARTICLE, CAPUT fora de
ARTICLE, ALINEA sem INCISO ou ITEM sem ALINEA.

Profundidade CF: níveis 1–10, com máximo no caminho
`ROOT → TITLE IV → CHAPTER I → SECTION VIII → SUBSECTION III → ARTICLE 61 →
PARAGRAPH 1 → INCISO II → ALINEA c → NOTE` (blocos 13, 881, 884, 1067, 1095,
1097–1104). A profundidade é legítima.

Profundidade ADCT: níveis 1–6, com máximo em
`ROOT → ARTICLE 60 → PARAGRAPH 5 → INCISO I → ALINEA a → NOTE` (blocos 3423,
3678, 3704–3706). Também é legítima.

## 10. Sentinelas, labels e proveniência

Foram localizados todos os artigos exigidos: CF 1, 5, 6, 12, 60 e 250; ADCT 1,
60, 116-A, 117 e 134–138. O Art. 116-A preserva o sufixo e não colide com 116/117.
Os arts. 134–138 permanecem ordenados, com proveniência tardia após o fechamento
HTML prematuro.

Labels alfanuméricos CF:

```text
29-A, 103-A, 103-B, 111-A, 130-A, 146-A, 149-A, 149-B, 149-C, 156-A,
156-B, 159-A, 163-A, 164-A, 166-A, 167-A, 167-B, 167-C, 167-D, 167-E,
167-F, 167-G, 212-A, 216-A, 219-A, 219-B
```

Labels alfanuméricos ADCT: `18-A, 54-A, 60-A, 76-A, 76-B, 92-A, 92-B, 107-A,
111-A, 116-A`.

Todos os 6.651 elementos apontam para `block_index` pertencente ao segmento certo;
zero `source_line` foi inventada ou ficou ausente nesta captura. CAPUTs sintéticos
apontam para o mesmo bloco factual do ARTICLE. Anchors vazias são legítimas (254 CF,
279 ADCT); links foram preservados em 2.897 elementos CF e 1.425 ADCT.

## 11. Normalização, cobertura e determinismo

Testes confirmam somente NFC, CRLF/CR para LF, NBSP para espaço, compressão de
whitespace e trim. Acentos, caixa, pontuação e texto riscado permanecem. Não existe
paráfrase ou modernização.

| Cobertura | CF/88 | ADCT |
|---|---:|---:|
| Total | 3404 | 900 |
| Consumidos | 3340 | 898 |
| Ignorados | 64 | 2 |
| Percentual | 98,12% | 99,78% |
| Sem registro de auditoria | 0 | 0 |

O problema não é o percentual: é que os blocos ignorados são jurídicos. Duas
execuções produziram fingerprint de auditoria idêntico:

```text
90db3661e1974ee8018b22465500dd7044cf5314326c5f83cffd6e665709bc22
```

Na execução final: decode 3,2 ms, DOM 272,9 ms, blocos 177–185 ms,
segmentação 1,6 ms, parsing jurídico 100,0 ms, auditoria 28,6 ms e pipeline
auditado 623,7 ms. Os tempos são diagnósticos e variam conforme o ambiente.

## 12. Findings e gate

Resultado real:

- INFO: 4 (`REPEATED_NOTE_TEXT_IN_SOURCE`);
- WARNING: 2 (`UNRESOLVED_PRESERVED`, um por ato);
- BLOCKER: 131:
  - 65 `DUPLICATE_ARTICLE_STRUCTURAL_KEY`;
  - 66 `IGNORED_BLOCK_DIAGNOSED/PARSER_MISSED_STRUCTURE`.

Não houve divergência de schema com docs/41–42; os blockers estão na projeção do
parser em relação à semântica congelada.

## 13. Próxima ação recomendada

Criar uma fase corretiva curta antes da 4B.4 para:

1. consolidar redações históricas sob um único ARTICLE sem perder sua ordem,
   status, texto ou proveniência;
2. ampliar deterministicamente os padrões de inciso/alínea e divisões/rubricas;
3. adicionar golden fixtures dos 66 casos e repetir integralmente este gate.

Até nova auditoria sem blockers, a Fase 4B.4 não deve começar.
