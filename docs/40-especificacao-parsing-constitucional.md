# Especificação do parsing estrutural da CF/88 e do ADCT

## 1. Objetivo

Esta especificação descreve como uma futura Fase 4B poderá transformar, de modo
determinístico e auditável, a captura HTML oficial da Constituição Federal de 1988
e do Ato das Disposições Constitucionais Transitórias (ADCT) em uma árvore de
elementos jurídicos.

O documento é resultado de investigação sobre a captura real persistida. Ele não
implementa parsing, não cria registros jurídicos e não altera o schema. A captura
bruta continua sendo a evidência documental imutável.

Pergunta central:

> Como transformar deterministicamente a captura HTML real da CF/88 e do ADCT
> em uma árvore jurídica rastreável, sem perder informação de auditoria e sem
> confundir apresentação HTML com semântica jurídica?

## 2. Escopo

Inclui:

- decoding determinístico dos bytes persistidos;
- inventário e análise do DOM real;
- reconhecimento candidato de preâmbulo, divisões e dispositivos;
- separação entre CF/88 e ADCT;
- distinção entre texto normativo, histórico e notas;
- identidade, hierarquia e ordem de `LegalElement`;
- criação, idempotência e atomicidade futuras de `LegalVersion`;
- invariantes e fixtures propostas para a Fase 4B.

Não inclui parsing executável, canonicalização do HTML, modificação de
`raw_bytes`, ingestão de normas referenciadas, chunking, FTS, embeddings,
retrieval, Evidence Engine, Citation Validator ou uso de LLM.

## 3. Captura analisada

| Campo | Valor |
|---|---|
| `document_id` | `27f0ff6b-dd9e-4c4e-ba56-c34984f691e1` |
| `url_source` | `https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm` |
| Tamanho persistido | 1.839.482 bytes |
| HTTP | 200 |
| `Content-Type` | `text/html` |
| `Content-Length` | 1.839.482 |
| ETag | `"1c0b63-6584ba7465d85"` |
| Last-Modified | `Wed, 05 Aug 2026 12:10:12 GMT` |
| SHA-256 | `25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d` |

A análise foi feita sobre `SourceDocument.raw_bytes` lido do PostgreSQL. Não
houve novo download, nova ingestão nem gravação de representações derivadas no
banco.

Os metadados também registram a URL final, cadeia de redirects, headers
repetidos, duração, tentativas, tamanho recebido, ETag e Last-Modified, conforme
a política aprovada na Fase 3. O script dinâmico `f5_cspm` permanece intacto e
fora do corpo normativo a ser interpretado.

## 4. Validação de integridade do SourceDocument

O SHA-256 foi recalculado diretamente sobre os 1.839.482 bytes recuperados do
banco:

```text
stored   = 25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d
computed = 25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d
```

A igualdade confirma que a investigação usou exatamente o artefato aceito na
Fase 3. O futuro parser deve repetir essa verificação antes de interpretar o
documento e falhar de forma fechada se houver divergência.

## 5. Encoding

### 5.1 Evidência observada

- o header `Content-Type` não declara `charset`;
- não existe `<meta charset>`;
- não existe `<meta http-equiv="Content-Type">`;
- o único `meta` encontrado informa `Microsoft FrontPage 6.0` como gerador;
- UTF-8 estrito falha no byte 102, em texto português como
  `Constitui\xe7\xe3o`;
- Windows-1252 estrito decodifica o arquivo inteiro sem substituições;
- há seis bytes `0x92`, empregados corretamente como apóstrofo tipográfico em
  nomes como `Carlos De’Carli`, `Carlos Sant’Anna` e `Roberto D’Ávila`;
- ISO-8859-1 mapearia `0x92` para um controle C1, portanto não representa
  corretamente esses caracteres.

### 5.2 Regra candidata

Para este adapter e esta família documental:

1. consultar, pela ordem, BOM, charset HTTP e declarações `meta`;
2. registrar qualquer declaração encontrada e divergências entre elas;
3. na ausência de declaração, usar o fallback explícito
   `windows-1252`, versionado no parser do Planalto;
4. realizar decoding estrito, sem `errors="ignore"` e sem substituição
   silenciosa;
5. registrar encoding escolhido, origem da decisão e eventuais erros na
   proveniência do parsing.

Fluxo especificado:

```text
raw_bytes imutáveis
    -> verificação SHA-256
    -> detecção/fallback documentado de encoding
    -> decoding estrito Windows-1252
    -> Unicode para análise estrutural
```

O texto Unicode é uma projeção derivada; ele não substitui os bytes nem serve
para recalcular o hash documental.

## 6. Anatomia geral do HTML

O documento é HTML legado e heterogêneo, produzido e atualizado por ferramentas
e estilos diferentes. Ele combina tags de apresentação (`font`, `align`, estilos
inline), classes do Microsoft Office (`MsoNormal`), classes recentes
(`dou-paragraph`, `dou-strong`), âncoras nominais e marcação editorial.

Peculiaridade crítica: o raw fecha `</body></html>` no byte 133.966, linha 3.878,
mas aproximadamente 1,7 MB de conteúdo continuam depois desse fechamento. O
`lxml.html.document_fromstring` direto reteve somente 476 parágrafos e 46
`strike`, descartando a maior parte normativa. `BeautifulSoup` com
`html.parser` preservou 4.338 parágrafos, 7.402 âncoras e 773 `strike`, inclusive
o fim do ADCT, e forneceu linhas de origem.

O DOM reparado pelo parser é necessariamente uma interpretação do HTML
malformado. Por isso, a Fase 4B deve congelar parser e versão de runtime, manter
fixtures de regressão e validar cobertura do início ao fim; não basta aceitar que
o parser retornou um DOM.

Também foram observados:

- `id="art"` repetido 79 vezes, portanto IDs HTML não são chaves confiáveis;
- 4.820 âncoras com `name`, 4.819 nomes distintos e uma duplicidade
  (`sadctart101.0`);
