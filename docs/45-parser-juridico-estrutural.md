# Parser jurídico estrutural em memória

## Objetivo e escopo

A Fase 4B.3 transforma os blocos já decodificados, enumerados e segmentados pelas
Fases 4B.1 e 4B.2 em duas árvores jurídicas independentes: CF/88 e ADCT. Todo o
processamento ocorre em memória. Não há criação de `ParsingRun`, `LegalVersion` ou
`LegalElement`, nem escrita no PostgreSQL.

O fluxo implementado é:

```text
SourceDocument → decode → DOM → DocumentBlock[] → segmentação CF/ADCT
               → ParsedConstitution(CF88, ADCT)
```

## Tipos em memória

Os dataclasses imutáveis `ParsedConstitution`, `ParsedLegalAct` e
`ParsedLegalElement` separam a projeção derivada dos modelos SQLAlchemy. Cada
elemento contém tipo, rótulo, textos factual e normalizado, status, papel,
`document_order`, localizador, metadados técnicos e filhos. A cobertura é descrita
por `BlockCoverage` e `CoverageReport`.

## Classificação e hierarquia

O reconhecimento usa padrões textuais determinísticos, sem LLM e sem depender
exclusivamente de CSS. A taxonomia é a congelada: `DOCUMENT_ROOT`, `PREAMBLE`,
`TITLE`, `CHAPTER`, `SECTION`, `SUBSECTION`, `ARTICLE`, `CAPUT`, `PARAGRAPH`,
`INCISO`, `ALINEA`, `ITEM` e `NOTE`.

Divisões estruturais mantêm um contexto hierárquico; níveis ausentes não são
inventados. Artigos são ligados ao nível estrutural mais específico ativo.
Parágrafos pertencem ao artigo; incisos pertencem ao parágrafo atual ou ao artigo;
alíneas pertencem ao inciso; itens, à alínea.

Cada ato recebe exatamente um `DOCUMENT_ROOT` sintético. Somente a CF recebe
`PREAMBLE`, identificado pelo marcador documental. O ADCT não recebe preâmbulo
artificial.

## ARTICLE e CAPUT

`ARTICLE` é o contêiner e preserva somente seu rótulo factual. Todo artigo recebe
exatamente um `CAPUT`, com o texto principal extraído do mesmo bloco. O CAPUT tem
o localizador factual desse bloco e registra `synthetic_structure=true` e a regra
`article_caput` em `parser_metadata`; nenhuma tag inexistente é inventada.

Parágrafo único é `PARAGRAPH` com `number_label="único"`. Artigos com sufixo,
como `116-A`, mantêm o sufixo no rótulo.

## Texto, status e roles

`raw_text` preserva o texto atribuído ao elemento, sem correção jurídica.
`normalized_text` aplica somente NFC, converte CRLF/CR para LF, converte espaços
não separáveis em espaço comum, comprime whitespace e remove whitespace externo.
Não há modernização, paráfrase nem remoção de acentos ou pontuação.

Os status são `CURRENT`, `HISTORICAL`, `REVOKED`, `UNRESOLVED` e
`NOT_APPLICABLE`. Uma marcação `<strike>` isolada resulta conservadoramente em
`UNRESOLVED`; com evidência textual de redação/inclusão, em `HISTORICAL`; e a
revogação exige marcador textual explícito. Notas sempre usam
`NOT_APPLICABLE`.

Os roles são `NORMATIVE`, `AMENDMENT_NOTE`, `REFERENCE_NOTE` e
`EDITORIAL_NOTE`. Notas de Emenda, inclusão, redação ou revogação são separadas do
texto normativo; referências como “Vide” e “Regulamento” recebem role de
referência. Links do bloco são preservados em `parser_metadata`.

## Proveniência e metadados

Todo elemento aponta para um `block_index` do segmento correto. Quando disponíveis,
também são preservados `tag`, `anchors` e `source_line`. Estruturas sintéticas,
regra de classificação, blocos combinados, cobertura de strike e links são
metadados técnicos determinísticos; o localizador continua factual.

## Ordem, cobertura e invariantes

`document_order` é atribuído em pré-ordem, começa em 1 no root, é contínuo e único
por ato. Ele não se confunde com `DocumentBlock.block_index`.

Todo bloco de CF e ADCT recebe destino explícito: `CONSUMED` ou
`IGNORED_WITH_REASON`. Blocos não classificáveis permanecem auditáveis como
`unclassified_block`; não há descarte silencioso. A validação exige root válido,
ordem contínua, textos não vazios, labels obrigatórios, proveniência no segmento,
um CAPUT por artigo e compatibilidade de NOTE com role/status. Falhas usam erros
de domínio específicos de classificação, hierarquia, estrutura ou cobertura.

## Golden fixtures e testes

