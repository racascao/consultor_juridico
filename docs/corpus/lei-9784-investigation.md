# Investigação documental — Lei nº 9.784/1999

Data da captura analisada: 31 de agosto de 2026.

Este documento separa fatos observados na fonte de propostas ainda sujeitas à
revisão humana. Nenhum parser, schema ou corpus foi implementado neste
checkpoint.

## Observado — autoridade e captura

| Campo | Valor |
|---|---|
| Ato | Lei nº 9.784, de 29 de janeiro de 1999 |
| Código jurídico previsto | `BR-FED-LEI-9784-1999` |
| Autoridade | Presidência da República — Planalto |
| URL canônica | `https://www.planalto.gov.br/ccivil_03/leis/l9784.htm` |
| URL efetiva | igual à URL canônica |
| HTTP | `200 OK` |
| Redirecionamentos | 0 |
| `Content-Type` | `text/html`, sem charset |
| `ETag` | `"11ea6-650289ee47a83"` |
| `Last-Modified` | `Thu, 23 Apr 2026 23:00:54 GMT` |
| Tamanho | 74.941 bytes |
| SHA-256 desta captura bruta | `b4abab2e47732f76a16a99e8b00311dcb420b378f89e99c096b609ae84529261` |

O artefato bruto usado nesta investigação está em
`docs/corpus/artifacts/lei-9784-1999-planalto-2026-08-31.raw.html`. Ele é uma
captura de desenvolvimento e ainda não é uma `SourceSnapshot` do pipeline.

A página não se apresenta textualmente como “Texto compilado”. Contudo, seu
conteúdo incorpora inclusões promovidas pelas Leis nº 11.417/2006,
12.008/2009 e 14.210/2021. A descrição factual adotada é “texto oficial
apresentado pelo Planalto na captura”, sem inferir uma classificação editorial
ausente da própria página.

### Variação dinâmica da resposta

Uma captura feita em 30 de agosto de 2026 tinha o mesmo tamanho, `ETag`,
`Last-Modified` e anatomia jurídica, mas SHA-256 bruto diferente. A cauda após
`</html>` contém um script dinâmico `f5_cspm`; seus dados mudam entre respostas.
Os bytes jurídicos anteriores ao fechamento permanecem estáveis nas
observações realizadas.

Isso não autoriza remover, normalizar ou canonicalizar a cauda: `raw_bytes`
deve preservar exatamente a resposta recebida. O servidor suporta requisição
condicional: `If-None-Match: "11ea6-650289ee47a83"` retornou `304 Not Modified`
sem corpo. A aquisição futura pode, portanto, reutilizar o snapshot existente
quando o servidor confirmar `304`, preservando idempotência sem alterar bytes.

## Observado — encoding

Não há charset no cabeçalho HTTP nem `<meta charset>`. O único `<meta>` é:

```html
<meta name="GENERATOR" content="Microsoft FrontPage 6.0">
```

Resultados de decoding estrito:

| Encoding | Resultado |
|---|---|
| UTF-8 | falha no byte 467 |
| Windows-1252 | sucesso integral |
| ISO-8859-1 | decodifica formalmente, mas interpreta `0x96` como controle `U+0096` |

Existe exatamente um byte `0x96`. No contexto documental ele representa o
travessão em `III – (VETADO)`. Windows-1252 produz corretamente `U+2013`.
Nenhuma etapa futura poderá usar `errors="ignore"` ou `errors="replace"`.

## Observado — anatomia HTML

| Elemento | Quantidade |
|---|---:|
| `<p>` | 260 |
| `<p>` não vazios | 251 |
| `<font>` | 251 |
| `<small>` | 224 |
| `<a>` | 159 |
| âncoras nomeadas | 108 |
| hyperlinks | 51 |
| `<span>` | 78 |
| `<sup>` | 54 |
| `<u>` | 54 |
| `<br>` | 22 |
| `<table>` | 2 |
| `<strike>`/`<s>` | 0 |
| listas semânticas | 0 |

As classes relevantes são `texto2` e `MsoNormal`. Tabelas, fontes, alinhamento,
recuos e sublinhado são predominantemente apresentação visual. Não existem
elementos HTML semânticos para artigo, parágrafo ou inciso. A estrutura jurídica
é expressa por um fluxo ordenado de parágrafos e pelos rótulos textuais.