- nomes diferentes apontando para o mesmo dispositivo;
- tags malformadas como `p<a` e erros de fechamento;
- 100 erros reportados pelo `lxml` direto: 78 IDs redefinidos e 22
  incompatibilidades de fechamento de tags;
- nenhum comentário HTML;
- navegação, cabeçalho institucional, assinaturas e scripts no mesmo artefato.

## 7. Inventário estrutural

### 7.1 Tags e classes

Contagens do DOM recuperado com `BeautifulSoup(..., "html.parser")`:

| Estrutura | Quantidade |
|---|---:|
| `a` | 7.402 |
| `p` | 4.338 (4.326 não vazios) |
| `font` | 1.812 |
| `span` | 813 |
| `strike` | 773 |
| `i` | 93 |
| `b` | 83 |
| `div` | 80 |
| `strong` | 52 |
| `sup` | 10 |
| `blockquote` | 7 |
| `u` | 7 |
| `table` | 2 |
| `script` | 2 |
| `s` | 0 |
| `del` | 0 |
| comentários HTML | 0 |

Classes mais frequentes:

| Classe | Quantidade |
|---|---:|
| `dou-paragraph` | 279 |
| `cstf` | 275 |
| `MsoNormal` | 267 |
| `c927` | 147 |
| `dou-strong` | 49 |

As duas tabelas são de apresentação: uma contém o cabeçalho institucional e
outra, a navegação inicial. Não foi encontrada tabela normativa.

### 7.2 Padrões textuais

As contagens abaixo consideram parágrafos não vazios e incluem variantes
históricas repetidas:

| Padrão no início do parágrafo | CF/88 | ADCT | Total |
|---|---:|---:|---:|
| `Art. <número>` | 339 | 173 | 512 |
| `§ <número>` | 937 | 315 | 1.252 |
| `Parágrafo único` | 78 | 37 | 115 |
| inciso romano + hífen | 1.408 | 299 | 1.707 |
| alínea + `)` | 362 | 72 | 434 |
| título | 10 | 0 | 10 |
| capítulo | 35 | 0 | 35 |
| seção | 53 | 0 | 53 |
| subseção | 5 | 0 | 5 |

Não foi encontrado padrão robusto de item numérico no início de parágrafo.
Isso não autoriza concluir que itens não existam semanticamente; a Fase 4B deve
ter um caso explícito de detecção e rejeição/registro de formas desconhecidas.

Artigos têm repetições consideráveis: os 339 blocos da CF representam 276
rótulos distintos; os 173 do ADCT representam 148 rótulos distintos. Exemplos
de repetição são os artigos 6º, 60, 76 e 115, por preservação de redações
anteriores. Assim, `documento + tipo + número` ainda não identifica uma
ocorrência HTML.

### 7.3 Links, scripts e notas

- 2.582 âncoras possuem `href`;
- 2.232 URLs relativas apontam para Emendas Constitucionais;
- há 72 URLs HTTP(S) absolutas, principalmente para STF;
- também há links para leis, decretos, medidas provisórias, ADIs, regulamentos,
  documentos de vigência, PDF e índice;
- o script externo é `../integracao/js/stf.js`;
- o script inline tem `id="f5_cspm"` e pertence à infraestrutura F5.

Ocorrências textuais observadas, sem afirmar equivalência um-para-um com notas:

| Sinal textual | Ocorrências |
|---|---:|
| `Redação dada pela Emenda Constitucional` | 569 |
| `Incluído pela Emenda Constitucional` | 1.378 no texto global; 1.377 parágrafos afetados |
| `Revogado pela Emenda Constitucional` | 54 |
| `Vide Emenda Constitucional` | 65 |
| `Vide Lei` | 36 |
| `Vide ADI`/`Vide ADIN` | ao menos 62 ocorrências textuais; 47 parágrafos com `Vide ADI` |
| `Regulamento` | 53 ocorrências textuais; 48 parágrafos afetados |
| `Vigência` | 82 |

Essas expressões aparecem frequentemente em links e entre parênteses, mas a
marcação não é uniforme. A classificação deve combinar delimitação textual,
relação com âncoras e contexto, nunca apenas tag ou CSS.

## 8. Estrutura da CF/88

A região normativa da CF inicia no marcador central `PREÂMBULO`, seguido do
texto preambular, `TÍTULO I`, sua rubrica e o artigo 1º. A hierarquia visual
observada segue, em geral:

```text
CF/88
├── PREÂMBULO
├── TÍTULO
│   ├── rubrica do título
│   ├── CAPÍTULO
│   │   ├── rubrica do capítulo
│   │   ├── SEÇÃO
│   │   │   ├── rubrica da seção
│   │   │   └── SUBSEÇÃO (quando presente)
│   │   └── ARTIGO e subdivisões
└── fecho, assinaturas e aviso editorial
```

Não existe wrapper DOM confiável para cada ramo. Divisões e dispositivos são,
em grande parte, parágrafos irmãos em ordem linear. Rubrica e marcador (`TÍTULO
I` / `Dos Princípios Fundamentais`) ocupam parágrafos distintos. O parser deve
ser uma máquina de estados sobre a sequência documental, e não uma tradução
direta de aninhamento de tags.

O fim da CF é marcado pelo artigo 250, seguido de data, signatários,
participantes, `In Memoriam` e o aviso `Este texto não substitui o publicado no
D.O.U.`. Esses blocos não são dispositivos, mas devem ser classificados e
preservados como material documental/editorial.

## 9. Estrutura do ADCT

O ADCT aparece no mesmo payload, depois do fecho editorial da CF, sob o marcador
centralizado `ATO DAS DISPOSIÇÕES CONSTITUCIONAIS TRANSITÓRIAS`. Não foram
encontrados títulos, capítulos, seções ou subseções no ADCT. Sua estrutura é uma
sequência de artigos e subdivisões, com várias camadas históricas.

