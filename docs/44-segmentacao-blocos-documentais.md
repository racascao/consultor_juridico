# Segmentação CF/ADCT e blocos documentais — Fase 4B.2

## 1. Objetivo e relação com a Fase 4B.1

Esta fase projeta o DOM íntegro da Fase 4B.1 em uma sequência factual e a
particiona em regiões documentais, inteiramente em memória:

```text
DomDocument → DocumentBlock[] → leading | CF | transition | ADCT | trailing
```

`DocumentBlock` não é `LegalElement`: não classifica artigo, caput, parágrafo,
inciso, alínea, item, divisão, nota, vigência ou revogação.

## 2. Definição de DocumentBlock

Um bloco é a projeção de um `<p>` observado, com:

- `block_index`;
- tag;
- texto factual;
- projeção normalizada somente para matching;
- linha de origem, quando fornecida pelo backend;
- anchors e links em ordem;
- indicador de ancestralidade em tabela;
- presença e cobertura factual de `strike`.

Os dataclasses são frozen. Nenhum campo é persistido.

## 3. Política de seleção

Todos os `<p>` são enumerados em ordem DOM. Essa unidade cobre o fluxo
documental real, inclusive navegação, texto constitucional, assinaturas e
editorial. Elementos internos (`a`, `span`, `font`, `strike`) permanecem
propriedades/conteúdo do parágrafo. Scripts, estilos e nós textuais soltos não
viram blocos independentes e não são removidos do DOM.

## 4. block_index

`block_index` começa em 1, cresce de um em um e deriva exclusivamente da ordem
de `soup.find_all("p")`. Para mesmos bytes, Python/backend e versão das regras,
é determinístico. Não usa UUID, banco, IDs HTML, dict ou set.

Ele representa ordem factual da fonte. Não é `document_order`: um bloco poderá
futuramente gerar zero, um ou vários LegalElements.

## 5. Texto factual e matching

`text` é `Tag.get_text()` sem trim, colapso ou mudança de caixa e preserva o
conteúdo textual factual dos descendentes.

`normalized_text_for_matching` é derivado sem substituir `text`:

1. NBSP (`U+00A0`) e narrow NBSP (`U+202F`) viram espaço comum;
2. sequências Unicode de whitespace colapsam para um espaço;
3. whitespace externo é removido;
4. `casefold()` é aplicado.

Acentos, pontuação, números e identificadores permanecem. Essa projeção serve
somente a comparação e sentinelas; não recebe hash documental e não é
persistida.

## 6. Proveniência, anchors e links

`source_line` é copiada quando o `html.parser` a fornece; ausência permanece
`None`. A tag factual é `p`. Anchors incluem `name`/`id` do parágrafo e de
âncoras descendentes, em ordem e sem inventar um identificador preferencial.

Cada link preserva:

- texto factual da âncora;
- `href` original;
- URL resolvida por `urljoin` quando `SourceDocument.url_source` está
  disponível; caso contrário, `resolved_url=None`.

Não há DOM path ou byte offset.

## 7. Tratamento factual de strike

O bloco registra `contains_strike`, `fully_struck` e `partially_struck`. A
cobertura é calculada verificando se cada nó textual não vazio possui ancestral
`strike`. Isso descreve somente a marcação HTML; não produz `text_status`, não
declara revogação e nunca remove texto.

## 8. Regiões documentais

`ConstitutionDocumentSegments` particiona todos os blocos em:

- `leading_blocks`: navegação/conteúdo anterior ao corpo;
- `cf_blocks`: do marcador real PREÂMBULO até o bloco sentinela Art. 250,
  inclusive;
- `transition_blocks`: fecho, assinaturas e editorial entre Art. 250 e ADCT;
- `adct_blocks`: do cabeçalho documental ADCT até o bloco sentinela Art. 138,
  inclusive;
- `trailing_blocks`: conteúdo documental/editorial posterior.

Nenhum bloco é descartado, duplicado ou reordenado.

## 9. Sentinelas e fronteiras

### Início da CF

Exige uma única ocorrência exata normalizada de `PREÂMBULO` fora de tabela. A
captura real inicia a região CF no bloco 13. A navegação anterior permanece em
`leading_blocks`.