Dez fixtures mínimas cobrem início da CF e preâmbulo, hierarquia profunda,
histórico, revogação explícita, notas e links, final da CF, ADCT complexo,
`116-A`, região recente e conteúdo posterior ao fechamento HTML prematuro. Os
testes declaram a árvore esperada, status, roles, proveniência, cobertura,
invariantes e determinismo. Elas preservam apenas os padrões mínimos derivados da
captura, não trechos extensos do documento.

As fixtures foram extraídas manualmente como recortes mínimos dos padrões da
captura aceita. Seus SHA-256 são:

| Fixture | SHA-256 |
|---|---|
| `legal_01_start_cf.html` | `12744c130bf878ddc152267f2dc69adbcf98b7831cb74f98fcc420f3ff2bf99a` |
| `legal_02_deep_hierarchy.html` | `592db78e43439c4388f6b783d213c9343b88751c4489f4cf5936876d81755470` |
| `legal_03_historical.html` | `a4fdba185505a857c1391792efc30fe89a6244f4173d880a5e5c1dfffaba631a` |
| `legal_04_revoked.html` | `74d1a8a2b23306cdd7c5d47a889a1b0e0e74045e1146f944ab13d746fe8e5e05` |
| `legal_05_notes_links.html` | `cf82ad07fc06647e95533d7e72fdd3c4b42f50c7f7a8d804c6f62e5df79ffdba` |
| `legal_06_cf_end.html` | `3be99d011ada49ebc19183ee752cc8185e3e2b89ff2cbe14fce4328e70226c1b` |
| `legal_07_adct_complex.html` | `aa9772200c72d9e9aeb2b3562ac8ad29fc2b58f5a69b8bd79384a5d29b23c27a` |
| `legal_08_suffix.html` | `877777f75f98c57877416e19fbdf7782c2b8f4c910bd24902c8189d750c5e2b8` |
| `legal_09_recent.html` | `e1ce0e994cf9aa734c90f97e577df9b157a361ef9531d5f295a58dcbbce1f60d` |
| `legal_10_after_close.html` | `5ec91b8a68eb95efd53dd30693fba26406004deae1ecf4897806e8d740177aee` |

## Integração real e métricas

O teste opt-in `parsing_integration` lê a captura persistida de 1.839.482 bytes,
confere o SHA-256
`25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d`,
executa o pipeline duas vezes e não escreve no banco.

Resultados da captura de referência:

| Métrica | CF/88 | ADCT |
|---|---:|---:|
| Blocos totais | 3.404 | 900 |
| Blocos consumidos | 3.340 | 898 |
| Blocos ignorados com razão | 64 | 2 |
| Cobertura | 98,12% | 99,78% |
| Elementos | 4.943 | 1.708 |
| Profundidade máxima | 10 | 6 |

CF/88 por tipo: ARTICLE 339, CAPUT 339, PARAGRAPH 1.015, INCISO 1.408,
ALINEA 362, NOTE 1.376, TITLE 10, CHAPTER 35, SECTION 52, SUBSECTION 5,
PREAMBLE 1 e DOCUMENT_ROOT 1.

ADCT por tipo: ARTICLE 175, CAPUT 175, PARAGRAPH 352, INCISO 299, ALINEA 70,
NOTE 636 e DOCUMENT_ROOT 1.

CF/88 por status: CURRENT 2.917, HISTORICAL 203, REVOKED 64, UNRESOLVED 383 e
NOT_APPLICABLE 1.376. ADCT: CURRENT 826, HISTORICAL 189, REVOKED 45,
UNRESOLVED 12 e NOT_APPLICABLE 636.

CF/88 por role: NORMATIVE 3.567, AMENDMENT_NOTE 1.203, REFERENCE_NOTE 133 e
EDITORIAL_NOTE 40. ADCT: NORMATIVE 1.072, AMENDMENT_NOTE 614,
REFERENCE_NOTE 21 e EDITORIAL_NOTE 1.

Na execução de referência, o parsing jurídico levou aproximadamente 102 ms; o
pipeline de decode, DOM, blocos, segmentação e parsing permaneceu abaixo de um
segundo. Tempos são diagnósticos e variam por ambiente.

As sentinelas Art. 1º, 5º, 12, 60 e 250 da CF e Art. 1º, 60, 116-A, 117, 134 e
138 do ADCT foram encontradas. O fingerprint lógico foi idêntico no reparse.

## Limitações e decisões adiadas

Blocos sem padrão jurídico seguro são mantidos no relatório como não classificados,
em vez de receber semântica especulativa. A classificação de strike é conservadora
e não resolve todas as combinações editoriais do Planalto. Não se pretende inferir
vigência material além das evidências explícitas da captura.

Ficam adiados para a Fase 4B.4: criação/retry de `ParsingRun`, materialização de
atos, versões e elementos, TX1/TX2/TX3, ativação conjunta CF/ADCT e idempotência
persistente. Chunking, retrieval, evidence, citation e LLM permanecem fora do
escopo.