O primeiro dispositivo é `Art. 1º.` e o último artigo observado é `Art. 138.`.
Há artigos alfanuméricos, como `116-A`, e muita repetição de rótulo causada por
alterações constitucionais. O artigo 60, por exemplo, possui sucessivas redações
riscadas, cada uma com sua própria árvore de incisos e alíneas, antes da redação
seguinte.

Depois do artigo 138 aparecem novamente data, signatários, participantes,
`In Memoriam` e separador. Esses elementos delimitam o fim documental, mas não
integram a árvore normativa.

## 10. Transição CF -> ADCT

Foram encontradas duas ocorrências exatas do nome do ADCT:

1. uma no menu de navegação inicial;
2. o cabeçalho documental real, no parágrafo não vazio 3.421, imediatamente
   depois do fecho e aviso editorial da CF.

Portanto, a primeira correspondência textual não pode ser usada como separador.
O separador candidato deve satisfazer conjuntamente: estar fora da tabela de
navegação, ocorrer depois do artigo final/fecho da CF, ter alinhamento central e
ser seguido pelo conjunto de notas iniciais e pelo `Art. 1º.` com âncoras ADCT
(`sadctart1`, `adctart1`, `art1adct`, `dtart1`).

### 10.1 Alternativas de representação

**Um LegalAct e uma LegalVersion com dois domínios internos.** Mantém a unidade
física do HTML, mas mistura dois sistemas de numeração, torna `Art. 1º` ambíguo e
contraria a descrição atual de `LegalAct`, que cita CF/88 e ADCT como atos.

**Dois LegalActs, cada qual com uma LegalVersion, ligados ao mesmo
SourceDocument.** Preserva a captura física única, remove colisões entre artigos,
permite evolução e consulta independentes e corresponde ao modelo conceitual
existente. Exige que uma execução de parsing produza e valide os dois resultados
na mesma transação.

**Um LegalAct composto com subatos.** Representaria a relação jurídica, mas o
modelo atual não possui relação entre atos e a complexidade não demonstrou ganho
para o MVP.

### 10.2 Recomendação

Usar `LegalAct(CF88)` e `LegalAct(ADCT)`, com uma `LegalVersion` de cada ato
referenciando o mesmo `SourceDocument`. A captura documental continua uma; a
separação ocorre somente na interpretação jurídica. A decisão precisa de
aprovação humana antes da Fase 4B.

## 11. Padrões de títulos, capítulos e seções

Os marcadores usam texto como `TÍTULO II`, `CAPÍTULO III`, `Seção I` e
`Subseção II`, geralmente centralizado. A caixa varia. A rubrica aparece no
parágrafo imediatamente seguinte, também centralizado.

Regra candidata:

1. reconhecer o marcador por gramática textual ancorada, tolerante a caixa e
   espaços, mas não por `strong`/`align` isoladamente;
2. validar numeral romano e sequência esperada;
3. consumir como rubrica o próximo parágrafo centralizado que não seja outro
   marcador ou dispositivo;
4. abrir/fechar o contexto hierárquico conforme o nível;
5. registrar divergências em vez de inventar hierarquia.

Há marcadores históricos riscados (um título, dois capítulos e duas seções na
contagem). Eles não podem substituir silenciosamente o ramo corrente.

## 12. Padrões de artigos

O padrão principal é `Art.` seguido por número, eventualmente sufixo alfabético
(`116-A`), pontuação variável e o caput no mesmo parágrafo. Exemplos reais
incluem `Art. 1º`, `Art. 12.`, `Art.246.` e `Art. 60.Nos`, mostrando que espaço e
pontuação não são uniformes.

Regra candidata:

- reconhecer `Art` + ponto opcional controlado + espaços opcionais + número +
  sufixo alfabético opcional + ordinal/ponto opcional;
- preservar a grafia encontrada em `number_label` e manter uma forma canônica
  auxiliar somente para comparação;
- separar o rótulo do texto do caput sem alterar a pontuação do texto;
- abrir um novo contexto de artigo e encerrar o anterior;
- permitir ocorrências repetidas do mesmo rótulo, classificadas por status e
  ordem documental;
- nunca escolher a redação vigente apenas por ser a última sem validar os
  sinais editoriais e o grupo completo.

## 13. Padrões de parágrafos

Foram observados `§ 1º`, `§ 21.`, variantes com hífen e `Parágrafo único.`.
O parágrafo pertence ao artigo aberto mais próximo, salvo quando integrar um
bloco histórico do mesmo artigo.

Regra candidata:

- reconhecer `§` e numeral/sufixo, ou a expressão ancorada `Parágrafo único`;
- preservar grafia e pontuação originais;
- criar `PARAGRAPH` filho do artigo corrente;
- tratar `Parágrafo único` como rótulo semântico próprio, não como `§ 1º`;
- falhar na validação se não houver artigo ancestral compatível.

O `caput` deve ser representado explicitamente como filho `CAPUT` do artigo, ou
como campo próprio bem especificado. Recomenda-se o nó `CAPUT`, pois ele permite
status, notas, links e chunks futuros sem tratamento especial.

## 14. Padrões de incisos

Incisos aparecem como numeral romano seguido de hífen e texto no mesmo
parágrafo. Podem ser filhos do caput, de parágrafo ou, em redações históricas,
de um bloco histórico específico.

Regra candidata:

- gramática ancorada para numeral romano válido + separador;
- pai = subdivisão normativa aberta mais próxima que admite inciso;
- reiniciar contexto de alínea quando surgir novo inciso;
- validar numeral e progressão, registrando lacunas sem preencher dispositivos;
- não confundir numeral romano em nota ou cabeçalho com inciso.

## 15. Padrões de alíneas e itens

Alíneas aparecem como letra minúscula seguida de `)`, no mesmo parágrafo. O
artigo 12 demonstra `a)`, `b)` e várias ocorrências históricas de `c)`. No ADCT,
o artigo 60 apresenta estrutura profunda artigo -> inciso III -> alíneas `a` a
`e`.

Regra candidata:

- reconhecer letra + `)` apenas em contexto que admita alínea;
- pai preferencial = inciso corrente; admitir parágrafo somente quando a
  gramática jurídica observada o justificar;
- fechar alíneas ao mudar inciso/parágrafo/artigo;
- preservar repetições históricas por ordem e status.

Não houve evidência suficiente para fixar uma gramática de item numérico. A
Fase 4B deve incluir detecção de linhas residuais e relatório de formas não
classificadas, em vez de absorvê-las silenciosamente como texto do nó anterior.

## 16. Redações anteriores

O documento preserva sucessões completas de redações. No artigo 6º da CF, duas
redações intermediárias estão riscadas e acompanhadas de nota `Redação dada`,
antes de uma redação posterior não riscada. No artigo 12, alínea `c`, o rótulo e
a pontuação podem ficar fora de `<strike>`, enquanto apenas o miolo textual fica
riscado.

Consequências:

- `strike` é um sinal de apresentação histórica, não uma conclusão jurídica
  autossuficiente;
- a unidade de classificação é o parágrafo/dispositivo completo, ainda que o
  risco cubra apenas parte de seus descendentes;
- `Redação dada` é uma nota de proveniência da redação, não texto normativo;
- todas as ocorrências devem ser preservadas e vinculadas em ordem.

Taxonomia candidata de status do texto:

- `CURRENT_TEXT`: redação apresentada como corrente;
- `HISTORICAL_TEXT`: redação anterior preservada;
- `REVOKED_TEXT`: dispositivo explicitamente revogado;
- `UNRESOLVED_TEXT_STATUS`: sinais contraditórios ou insuficientes, que impedem
  ativar a versão para consulta até revisão.

## 17. Dispositivos revogados

Foram encontrados 54 parágrafos com a expressão `Revogado pela Emenda
Constitucional`. Em exemplos reais, o dispositivo está riscado e a nota pode
estar dentro ou fora da mesma marcação. Também há dispositivos que foram
incluídos, depois revogados, acumulando duas notas.

O booleano atual `LegalElement.is_revoked` não é suficiente. Ele não distingue
uma redação anterior substituída de um dispositivo expressamente revogado, não
representa status desconhecido e não permite modelar uma nota editorial
separadamente. Mantê-lo pode ser útil como projeção derivada (`status ==
REVOKED_TEXT`), mas não como fonte primária da classificação.

Regra candidata conservadora:

1. `Revogado...` explicitamente associado ao dispositivo -> `REVOKED_TEXT`;
2. risco + redação posterior do mesmo localizador -> `HISTORICAL_TEXT`;
3. risco sem evidência contextual suficiente -> `UNRESOLVED_TEXT_STATUS`;
4. ausência de risco não basta, isoladamente, para declarar vigência;
5. nunca apagar texto riscado.

## 18. Notas editoriais

Notas aparecem inline no mesmo `<p>` do dispositivo, usualmente entre
parênteses e frequentemente como links, mas com variações de pontuação, caixa
e espaçamento. Exemplos:

- `(Redação dada pela Emenda Constitucional nº ...)`;
- `(Incluído pela Emenda Constitucional nº ...)`;
- `(Revogado pela Emenda Constitucional nº ...)`;
- `(Vide Emenda Constitucional ...)`;
- `(Vide Lei ...)`;
- `(Vide ADIN 3392)`;
- `(Regulamento)`;
- `Vigência` e `Produção de efeito`.

O parser deve extrair a nota como elemento/registro separado e preservar o texto
exato, o link e a associação ao dispositivo. Remover a nota do texto normativo
normalizado somente é aceitável depois de preservá-la estruturalmente e validar
que nenhum caractere normativo foi capturado junto.

## 19. Referências a Emendas

As 2.232 URLs relativas relacionadas a Emendas formam a maior classe de links.
Elas podem indicar inclusão, nova redação, revogação, simples remissão ou
vigência. Portanto, o alvo do link não determina sozinho a natureza da relação.

Preservação candidata:

- texto original da nota;
- categoria e subtipo inferido pela gramática;
- `href` original, sem reescrita;
- URL resolvida contra `url_source` como campo derivado;
- texto da âncora;
- ordem da nota dentro do dispositivo;
- localizador do elemento de origem.

O MVP não deve baixar nem interpretar as Emendas vinculadas.

## 20. Links externos

Foram encontrados links para STF (`portal.stf.jus.br`, `www.stf.jus.br`), leis,
decretos, medidas provisórias, regulamentos e outros artefatos do Planalto. Eles
são proveniência editorial relevante mesmo fora do corpus do MVP.

Recomenda-se preservá-los como referências estruturadas ligadas ao elemento,
com `href` original, URL resolvida, texto da âncora, categoria e ordem. Isso não
transforma o documento externo em fonte ingerida nem amplia o corpus; apenas
evita perda de informação auditável.

## 21. Classificação normativa versus editorial

Taxonomia candidata:

| Papel | Conteúdo |
|---|---|
| `NORMATIVE_TEXT` | preâmbulo, rubrica e texto de dispositivo |
| `AMENDMENT_NOTE` | incluído, redação dada, revogado por EC |
| `REFERENCE_NOTE` | vide norma, ADI/ADIN, regulamento |
| `EFFECT_NOTE` | vigência, produção de efeito |
| `EDITORIAL_NOTE` | aviso do DOU, separadores e informação editorial |
| `EXTERNAL_REFERENCE` | link preservado para documento fora do corpus |
| `SIGNATURE_BLOCK` | data, signatários, participantes e `In Memoriam` |
| `NAVIGATION` | menu e atalhos iniciais |
| `INFRASTRUCTURE` | scripts, inclusive F5, e elementos técnicos |
| `UNCLASSIFIED` | conteúdo não reconhecido que exige relatório/validação |

A classificação deve resultar de regras versionadas. Elementos
`UNCLASSIFIED` não podem desaparecer; acima de limites aprovados, impedem o
parsing de ser ativado para consulta.

## 22. Proposta de árvore LegalElement

