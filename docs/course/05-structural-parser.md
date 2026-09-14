# 05. Parser estrutural

## Objetivo

Transformar o HTML oficial em provisions hierárquicas, ordenadas, localizáveis
e completamente auditadas.

## Onde estamos e incremento

```text
SourceSnapshot.raw_bytes → PlanaltoLeiParser → ParsedDocument
                                             ├─ provisions
                                             └─ coverage records
```

## Arquivos desta etapa

- `domain/corpus.py` para enums e dataclasses;
- `application/corpus/parser.py` para reconhecimento;
- `application/corpus/audit.py` para cobertura;
- fixtures em `tests/fixtures/corpus/`;
- testes em `tests/test_v02_foundation_corpus.py`.

## Contrato do domínio

O parser da tag reconhece `DOCUMENT_ROOT`, `CHAPTER`, `ARTICLE`, `CAPUT`,
`PARAGRAPH` e `INCISO`; `IN_FORCE` e `VETOED` são estados aceitos.

```python
class ProvisionType(StrEnum):
    DOCUMENT_ROOT = "DOCUMENT_ROOT"
    CHAPTER = "CHAPTER"
    ARTICLE = "ARTICLE"
    CAPUT = "CAPUT"
    PARAGRAPH = "PARAGRAPH"
    INCISO = "INCISO"


@dataclass(frozen=True, slots=True)
class ParsedProvision:
    stable_key: str
    provision_type: ProvisionType
    number_label: str | None
    parent_stable_key: str | None
    document_order: int
    citation_text: str | None
    source_locator: SourceLocator
    legal_status: LegalStatus
```

`SourceLocator` guarda `paragraph_start` e `paragraph_end`; `ParsedDocument`
traz provisions e uma entrada `CoverageRecord` para cada parágrafo relevante.
Esses objetos são imutáveis para impedir ajustes tardios invisíveis.

## Leitura do HTML

`PlanaltoLeiParser.parse` executa quatro passos:

1. `decode_strict(raw_bytes, encoding)`;
2. limita ao primeiro fechamento HTML relevante;
3. usa `BeautifulSoup(..., "html.parser")` e enumera `<p>`;
4. delega a `_parse_paragraphs` a máquina estrutural.

Um fragmento didático:

```html
<p>CAPÍTULO II</p>
<p>Art. 3º O administrado tem os seguintes direitos:</p>
<p>I - ser tratado com respeito;</p>
```

torna-se:

```text
DOCUMENT_ROOT
└─ CHAPTER:II
   └─ ARTICLE:3
      ├─ CAPUT
      └─ INCISO:I
```

## Reconhecimento e identidade

A implementação usa regexes restritas para chapter, article, parágrafo e
inciso. Ao encontrar um artigo, cria o container `ARTICLE` e uma provision
textual `CAPUT`; parágrafos e incisos usam o ancestral estrutural atual.
`document_order` cresce uma vez por provision.

`stable_key` é formada pela ancestralidade e rótulos normalizados; sua função
é identificar a mesma unidade dentro da versão e permitir citação. O texto
factual permanece em `citation_text`; não derive identidade do texto integral.

```python
# forma do método real; detalhes das regexes ficam no mesmo módulo
class PlanaltoLeiParser:
    def parse(self, raw_bytes: bytes, *, encoding: str) -> ParsedDocument:
        text = through_first_html_close(decode_strict(raw_bytes, encoding))
        soup = BeautifulSoup(text, "html.parser")
        paragraphs = tuple(
            _Paragraph(
                i,
                _normalize_presentation(node.get_text(" ", strip=True)),
                _anchor(node),
            )
            for i, node in enumerate(soup.find_all("p"))
        )
        return self._parse_paragraphs(paragraphs)
```

O recorte é fiel ao fluxo, mas omite extração auxiliar de anchors/locators.

## Cobertura e erros

Todo parágrafo deve ser consumido por uma provision ou explicitamente ignorado
com `IgnoreReason`. Estrutura desconhecida relevante levanta
`UnsupportedSourceStructure` com índice e excerpt. Essa regra impede parser
"bem-sucedido" que silenciosamente perca texto.

## Testes

Crie fixtures pequenas para documento root, chapter, artigos ordinal/decimal e
com sufixo, caput com incisos, parágrafo único/múltiplo, veto, nota editorial e
cauda Windows-1252.

```python
def test_caput_and_incisos_form_same_article_tree(parser, fixture_bytes):
    parsed = parser.parse(fixture_bytes, encoding="windows-1252")
    article = next(p for p in parsed.provisions if p.provision_type == "ARTICLE")
    children = [
        p for p in parsed.provisions if p.parent_stable_key == article.stable_key
    ]
    assert [p.provision_type for p in children] == ["CAPUT", "INCISO", "INCISO"]
    assert [p.document_order for p in parsed.provisions] == list(
        range(1, len(parsed.provisions) + 1)
    )
```

Teste também determinismo, parent existente, stable keys únicas, locator válido
e accounting `consumed + ignored == total`.

```bash
uv run pytest tests/test_v02_foundation_corpus.py -q
```

## Checkpoint

Todas as fixtures passam; duas execuções produzem objetos idênticos; nenhuma
estrutura relevante fica sem coverage record. Ainda não gravamos a árvore.

**Anterior:** [corpus](04-corpus.md).  
**Próximo:** [SearchUnits](06-search-units.md).