O documento fecha `</body></html>` antes de uma cauda de 1.561 bytes. A cauda é
integralmente o script `f5_cspm`; não contém texto jurídico.

## Observado — estrutura documental

O fluxo possui:

1. cabeçalho institucional;
2. epígrafe;
3. ementa;
4. fórmula de promulgação;
5. capítulos e dispositivos;
6. local, data e assinaturas;
7. aviso de publicação e retificação;
8. marcador residual `*`;
9. script dinâmico F5.

Contagens jurídicas:

| Tipo | Quantidade |
|---|---:|
| capítulos | 19 |
| artigos | 80 |
| parágrafos numerados | 52 |
| parágrafos únicos | 14 |
| incisos | 76 |
| seções | 0 |
| subseções | 0 |
| alíneas | 0 |
| itens | 0 |

Há 18 capítulos numerados de I a XVIII e o capítulo intercalado XI-A. O XI-A
é representado por três parágrafos consecutivos: número, rubrica e nota de
inclusão.

Os 80 artigos têm rótulos únicos: 1 a 70, 49-A a 49-G, 64-A, 64-B e 69-A.
Os arts. 1º a 9º usam `o` sobrescrito/sublinhado; a partir do art. 10 predomina
o ponto. Parágrafos também alternam entre `º` literal e `o` sobrescrito. Incisos
usam romanos com hífen, salvo a ocorrência com travessão já registrada.

Existem combinações reais de caput com incisos e de parágrafo com incisos. As
âncoras seguem padrões como `capituloi`, `capituloxia`, `art1`, `art49a` e
`art1§1`, mas não cobrem todos os dispositivos. Há a âncora irregular
`art2pxiii`.

## Observado — conteúdo editorial e status

| Padrão | Quantidade |
|---|---:|
| `(Incluído pela Lei nº ...)` | 43 |
| `Vigência` | 3 |
| `(VETADO)` | 7 |
| `Redação dada` | 0 |
| `Revogado/Revogada` | 0 |
| `(Vide...)` | 0 |
| `<strike>`/`<s>` | 0 |

Notas e links editoriais frequentemente compartilham o mesmo `<p>` com o
dispositivo. A nota final informa publicação no DOU e retificação em 11 de
março de 1999, com hyperlink para o PDF correspondente.

Dispositivos explicitamente vetados:

- art. 49-A, §§ 2º e 3º;
- art. 49-C;
- art. 49-G, § 2º;
- art. 69-A, inciso III;
- art. 69-A, §§ 3º e 4º.

Não há outra marcação inequívoca de status jurídico na captura. `IN_FORCE` e
`VETOED` cobrem os estados explicitamente observados; ausência de marcação não
autoriza inferência sobre histórico ou vigência externa.

## Observado — cobertura textual

Todo texto normativo se encaixa em `CHAPTER`, `ARTICLE`, `CAPUT`, `PARAGRAPH`
ou `INCISO`. Epígrafe, ementa e fórmula de promulgação formam o contexto raiz.
Assinaturas, aviso de retificação e scripts são conteúdo documental ou técnico,
mas não dispositivos normativos. Permanecem auditáveis nos bytes brutos e não
exigem novo `provision_type` nesta fase.

## Proposto — tipos e raiz

```text
PROVISION_TYPES_CONFIRMED:
DOCUMENT_ROOT, CHAPTER, ARTICLE, CAPUT, PARAGRAPH, INCISO

PROVISION_TYPES_MISSING:
NONE

PROVISION_TYPES_UNNECESSARY:
SECTION, SUBSECTION, ALINEA, ITEM
```

Recomenda-se manter `DOCUMENT_ROOT` como uma única Provision para epígrafe,
ementa e fórmula de promulgação. Esses três blocos são oficiais, precedem a
estrutura normativa e fornecem um ancestral determinístico comum. O cabeçalho
institucional, as assinaturas e a nota de retificação não integram seu
`citation_text`.

`ARTICLE` representa a identidade e o contêiner estrutural. `CAPUT` representa
o texto do artigo, inclusive quando não existem subdivisões. Isso evita duplicar
o texto integral no contêiner e mantém uma forma uniforme.

## Proposto — source locator

Usar um objeto factual derivado da ordem do DOM:

```json
{
  "paragraph_start": 143,
  "paragraph_end": 143,
  "anchor_name": "art49a"
}
```

- índices são baseados na coleção completa de `<p>`, em ordem documental e
  começando em zero;
- `paragraph_end` permite estruturas compostas, como o Chapter XI-A;
- `anchor_name` é opcional porque a fonte não ancora todos os dispositivos;
- ARTICLE e CAPUT sintético podem compartilhar o mesmo locator factual;
- linha de origem pode ser mantida apenas como diagnóstico, não como identidade;
- o locator nunca armazena texto ou interpretações editoriais.

A reprodutibilidade deverá ser comprovada sobre os bytes e versão de parser
específicos da `ActVersion`.

## Proposto — stable key

```text
PREAMBLE
CHAPTER:I
CHAPTER:XI-A
ARTICLE:1
ARTICLE:1/CAPUT
ARTICLE:1/PARAGRAPH:1
ARTICLE:2/PARAGRAPH:UNIQUE
ARTICLE:1/PARAGRAPH:2/INCISO:I
ARTICLE:3/CAPUT/INCISO:I
ARTICLE:49-A
```

O caminho do inciso inclui seu pai jurídico imediato para evitar colisões entre
incisos do caput e de parágrafos do mesmo artigo. As chaves usam rótulos
normalizados apenas para identidade; `number_label` e `citation_text` preservam
a apresentação factual. Nenhuma chave depende de UUID ou SearchUnit.

## Proposto — fixtures

| Fixture | Padrão de origem | Motivo | Estrutura esperada |
|---|---|---|---|
| `document_root` | epígrafe, ementa e promulgação | validar raiz oficial | `DOCUMENT_ROOT` |
| `chapter_standard` | capítulo com número e rubrica juntos | padrão dominante | `CHAPTER` |
| `chapter_xi_a` | número, rubrica e nota em três parágrafos | irregularidade real | `CHAPTER:XI-A` |
| `article_ordinal` | art. 1º com `<sup><u>o` | ordinal legado | `ARTICLE → CAPUT` |
| `article_decimal` | art. 10 com ponto | segundo padrão de artigo | `ARTICLE → CAPUT` |
| `article_suffix` | art. 49-A | rótulo alfanumérico | `ARTICLE:49-A → CAPUT` |
| `caput_inciso` | artigo com incisos diretos | hierarquia enumerativa | `CAPUT → INCISO*` |
| `unique_paragraph` | Parágrafo único | rótulo não numérico | `PARAGRAPH:UNIQUE` |
| `paragraph_inciso` | parágrafo numerado com incisos | hierarquia profunda | `PARAGRAPH → INCISO*` |
| `multiple_paragraphs` | artigo com vários parágrafos | ordem entre irmãos | `PARAGRAPH*` |
| `inline_editorial_note` | inclusão e vigência no mesmo `<p>` | fidelidade textual | texto oficial integral |
| `vetoed_devices` | artigo, parágrafo e inciso vetados | status explícito | `legal_status=VETOED` |
| `windows_1252_tail` | byte `0x96` e script após `</html>` | decoding e cobertura | U+2013; cauda não normativa |

Total proposto: 13 fixtures mínimas.

## Proposto — revisão do modelo e ports

Os achados não exigem nova entidade ou campo além do modelo já proposto:
`Source`, `SourceSnapshot`, `LegalAct`, `ActVersion`, `Provision`, `SearchUnit`
e `SearchUnitProvision`.

O contrato de `version_hash` permanece conceitualmente completo, desde que os
componentes sejam serializados de forma canônica, delimitada e com identificação
do algoritmo:

```text
legal_act.natural_key
source_snapshot.sha256
parser_name/parser_version
projection_name/projection_version
```

UUID não participa do hash. Não existe versão ativa implícita.

Os ports `SourceAcquirer`, `SnapshotRepository`, `CorpusMaterializer` e
`CorpusRepository` continuam suficientes. O contrato de aquisição deverá
suportar validadores HTTP (`ETag`/`Last-Modified`) e o resultado `not modified`,
sem expor parser ao adquirente. O materializador permanece sem acesso HTTP.

```text
MODEL_DATA_ADJUSTMENTS_REQUIRED: NO
VERSION_HASH_CONTRACT: VALID
PORTS_REVIEW: VALID
```