Para cada `LegalVersion`:

```text
DOCUMENT_ROOT (CF88 ou ADCT)
├── PREAMBLE [somente CF]
├── TITLE [somente CF]
│   └── CHAPTER
│       └── SECTION
│           └── SUBSECTION
├── ARTICLE
│   ├── CAPUT
│   │   └── ITEM_ROMAN
│   │       └── ITEM_LETTER
│   └── PARAGRAPH
│       └── ITEM_ROMAN
│           └── ITEM_LETTER
├── ANNOTATION / REFERENCE (associada ao nó afetado)
└── DOCUMENTARY_BLOCK (fecho/assinaturas, fora do texto de consulta)
```

Os nomes finais de `element_type` devem ser aprovados e congelados. A rubrica de
uma divisão pode ficar no próprio nó, desde que seu texto e localizador sejam
preservados. Redações históricas devem formar ocorrências distintas, associadas
ao mesmo localizador jurídico auxiliar, nunca sobrescrever a corrente.

## 23. Identidade e path

`LegalElement.id` continua sendo a identidade primária/semântica persistida;
`path` continua auxiliar e denormalizado. Uma chave natural auxiliar candidata
para reconhecer um local jurídico é:

```text
legal_act/domain
  + ancestry canônica
  + element_type
  + number_label canônico
```

Para reconhecer uma ocorrência concreta no documento, acrescentar:

```text
text_status
  + document_order
  + occurrence_index entre localizadores repetidos
```

Isso evita colisões entre `Art. 1º` da CF e do ADCT, entre `§ 1º` de artigos
diferentes e entre incisos/alíneas de ancestrais diferentes. As âncoras HTML
podem ser armazenadas como sinais auxiliares, mas não são identidade: o artigo
1º da CF possui simultaneamente `cf-88-parte-1-titulo-1-artigo-1`, `art1` e `1`,
enquanto o artigo 1º do ADCT possui quatro nomes diferentes, e existe ao menos
uma âncora duplicada.

O `path` recomendado é legível e regenerável, por exemplo
`cf88/titulo-ii/capitulo-i/art-5/inciso-lxxviii`, com sufixo explícito para uma
ocorrência histórica. Ele não deve ser usado como PK nem como única garantia de
unicidade.

IDs aleatórios não permitem reconhecer semanticamente o mesmo resultado entre
reprocessamentos. UUIDv5 derivado da chave auxiliar é uma alternativa, mas
mudanças corrigidas de ancestralidade alterariam o ID. Recomenda-se manter UUID
como identidade persistida e usar uma chave auxiliar física/versionada para
idempotência; esta decisão requer aprovação.

## 24. Ordem documental

Resposta à pergunta obrigatória: **não, o modelo atual não garante a reconstrução
determinística da ordem total sem depender de comportamento incidental**.

`parent_id` representa somente hierarquia. `ordinal` é anulável, não possui
unicidade e sua semântica global ou entre irmãos não está definida. UUID, `path`
textual e ordem de retorno do banco não são substitutos.

Recomendação: adicionar `document_order BIGINT NOT NULL`, monotônico na
sequência integral de cada `LegalVersion`, com unicidade
`(legal_version_id, document_order)`. Manter `ordinal` como ordinal jurídico ou
ordem local entre irmãos, com semântica documentada. Essa separação preserva a
posição de notas e redações históricas no fluxo original.

## 25. raw_text versus normalized_text

### 25.1 `raw_text`

`raw_text` deve ser a projeção Unicode fiel do texto pertencente ao nó, após
decoding estrito e resolução normal do HTML, antes de normalização textual.
Deve:

- preservar acentos, pontuação, quebras e whitespace significativo observado;
- preservar NBSP como `U+00A0` e registrar entidades resolvidas pelo parser;
- preservar texto riscado em seu nó histórico/revogado;
- excluir filhos normativos e notas apenas se estes forem simultaneamente
  preservados como nós separados, evitando duplicação;
- nunca ser confundido com `SourceDocument.raw_bytes` nem com HTML bruto.

Como a projeção do DOM perde a grafia literal de entidades e tags, o parser deve
armazenar um localizador de origem e, idealmente, hash do fragmento/linhas de
origem para retornar aos bytes oficiais.

### 25.2 `normalized_text`

`normalized_text` deve ser derivado deterministicamente de `raw_text`:

1. normalização Unicode NFC;
2. CRLF/CR para LF;
3. NBSP e espaços equivalentes para espaço comum;
4. colapso de runs de whitespace e quebras editoriais, mantendo limites de nó;
5. trim nas bordas;
6. preservação de acentos, caixa, números, sinais, aspas e pontuação jurídica.

Não corrigir ortografia (`Assembléia`, `cinqüenta`), não atualizar grafia,
não renumerar, não remover texto por aparente revogação e não incorporar ou
remover notas sem classificação estrutural registrada.

## 26. Criação de LegalVersion

Uma captura HTTP é uma versão documental; um resultado do algoritmo é uma
execução de parsing. **São conceitos diferentes.** ETag, Last-Modified e data de
captura também não provam, isoladamente, uma nova versão jurídica.

Fluxo candidato:

```text
SourceDocument íntegro
  -> ParsingRun(parser_name, parser_version, regras de decoding)
  -> duas LegalVersions derivadas (CF88 e ADCT)
  -> validações
  -> ativação conjunta para consulta
```

`version_label` deve identificar a captura documental de forma neutra, por
exemplo data de aquisição + prefixo do SHA-256, sem alegar data de vigência
jurídica. `source_document_id` é a proveniência obrigatória.

`is_active_for_query` somente pode ser verdadeiro depois de parsing e validação
completos. Uma captura futura com bytes diferentes gera novo SourceDocument e
novos resultados candidatos; não desativa automaticamente a versão anterior
antes do aceite estrutural.

