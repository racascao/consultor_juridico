# Decoder e DOM íntegro — Fase 4B.1

## 1. Objetivo

Esta subfase implementa somente a projeção derivada e determinística:

```text
SourceDocument.raw_bytes
  → validação SHA-256
  → decoding estrito
  → BeautifulSoup + html.parser
  → DOM e métricas diagnósticas em memória
```

Não cria ParsingRun, LegalAct, LegalVersion ou LegalElement e não modifica o
banco, os bytes oficiais ou o HTML recebido.

## 2. Captura de referência

| Campo | Valor |
|---|---|
| document_id | `27f0ff6b-dd9e-4c4e-ba56-c34984f691e1` |
| URL | `https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm` |
| tamanho | 1.839.482 bytes |
| SHA-256 | `25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d` |

O UUID é usado somente no teste de integração local. A API de produção aceita
qualquer SourceDocument ou os dados genéricos `id`, bytes e hash esperado.

## 3. Integridade SHA

`decode_raw_document` calcula SHA-256 diretamente sobre `raw_bytes` e compara o
resultado antes de qualquer tentativa de decoding. Divergência lança
`SourceDocumentIntegrityError` e impede a continuação. O hash nunca é calculado
sobre Unicode ou DOM.

## 4. Encoding e estratégia de decoding

O encoding centralizado do adapter constitucional é `windows-1252`. O decoding
usa `errors="strict"`: não há descarte, substituição ou normalização silenciosa.
Falha estrita lança `SourceDocumentDecodingError`.

A captura de referência foi integralmente decodificada, inclusive os bytes
`0x92`, projetados como apóstrofo tipográfico `U+2019`. O texto decodificado
mantém whitespace, CR/LF, NBSP, pontuação e grafia; é uma projeção derivada e
não substitui `raw_bytes`.

## 5. Backend HTML

O backend congelado e implementado é:

```python
BeautifulSoup(decoded_text, "html.parser")
```

Não se usa `lxml` como caminho principal. Python, BeautifulSoup e demais
dependências permanecem travados pelo `uv.lock` e pela imagem do projeto.

## 6. Fechamento HTML prematuro

O diagnóstico localiza o primeiro `</html>` sem modificar ou reparar
manualmente o texto. A captura mantém 1.705.509 caracteres depois desse ponto.
`premature_close_found` somente é verdadeiro quando existe conteúdo não trivial
na cauda.

O `html.parser` preservou no DOM tanto conteúdo anterior quanto o artigo 250 da
CF, o cabeçalho do ADCT e o artigo 138 do ADCT, todos os marcadores tardios
verificados sem interpretação ou segmentação jurídica.

## 7. Métricas da captura aceita

| Métrica | Resultado |
|---|---:|
| parágrafos | 4.338 |
| parágrafos não vazios | 4.326 |
| âncoras (`a`) | 7.402 |
| links (`a[href]`) | 2.582 |
| `strike` | 773 |
| tabelas | 2 |
| scripts | 2 |
| caracteres após primeiro `</html>` | 1.705.509 |
| linhas de origem disponíveis | sim |

Esses números são fingerprint diagnóstico desta captura, não regras jurídicas
nem cardinalidades globais. O teste opt-in usa faixas estreitas para detectar
perda catastrófica diante dessa mesma captura.

## 8. Invariantes de regressão

- SHA-256 válido antes do decoding;
- Windows-1252 estrito, sem replacement character;
- presença do preâmbulo antes do primeiro fechamento;
- presença do artigo 250 depois do fechamento;
- presença do cabeçalho do ADCT;
- presença do artigo 138 na região tardia;
- contagens estruturais compatíveis com a captura aceita;
- conteúdo anterior e posterior ao fechamento acessível no DOM;
- duas execuções com mesmo texto, encoding, métricas e marcadores;
- contagens de ParsingRun, LegalVersion e LegalElement inalteradas.

## 9. Testes

Os testes unitários usam bytes e HTML pequenos. A fixture
`premature_html_close.html` preserva o padrão malformado mínimo e cobre conteúdo
antes/depois do fechamento, links, âncoras, `strike`, script e parágrafo vazio.

A regressão local é opt-in e somente leitura:

```bash
RUN_PARSING_INTEGRATION=1 uv run pytest -m parsing_integration -vv -s
```

Ela não acessa a internet e não executa ingestão.

## 10. Determinismo

Para os mesmos bytes, duas execuções produziram o mesmo SHA, encoding, texto,
métricas e projeção textual relevante. Não se exige reserialização byte a byte
do BeautifulSoup: o DOM é derivado e não se torna fonte documental.

## 11. Source line e proveniência futura

O backend fornece `sourceline` para os nós observados e a métrica registra essa
disponibilidade. A linha identifica a abertura do nó segundo o HTML reparado;
depende da versão do Python/backend e será apenas auxiliar. Ela não substitui o
futuro `block_index`, não é identidade e não autoriza inventar linha ausente.

A API mantém o DOM integral, a projeção Unicode, o document ID e o SHA validado.
Isso permite à próxima subfase enumerar blocos deterministicamente e obter tag,
âncoras e linha sem persistir localizadores agora.

## 12. Performance observada

Na execução local de referência:

- decoding: aproximadamente 3 ms;
- construção do primeiro DOM: aproximadamente 277 ms;
- pipeline medido: aproximadamente 312 ms.

A captura de cerca de 1,8 MB é processada integralmente em memória. Não foi
adicionada dependência de profiling nem aplicada otimização prematura.

## 13. Limitações

- `BeautifulSoup` é um objeto internamente mutável; `DomDocument` congela a
  referência e os resultados, e o pipeline não executa mutações. Consumidores
  futuros devem tratar o DOM como read-only.
- `sourceline` é auxiliar e sensível ao backend/runtime.
- thresholds pertencem exclusivamente à captura de referência.
- nenhuma segmentação CF/ADCT ou interpretação jurídica é realizada.

## 14. Ausência de materialização jurídica

Não há repository ou serviço de parsing nesta subfase. O teste real faz apenas
SELECT e confirma antes/depois:

```text
parsing_runs=0
legal_versions=0
legal_elements=0
```

## 15. Critérios para a Fase 4B.2

A próxima subfase poderá partir de um documento íntegro contendo texto, DOM,
métricas e proveniência documental. Ela deverá tratar somente a segmentação do
fluxo CF/ADCT e continuar sem alterar `raw_bytes`. Seu início depende de revisão
humana explícita desta entrega.