### Final da CF e transição

Depois do início da CF deve existir um único bloco cujo início corresponda a
`Art. 250`. Ele encerra o segmento CF. Os blocos seguintes permanecem na região
de transição até o cabeçalho ADCT.

### Início real do ADCT

O cabeçalho deve ser uma ocorrência exata de
`ATO DAS DISPOSIÇÕES CONSTITUCIONAIS TRANSITÓRIAS`, fora de tabela e depois do
Art. 250. A ocorrência do menu está dentro de tabela e é rejeitada. Zero
candidatas falha; mais de uma candidata contextual falha como ambiguidade.

### Final do ADCT

Depois do cabeçalho ADCT deve existir um único bloco iniciado por `Art. 138`.
Ele encerra o segmento ADCT. Blocos posteriores ficam em `trailing_blocks`.
Regex de artigo é usada somente como sentinela de fronteira e não cria ou
interpreta artigo.

## 10. Invariantes e erros explícitos

São validados:

- índices contínuos, crescentes e iniciados em 1;
- unicidade das sentinelas contextuais;
- ordem `PREÂMBULO ≤ Art. 250 < ADCT ≤ Art. 138`;
- CF e ADCT não vazios;
- concatenação das cinco regiões exatamente igual à entrada;
- determinismo estrutural em execuções repetidas.

Erros:

- `MissingDocumentSentinelError`;
- `AmbiguousDocumentSentinelError`;
- `InvalidDocumentOrderError`;
- base comum `DocumentSegmentationError`.

Não existe fallback silencioso.

## 11. Fingerprint diagnóstico

A projeção recebe SHA-256 de JSON canônico contendo índice, tag, texto,
source_line, anchors, links e flags factuais estáveis. Ele diagnostica a versão
da projeção e não substitui SHA-256 de `raw_bytes`, identidade documental ou
identidade jurídica. Não é persistido.

Captura aceita:

```text
7052caa371a1af7a812f226a58dd101d290fbbd68efcc46a1a5fd3d25b381ac2
```

## 12. Resultado observado na captura real

| Região | Blocos | Intervalo diagnóstico |
|---|---:|---:|
| leading | 12 | 1–12 |
| CF | 3.404 | 13–3.416 |
| transition | 6 | 3.417–3.422 |
| ADCT | 900 | 3.423–4.322 |
| trailing | 16 | 4.323–4.338 |

O primeiro `</html>` prematuro não truncou a projeção. O cabeçalho real ADCT é
o bloco 3.423 e o Art. 138 tardio é o bloco 4.322.

Esses índices e totais são diagnóstico desta captura, não semântica jurídica
hardcoded no algoritmo.

## 13. Fixtures e testes

Oito fixtures mínimas cobrem falsa ocorrência no menu, início da CF, transição,
final do ADCT, fechamento prematuro, sentinela ausente, ambiguidade e ordem
impossível. A fixture 4B.1 continua cobrindo a recuperação básica da cauda.

Testes adicionais cobrem texto, matching, anchors, links, source_line, strike,
exclusão de scripts como blocos, índice, partição e determinismo.

Integração read-only:

```bash
RUN_PARSING_INTEGRATION=1 uv run pytest -m parsing_integration -vv -s
```

## 14. Performance

Na execução real observada:

- enumeração/fingerprint: aproximadamente 181 ms;
- segmentação: aproximadamente 1,9 ms;
- decode + DOM + blocos + segmentação: aproximadamente 508 ms.

Não houve paralelização nem nova dependência.

## 15. Limitações e responsabilidades adiadas

- `<p>` é a unidade documental da fonte atual; mudanças estruturais futuras
  devem falhar nas sentinelas/regressões e exigir nova versão de parser.
- `source_line` depende do backend/runtime.
- cobertura de strike é marcação factual, não conclusão jurídica.
- sentinelas Art. 250 e Art. 138 delimitam esta família documental; não são um
  parser genérico de artigos.
- classificação estrutural, LegalElements, status, notas jurídicas,
  materialização, chunking, retrieval, evidence, citation e LLM permanecem
  adiados para fases expressamente autorizadas.