Um parser v2 sobre o mesmo SourceDocument deve produzir nova execução de
parsing auditável, sem fingir que houve mudança documental. Recomenda-se uma
entidade `ParsingRun` separada; guardar apenas `parser_version` no JSON de
`LegalVersion` é uma alternativa menor, mas não oferece unicidade ou integridade
física adequadas.

## 27. Idempotência

Comportamento recomendado para `parse(document_id)`:

- buscar `ParsingRun` concluído para `(source_document_id, parser_name,
  parser_version)`;
- se existir, validar que as duas LegalVersions e seus invariantes permanecem
  íntegros e retornar `ALREADY_PARSED`;
- se não existir, criar todo o resultado em uma transação;
- uma execução concorrente deve ser serializada por unicidade física e tratar a
  colisão como `ALREADY_PARSED`;
- `force` para a mesma versão, se futuramente aprovado, deve substituir o
  resultado apenas atomicamente e conservar registro de auditoria;
- parser com versão diferente gera novo `ParsingRun`; não sobrescreve
  silenciosamente o anterior;
- ativar o resultado novo somente após validação e decisão explícita.

`upsert` elemento a elemento não é recomendado: ele pode misturar resultados de
versões de algoritmo e deixar elementos obsoletos.

## 28. Atomicidade

A unidade transacional recomendada é a captura completa, incluindo CF e ADCT:

```text
verificar raw SHA-256
BEGIN
  criar/buscar LegalActs canônicos
  criar ParsingRun em estado interno
  construir LegalVersion(CF)
  construir LegalVersion(ADCT)
  persistir elementos, notas e referências
  executar validações estruturais e de cobertura
  marcar resultado como validado/ativo conforme política
COMMIT
```

Qualquer falha no artigo N, decoding, classificação crítica, integridade ou
cobertura deve causar `ROLLBACK`. Nenhuma LegalVersion parcialmente parseada
deve ser visível. Diagnósticos podem ser emitidos em log/relatório fora da
transação, sem copiar HTML bruto para outro armazenamento permanente.

Critérios mínimos de validade:

- SHA-256 e decoding verificados;
- marcador real de CF e transição para ADCT reconhecidos uma única vez no corpo;
- primeiro e último artigos esperados de ambos os domínios presentes;
- todos os parágrafos do intervalo documental classificados ou explicitamente
  contabilizados;
- nenhuma unidade normativa descartada;
- hierarquia, ordem, status e referências íntegros;
- contagens e fingerprints estruturais dentro da política aprovada;
- zero erro estrutural de severidade impeditiva.

## 29. Invariantes

Invariantes candidatos a testes da Fase 4B:

1. todo `LegalElement` pertence a exatamente uma `LegalVersion`;
2. `parent_id` nulo somente para raiz permitida;
3. pai e filho pertencem à mesma `LegalVersion`;
4. nenhum elemento é seu próprio ancestral e a árvore não possui ciclos;
5. existe exatamente uma raiz por LegalVersion;
6. todo artigo pertence ao domínio CF ou ADCT correto;
7. `Art. 1º` da CF e do ADCT nunca colidem;
8. caput, parágrafo, inciso e alínea têm ancestrais compatíveis;
9. nenhum parágrafo, inciso ou alínea fica órfão;
10. `document_order` é único, total, crescente e estável por versão;
11. a travessia por `document_order` reproduz a ordem observada no HTML;
12. números e sufixos de artigo são preservados e canonicamente comparáveis;
13. `raw_text` nunca perde texto normativo ou riscado;
14. `normalized_text` é função pura, idempotente e não altera semântica;
15. toda nota removida do texto normativo possui representação estruturada;
16. todo link preserva `href` original, texto e ordem;
17. `REVOKED_TEXT` exige evidência editorial explícita registrada;
18. texto apenas riscado sem evidência suficiente não é declarado revogado;
19. uma redação corrente e suas anteriores permanecem distinguíveis;
20. menu, scripts F5 e assinaturas não entram como texto normativo;
21. o parser alcança o artigo 250 da CF e o artigo 138 do ADCT;
22. nenhuma cauda após o `</html>` prematuro é descartada;
23. parsing repetido com mesma versão retorna resultado semanticamente idêntico
    e não duplica registros;
24. falha em qualquer ponto não deixa estado parcial;
25. resultado novo não se torna ativo antes da validação completa.

## 30. Golden fixtures propostas

As fixtures devem ser cópias mínimas e fiéis de trechos da captura identificada,
com comentário de origem (document ID, SHA-256, linhas/ordem), sem corrigir HTML:

| Fixture | Região real e caso coberto |
|---|---|
| `fixture_01_inicio_preambulo_art1.html` | menu falso, preâmbulo, Título I, art. 1º e incisos |
| `fixture_02_art12_hierarquia.html` | art. 12, incisos, alíneas, parágrafos e estrutura profunda |
| `fixture_03_art6_redacoes.html` | sucessivas redações riscadas e corrente do art. 6º |
| `fixture_04_revogado_explicito.html` | dispositivo riscado com nota `Revogado pela EC` |
| `fixture_05_art5_notas_links.html` | notas de EC, ADI/ADIN, lei, regulamento e múltiplos links |
| `fixture_06_fim_cf_transicao_adct.html` | art. 250, assinaturas, aviso DOU, marcador ADCT e art. 1º |
| `fixture_07_adct_art60_historico_profundo.html` | múltiplas redações, parágrafos, incisos e alíneas |
| `fixture_08_adct_art116a_117.html` | artigo alfanumérico, redação anterior e corrente recente |
| `fixture_09_adct_art134_138.html` | classes modernas, estrutura profunda e fim documental |
| `fixture_10_html_fechamento_prematuro.html` | contexto antes/depois de `</body></html>` na linha 3.878 |

As fixtures não foram criadas nesta fase. A extração futura deve ser feita por
intervalos comprováveis dos bytes/texto decodificado, preservando a marcação
original e registrando um hash de cada fixture.

## 31. Estratégia recomendada de parser

### 31.1 Biblioteca

Recomenda-se `BeautifulSoup4` com backend explícito `html.parser` para esta fonte,
sob a versão Python travada pelo projeto. Na captura real ele preservou a cauda
fora do `</html>`, manteve as contagens integrais e forneceu `sourceline`.

`lxml` direto é mais rápido e oferece XPath, mas descartou a maior parte do
documento devido ao fechamento prematuro. `BeautifulSoup(..., "lxml")` recuperou
as mesmas estruturas principais, mas sem linhas de origem nesta execução. Ele
pode ser usado em análise auxiliar, não como caminho principal sem resolver e
testar a perda de cauda. Não é necessária nova dependência.

### 31.2 Pipeline determinístico

1. carregar `SourceDocument` e verificar SHA-256;
2. decidir encoding por regras versionadas e decodificar estritamente;
3. construir DOM recuperado sem modificar `raw_bytes`;
4. localizar intervalos de navegação, CF, transição, ADCT e fechos;
5. linearizar parágrafos relevantes conservando linha e ordem;
6. tokenizar cada bloco em texto normativo, marcação de risco, notas e links;
7. alimentar máquina de estados de divisões e dispositivos;
8. classificar status textual por regras conservadoras;
9. construir duas árvores em memória;
10. validar cobertura, hierarquia, status, ordem e contagens;
11. persistir tudo atomicamente e registrar versão do parser.

O parser funciona offline. Regex reconhece gramática local, mas o estado
jurídico e o contexto determinam o pai. CSS, tag, âncora e texto são sinais
complementares; nenhum deles, isoladamente, define semântica.

### 31.3 Amostragem estratificada investigada

| Amostra | Estrutura/texto observado | Sinais e regra candidata | Dificuldade |
|---|---|---|---|
| A. Início | menu, preâmbulo, Título I, art. 1º | marcador fora da tabela + sequência centralizada; máquina de estados | menu repete nomes antes do corpo |
| B. Direitos fundamentais | art. 5º com muitos incisos e notas | artigo abre contexto; romanos viram filhos; notas/links separados | alta densidade de EC, ADI e regulamento |
| C. Estrutura profunda | art. 12: inciso I -> alíneas; depois parágrafos e incisos | prefixos ancorados + contexto aberto | alínea `c` e outros locais repetidos por histórico |
| D. Redação alterada | art. 6º em redações sucessivas | agrupar mesmo localizador por ordem, risco e notas | `Redação dada` não implica que aquela ocorrência ainda seja corrente |
| E. Revogado/riscado | incisos e parágrafos com `Revogado pela EC` | nota explícita autoriza `REVOKED_TEXT` | risco pode cobrir só parte do `<p>` |
| F. Múltiplas referências | art. 5º, inclusive § 3º, combina EC, ADIN e atos decorrentes | extrair cada nota/link em ordem | texto e notas compartilham o mesmo parágrafo |
| G. Fim da CF | arts. 246 com três redações, 247-250, assinaturas e aviso DOU | artigo 250 + fecho editorial delimitam CF | material documental não normativo entre CF e ADCT |
| H. Início do ADCT | marcador, notas gerais e art. 1º | âncoras ADCT + posição após fecho CF | marcador também existe no menu |
| I. Meio do ADCT | art. 60 e sucessivas redações profundas | contexto histórico precisa carregar filhos correspondentes | vários arts. 60 completos e riscados |
| J. ADCT recente | arts. 116-A/117 e 134-138 com EC 132/136 | aceitar sufixos, classes modernas e notas recentes | mistura de `MsoNormal`, `dou-paragraph` e estilos inline |

## 32. Riscos conhecidos

- HTML malformado e fechamento prematuro podem causar perda silenciosa de 90%
  do documento dependendo do parser;
- mudança de versão do parser/CPython pode alterar o DOM reparado;
- CSS e tags variam por período de edição;
- âncoras e IDs são redundantes, ausentes ou duplicados;
- pontuação e espaçamento de rótulos são inconsistentes;
- redações históricas formam subárvores, não apenas linhas isoladas;
- `strike` parcial e notas inline tornam seletores simples inseguros;
- uma atualização do Planalto pode introduzir padrão não coberto;
- F5 muda raw SHA-256 sem mudança material, mas não deve ser canonicalizado;
- `Last-Modified`/ETag são validators HTTP, não vigência jurídica;
- regras excessivamente permissivas podem classificar navegação ou notas como
  norma; regras excessivamente estritas podem omitir dispositivos;
- o modelo atual não representa toda a proveniência e os estados observados.

## 33. Decisões abertas

Exigem aprovação humana antes da Fase 4B:

1. dois LegalActs (CF e ADCT) compartilhando o SourceDocument;
2. adoção de `BeautifulSoup` + `html.parser` como parser congelado;
3. taxonomias de `element_type`, papel do conteúdo e status textual;
4. representação explícita de `CAPUT`;
5. campo global `document_order` e semântica de `ordinal`;
6. identidade auxiliar/estratégia de UUID entre reprocessamentos;
7. entidade `ParsingRun` separada da versão documental;
8. forma de preservar notas, links e localizadores de origem;
9. critério exato para ativar uma versão para consulta;
10. limites de conteúdo `UNCLASSIFIED` e divergências que causam falha;
11. política para `force` e reprocessamento por parser novo;
12. alterações de schema descritas a seguir.

ADR recomendado: **separação entre versão documental, execução de parsing e
status editorial do texto constitucional**. A decisão afeta identidade,
idempotência, auditoria, ativação de consulta e futuras migrations; por isso
deve ser congelada antes da implementação. Nenhum ADR foi criado nesta fase.

## 34. Alterações de schema propostas para aprovação

Nenhuma alteração foi aplicada. As propostas abaixo são cumulativas, mas podem
ser aprovadas separadamente.

### 34.1 Ordem documental total

**Problema observado:** `parent_id` não ordena a árvore; `ordinal` é anulável e
sem semântica/unicidade global.

**Evidência real:** notas e redações repetidas são parágrafos irmãos cuja ordem
define seu contexto.

**Alteração proposta:** `legal_elements.document_order BIGINT NOT NULL` e
`UNIQUE (legal_version_id, document_order)`; documentar `ordinal` como ordem
local/legal.

**Alternativas:** tornar `ordinal` global e obrigatório; guardar ordem somente em
JSON. A primeira perde a distinção de ordinal local; a segunda perde integridade
física.

**Impacto:** pequena coluna/index adicional e ordenação determinística.

**Migration necessária:** sim, futura.

**Compatibilidade com dados existentes:** tabelas jurídicas estão vazias no
checkpoint; adoção é direta antes da Fase 4B.

### 34.2 Status textual e papel do conteúdo

**Problema observado:** `is_revoked` não distingue corrente, histórico, revogado
e incerto; `element_type` sozinho mistura estrutura e papel editorial.

**Evidência real:** 773 `strike`, 54 notas explícitas de revogação e centenas de
redações anteriores/incluídas.

**Alteração proposta:** campo controlado `text_status` e campo `content_role`,
com CHECK/enum de aplicação versionado; `is_revoked` torna-se projeção derivada
ou é removido em migration aprovada.

**Alternativas:** codificar tudo em `element_type`; usar JSONB. Ambas reduzem
integridade e tornam consultas ambíguas.

**Impacto:** altera queries futuras e exige definição cuidadosa dos valores.

**Migration necessária:** sim, futura.

**Compatibilidade com dados existentes:** sem elementos persistidos; sem
backfill material no estado atual.

### 34.3 ParsingRun e idempotência física

**Problema observado:** `LegalVersion` representa uma captura estrutural, mas não
separa a captura documental da versão do algoritmo e não tem unicidade para
reprocessamento.

**Evidência real:** o mesmo SourceDocument deve poder ser processado por parser
v1 e v2 sem alegar duas versões jurídicas; uma execução produz CF e ADCT.

**Alteração proposta:** tabela `parsing_runs` com source document, nome/versão do
parser, encoding, status e timestamps; unicidade por
`(source_document_id, parser_name, parser_version)`; FK de `LegalVersion` para o
run e unicidade por `(parsing_run_id, legal_act_id)`.

**Alternativas:** colunas em `LegalVersion`; metadata JSONB e verificação apenas
na aplicação. Colunas são aceitáveis, mas duplicam dados entre CF/ADCT; JSONB não
oferece a mesma garantia.

**Impacto:** entidade e repository adicionais, com melhor auditoria e
concorrência.

**Migration necessária:** sim, futura.

**Compatibilidade com dados existentes:** `legal_versions = 0`; introdução sem
migração de resultados jurídicos.

### 34.4 Proveniência de DOM, notas e links

**Problema observado:** `LegalElement` não possui localizador de origem nem
estrutura adequada para notas/links repetidos.

**Evidência real:** 7.402 âncoras, 2.582 links, notas inline e HTML malformado;
texto Unicode sozinho não retorna ao fragmento original.

**Alteração proposta:** campos de proveniência (`source_line`,
`source_locator`, `source_fragment_hash`) e uma coleção estruturada para notas e
referências, preferencialmente tabelas filhas com ordem, texto, categoria,
`href_original` e URL resolvida.

**Alternativas:** `metadata JSONB` em `LegalElement`; notas como elementos filhos.
JSONB é menor, mas reduz constraints; elementos filhos podem funcionar se a
taxonomia e as associações forem suficientes.

**Impacto:** maior volume, melhor auditoria e futuras consultas de proveniência.

**Migration necessária:** sim, futura, conforme opção aprovada.

**Compatibilidade com dados existentes:** sem elementos; impacto somente na
implementação futura.

### 34.5 Integridade pai-filho na mesma versão

**Problema observado:** a FK atual de `parent_id` garante existência do pai, mas
não garante fisicamente que pai e filho pertençam à mesma `LegalVersion`.

**Evidência real:** a especificação exige duas árvores ligadas ao mesmo
SourceDocument; um vínculo cruzado seria semanticamente inválido.

**Alteração proposta:** constraint composta que force
`(parent_id, legal_version_id)` a referenciar um elemento da mesma versão, com a
chave/unique auxiliar necessária.

**Alternativas:** validação somente em serviço/evento SQLAlchemy. Ela é mais
simples, mas não garante integridade contra outras escritas.

**Impacto:** constraint e índice adicionais; repository deve preencher a versão
consistentemente.

**Migration necessária:** sim, futura.

**Compatibilidade com dados existentes:** sem elementos no banco atual.

## 35. Critérios de aceite da Fase 4B

1. decisões abertas e alterações de schema aprovadas antes do código;
2. parser determinístico, offline, sem LLM e sem download implícito;
3. nenhuma modificação ou canonicalização de `raw_bytes`;
4. SHA-256 verificado antes do parsing;
5. decoding Windows-1252 estrito para a captura estudada, com proveniência;
6. backend de HTML explicitamente fixado e cobertura após o fechamento prematuro;
7. golden fixtures aprovadas cobrindo todos os casos desta especificação;
8. CF e ADCT separados conforme decisão aprovada, com proveniência comum;
9. árvore, identidade auxiliar e ordem total determinísticas;
10. texto corrente, histórico, revogado e anotação distinguíveis;
11. links e notas preservados sem ingerir documentos externos;
12. `raw_text` e `normalized_text` obedecem às semânticas especificadas;
13. nenhuma unidade normativa ou histórica desaparece silenciosamente;
14. invariantes estruturais cobertos por testes unitários e de banco;
15. parsing repetido é idempotente e concorrência é protegida fisicamente;
16. falha em qualquer ponto produz rollback integral;
17. resultados de parser diferentes e versões documentais não são confundidos;
18. ativação para consulta ocorre somente depois de validação completa;
19. teste controlado sobre o SourceDocument real confirma os artigos finais,
    contagens, cobertura e integridade;
20. Ruff e toda a suíte de testes passam, sem alterar a lógica de ingestão.
