# Modelo congelado do parsing constitucional

## 1. Objetivo

Congelar o modelo arquitetural mínimo necessário para que a futura migration
`004` e a Fase 4B implementem o parsing determinístico da CF/88 e do ADCT sem
reabrir decisões de identidade, proveniência, ordem, status ou atomicidade.

Este documento é normativo para a futura implementação, mas continua sujeito ao
checkpoint humano que encerra a Fase 4A.1. Nenhuma definição aqui altera o banco,
os modelos SQLAlchemy ou a captura documental existente.

## 2. Contexto confirmado

A especificação empírica está em
`docs/40-especificacao-parsing-constitucional.md`. O schema físico atual contém:

- `SourceDocument.raw_bytes` em `BYTEA`, com hash SHA-256 por fonte;
- `LegalAct`, `LegalVersion` e `LegalElement` já criados, mas sem dados jurídicos;
- `LegalVersion.source_document_id` como vínculo direto de proveniência;
- `LegalElement.parent_id`, `ordinal`, `raw_text`, `normalized_text`,
  `is_revoked` e `path`;
- nenhuma entidade que identifique uma execução técnica do parser;
- nenhuma garantia de ordem total dos elementos;
- nenhuma garantia física de que pai e filho pertencem à mesma LegalVersion.

A captura aceita permanece:

| Campo | Valor |
|---|---|
| `document_id` | `27f0ff6b-dd9e-4c4e-ba56-c34984f691e1` |
| URL | `https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm` |
| Bytes | 1.839.482 |
| SHA-256 | `25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d` |

O mesmo payload físico contém a CF/88 e o ADCT. O HTML fecha
`</body></html>` prematuramente e mantém aproximadamente 1,7 MB relevantes após
o fechamento. O backend HTML é, portanto, parte da proveniência técnica.

## 3. Invariantes congelados

1. `raw_bytes` e seu SHA-256 nunca são alterados pelo parsing.
2. Todo parsing parte de um `SourceDocument` íntegro e identificado.
3. UUID permanece a PK de todas as entidades.
4. `path` é somente um localizador jurídico auxiliar e regenerável.
5. CF/88 e ADCT são atos jurídicos distintos derivados da mesma captura física.
6. Uma execução esperada para essa captura produz as duas versões ou nenhuma.
7. Todo elemento identifica inequivocamente a execução que o produziu.
8. Elementos de execuções ou versões diferentes nunca formam uma mesma árvore.
9. `document_order` é a única ordem total canônica persistida.
10. Texto histórico e revogado é preservado, mas não entra silenciosamente como
    texto corrente.
11. Incerteza de status resulta em `UNRESOLVED`.
12. Papel editorial e status temporal são dimensões independentes.
13. Conteúdo não normativo não entra, por padrão, em chunking ou retrieval.
14. Notas e links necessários à auditoria não são descartados.
15. Resultado incompleto nunca é consultável.
16. O parser é determinístico, offline, versionado e coberto por fixtures reais.
17. O banco impede estados impossíveis quando a constraint é simples e local;
    invariantes globais de completude ficam no serviço transacional.

## 4. Decisões arquiteturais congeladas

### 4.1 CF/88 e ADCT

**Problema.** Uma captura contém dois domínios normativos com numeração própria,
inclusive `Art. 1º` em ambos.

**Alternativas consideradas.** Um único LegalAct; um ato composto com subatos;
dois LegalActs ligados ao mesmo SourceDocument.

**Decisão.** Criar os atos canônicos `CF88` e `ADCT`. Cada `ParsingRun` concluído
produz exatamente uma `LegalVersion` de cada ato, ambas referenciando o mesmo
`SourceDocument` do run.

**Justificativa.** Evita colisões, preserva a captura física única e mantém
granularidade adequada para consulta e citação. Um modelo genérico de subatos não
é necessário no MVP1.

**Schema.** `LegalAct.short_name` já é único. `LegalVersion` recebe
`parsing_run_id`; uma unicidade `(parsing_run_id, legal_act_id)` impede duas
versões do mesmo ato no mesmo run.

**Parser.** A segmentação CF/ADCT acontece em memória e as duas árvores são
validadas antes da persistência.

**Retrieval/evidence/citation.** O ato passa a ser inequívoco em labels,
filtros, chunks e citações, embora a URL e o documento de origem sejam comuns.

**Risco.** O banco não consegue garantir sozinho que todo run tenha exatamente
os dois atos esperados. O serviço valida essa cardinalidade antes de concluir.

**Invariante.** Um run `COMPLETED` do adapter constitucional possui uma versão
CF88 e uma versão ADCT, nunca somente uma.

### 4.2 Separação dos três conceitos versionados

**Problema.** Captura física, versão jurídica derivada e execução técnica não são
o mesmo conceito.

**Alternativas consideradas.** Guardar a versão do parser apenas no JSON de
LegalVersion; ligar ParsingRun diretamente aos elementos; introduzir ParsingRun
entre SourceDocument e LegalVersion.

**Decisão.** Adotar:

```text
SourceDocument 1 ── N ParsingRun
ParsingRun      1 ── N LegalVersion (exatamente CF88 + ADCT no adapter MVP1)
LegalAct        1 ── N LegalVersion
LegalVersion    1 ── N LegalElement
LegalElement    0..1 ── N LegalElement (árvore)
```

`LegalVersion.source_document_id` é mantido para preservar a cadeia direta já
estabelecida. Uma FK composta garante que ele é igual ao documento do
`ParsingRun`. `LegalElement` não recebe FK redundante para ParsingRun: o caminho
`element → legal_version → parsing_run` é único e suficiente.

**Impacto futuro.** Evidence e Citation continuam alcançando diretamente
LegalVersion e SourceDocument, e passam a poder auditar também nome e versão do
parser.

**Invariantes.** Uma LegalVersion pertence a um run e ao mesmo SourceDocument
desse run; um LegalElement pertence a uma única LegalVersion e, transitivamente,
a um único run.

### 4.3 Ativação para consulta

**Problema.** Runs v1 e v2 podem coexistir, mas retrieval não pode misturá-los.

**Decisão.** Preservar `LegalVersion.is_active_for_query`, alterar seu default
para `false` e permitir no máximo uma versão ativa por LegalAct, por índice único
parcial. A troca de ativa ocorre atomicamente somente no commit de um run
validado.

**Risco.** A condição “run deve estar COMPLETED” cruza tabelas e não cabe em
CHECK PostgreSQL. Ela permanece invariante do serviço e recebe teste de banco/
integração.

## 5. Modelo conceitual resultante

```text
Source
└── SourceDocument (bytes oficiais imutáveis)
    └── ParsingRun (execução técnica versionada)
        ├── LegalVersion ── LegalAct(CF88)
        │   └── LegalElement tree
        └── LegalVersion ── LegalAct(ADCT)
            └── LegalElement tree

LegalElement
└── future Chunk
    └── future EvidenceItem
        └── future Citation
```

`LegalVersion` representa a versão documental estruturada de um ato naquela
captura. `ParsingRun` registra como ela foi produzida. Parser v2 sobre os mesmos
bytes é novo run e novo resultado estrutural, não uma nova captura nem uma
afirmação automática de nova vigência jurídica.

## 6. Cardinalidades e chaves auxiliares

| Relação | Cardinalidade | Proteção |
|---|---|---|
| Source → SourceDocument | 1:N | FK existente |
| SourceDocument → ParsingRun | 1:N | FK `RESTRICT` |
| ParsingRun → LegalVersion | 1:N | FK + unique por ato |
| LegalAct → LegalVersion | 1:N | FK existente |
| LegalVersion → LegalElement | 1:N | FK existente |
| LegalElement pai → filhos | 1:N | FK composta na mesma versão |

Chaves naturais/auxiliares:

- run técnico: `(source_document_id, parser_name, parser_version)`;
- versão no run: `(parsing_run_id, legal_act_id)`;
- posição: `(legal_version_id, document_order)`;
- local jurídico: ato + ancestralidade + tipo + `number_label`, nunca `path`
  isoladamente.

## 7. Taxonomia definitiva de LegalElement

Taxonomia mínima do MVP1:

| Valor | Semântica |
|---|---|
| `DOCUMENT_ROOT` | raiz única de CF88 ou ADCT |
| `PREAMBLE` | preâmbulo da CF |
| `TITLE` | título constitucional |
| `CHAPTER` | capítulo |
| `SECTION` | seção |
| `SUBSECTION` | subseção |
| `ARTICLE` | contêiner do artigo e de seu rótulo |
| `CAPUT` | texto principal do artigo |
| `PARAGRAPH` | parágrafo numerado ou único |
| `INCISO` | inciso identificado por numeral romano |
| `ALINEA` | alínea identificada por letra |
| `ITEM` | item subordinado, normalmente numérico |
| `NOTE` | anotação não normativa ligada ao dispositivo ou à raiz |

Não são criados tipos genéricos para partes, livros, anexos ou outras normas.

### 7.1 Regras estruturais

- existe exatamente um `DOCUMENT_ROOT` por LegalVersion;
- `PREAMBLE` existe somente na CF;
- divisões ausentes no ADCT não são inventadas;
- todo `ARTICLE` possui exatamente um `CAPUT`, inclusive artigo sem subdivisões;
- `ARTICLE.raw_text` preserva somente o rótulo factual do artigo e
  `ARTICLE.normalized_text` sua forma mecanicamente normalizada; ARTICLE não
  duplica o texto normativo integral;
- `CAPUT.raw_text` preserva o texto normativo após o rótulo e
  `CAPUT.normalized_text` sua normalização mecânica;
- artigo sem subdivisões é `ARTICLE → CAPUT`;
- artigo com incisos possui `CAPUT` e `INCISO` como filhos de `ARTICLE`;
- parágrafos são filhos do artigo e podem possuir INCISO;
- `Parágrafo único` é `PARAGRAPH`, com `number_label="único"`;
- `116-A` é preservado em `number_label`, com forma canônica apenas derivada;
- numeral romano é preservado em `number_label` de INCISO;
- alínea é ALINEA; subdivisão numérica subordinada é ITEM;
- INCISO que subdivide o caput é filho de ARTICLE; INCISO que subdivide um
  parágrafo é filho de PARAGRAPH;
- NOTE é filho do elemento afetado ou da raiz quando a nota é documental geral.

### 7.2 CAPUT explícito

**Decisão.** CAPUT é sempre LegalElement próprio.

Isso elimina tratamento especial para artigo simples, permite que caput tenha
status, notas e links próprios e fornece granularidade estável para chunking e
citação. O ARTICLE funciona como nó estrutural/localizador e nunca duplica o
texto integral de CAPUT e filhos.

CAPUT é uma estrutura jurídica sintética do parser: não pressupõe tag HTML
específica. ARTICLE e CAPUT apontam em `source_locator` para o bloco factual que
contém rótulo e texto; `CAPUT.parser_metadata` registra
`{"synthetic_structure": true}`. Localização factual permanece separada da
interpretação técnica.

### 7.3 Impacto futuro

Chunks normativos serão construídos a partir de CAPUT, PARAGRAPH, INCISO, ALINEA
e ITEM correntes. ARTICLE e divisões fornecem contexto e labels. NOTE não entra
automaticamente no corpus normativo, mas permanece disponível para validação e
exibição de proveniência.

## 8. `document_order` e `ordinal`

### 8.1 `document_order`

Definição congelada:

- tipo: `BIGINT`;
- `NOT NULL`;
- começa em `1` para cada LegalVersion;
- representa a posição global do LegalElement na projeção documental daquela
  versão;
- inclui raiz, divisões, dispositivos históricos, vigentes e notas persistidas;
- é único por `(legal_version_id, document_order)`;
- a sequência produzida pelo parser deve ser contígua, sem gaps;
- a ausência de gaps é validada pelo serviço, pois UNIQUE não a garante;
- em reparse, uma nova LegalVersion recebe nova sequência determinística;
- igualdade semântica de dois parses inclui igualdade da sequência e dos dados
  dos elementos, não igualdade dos UUIDs.

`document_order` não representa número jurídico. Inserções futuras no documento
podem alterar ordens posteriores em outra LegalVersion, sem mudar a identidade
primária das versões antigas.

### 8.2 `ordinal`

**Decisão.** Remover `ordinal` na migration 004.

Defini-lo como posição entre irmãos duplicaria informação derivável pela ordem
global; usá-lo como número jurídico duplicaria `number_label`. Manter os dois
campos criaria duas ordens potencialmente contraditórias. A ordem entre irmãos é
obtida por `document_order` dentro do mesmo `parent_id`.

### 8.3 Impacto futuro

Retrieval e Citation Validator sempre ordenam elementos por `document_order`,
nunca por UUID, path ou retorno incidental. `number_label` serve para rótulos de
citação, não para ordenação total.

## 9. `text_status`

Taxonomia final:

| Valor | Semântica |
|---|---|
| `CURRENT` | o documento apresenta esta ocorrência como redação corrente |
| `HISTORICAL` | redação normativa anterior preservada no documento |
| `REVOKED` | dispositivo explicitamente apresentado como revogado |
| `UNRESOLVED` | sinais insuficientes ou contraditórios |
| `NOT_APPLICABLE` | elemento cujo papel não é normativo |

Regras:

- default físico e lógico: `UNRESOLVED`;
- `strike` isolado nunca determina `REVOKED`;
- nota explícita de revogação associada permite `REVOKED`;
- risco mais redação substituta contextual permite `HISTORICAL`;
- dúvida permanece `UNRESOLVED` e impede uso normativo em consulta;
- `content_role=NORMATIVE` exige um dos quatro status jurídicos;
- papel não normativo exige `NOT_APPLICABLE`.

**Decisão sobre `is_revoked`.** Remover na migration 004. O banco ainda não
possui LegalElements, portanto não há dado a migrar. A propriedade pode ser
derivada por `text_status == REVOKED`; manter ambos permitiria contradição.

**Impacto futuro.** Chunking, FTS e embeddings incluem somente `CURRENT +
NORMATIVE` por default. Histórico ou revogado só entra em uma busca histórica
explicitamente solicitada. `UNRESOLVED` nunca fundamenta resposta como texto
vigente.

## 10. `content_role`

Taxonomia final mínima:

| Valor | Semântica |
|---|---|
| `NORMATIVE` | estrutura ou texto constitucional |
| `AMENDMENT_NOTE` | inclusão, nova redação ou revogação por EC |
| `REFERENCE_NOTE` | vide norma, ADI/ADIN, regulamento ou remissão externa |
| `EDITORIAL_NOTE` | vigência, produção de efeitos, aviso do DOU ou nota geral |

Essas quatro categorias cobrem os padrões relevantes da captura. Navegação,
scripts, cabeçalho técnico e infraestrutura não precisam virar LegalElement;
são contabilizados como blocos ignorados/classificados nos metadados do run.
Blocos documentais relevantes, como aviso do DOU, podem ser NOTE com
`EDITORIAL_NOTE`.

`text_status` e `content_role` são independentes na semântica, com compatibilidade
controlada: `HISTORICAL + NORMATIVE` é válido; `NOT_APPLICABLE +
AMENDMENT_NOTE` é válido; `CURRENT + REFERENCE_NOTE` é inválido.

Impacto futuro:

- chunking/FTS/embeddings: somente NORMATIVE/CURRENT por default;
- retrieval: filtros explícitos de ato, versão, papel e status;
- EvidenceBuilder: não cria evidência normativa apenas de NOTE;
- notas podem acompanhar a evidência como contexto/proveniência;
- Citation Validator verifica que o elemento fundamentador é normativo e que
  seu status é compatível com o tipo de resposta.

## 11. ParsingRun

`ParsingRun` representa um **processamento lógico** de uma captura por uma versão
específica do parser, não cada tentativa física. A chave natural abaixo materializa
essa semântica. Um retry de FAILED reutiliza a mesma linha; não existe
`ParsingAttempt` no MVP1. Logs fornecem observabilidade por tentativa, enquanto o
metadata do run conserva somente diagnóstico consolidado e contador de retries.

### 11.1 Campos mínimos

| Campo | Tipo/constraint | Semântica |
|---|---|---|
| `id` | UUID PK | identidade da execução |
| `source_document_id` | UUID FK, NOT NULL | captura processada |
| `parser_name` | VARCHAR(100), NOT NULL | adapter/algoritmo, ex. `planalto_constitution` |
| `parser_version` | VARCHAR(50), NOT NULL | versão semântica das regras |
| `status` | VARCHAR(20), NOT NULL | `RUNNING`, `COMPLETED`, `FAILED` |
| `started_at` | TIMESTAMPTZ, NOT NULL | início persistido |
| `finished_at` | TIMESTAMPTZ, NULL | término, com sucesso ou falha |
| `metadata` | JSONB, NULL | encoding, versão do runtime/backend, contagens, validações ou erro |

`finished_at` foi escolhido no lugar de `completed_at`, pois também representa o
fim de um run `FAILED`. CHECK exige `NULL` para RUNNING e não nulo para estados
terminais.

Unicidades:

- `UNIQUE(source_document_id, parser_name, parser_version)`;
- `UNIQUE(id, source_document_id)`, necessária para a FK composta de
  LegalVersion.

### 11.2 Cardinalidade e ausência de FK direta no elemento

ParsingRun pertence a um SourceDocument e produz duas LegalVersions. LegalElement
pertence à LegalVersion. Não há `legal_elements.parsing_run_id`, pois seria dado
duplicado sujeito a divergência. A consulta inequívoca é:

```text
LegalElement.legal_version_id
  → LegalVersion.parsing_run_id
  → ParsingRun.id
```

## 12. Reparse e idempotência

| Cenário | Resultado |
|---|---|
| parser v1 + documento X, primeira vez | novo run e duas versões |
| parser v1 + documento X novamente, run COMPLETED | `ALREADY_PARSED`; reutiliza resultado |
| parser v1 + documento X, run RUNNING | `PARSING_IN_PROGRESS`; não inicia concorrente |
| parser v1 + documento X, run FAILED | retry explícito reutiliza o mesmo run após limpar somente resultados inexistentes/parciais transacionais |
| parser v2 + documento X | novo run e novas versões; v1 permanece auditável |

UUIDs dos elementos são identidades persistidas do resultado. Um `ALREADY_PARSED`
retorna os mesmos IDs. Parser v2 cria novos IDs, pois é novo resultado técnico.

Resultados antigos permanecem no banco e inativos, não são sobrescritos. Não há
`force` destrutivo no MVP1. Um run FAILED não pode possuir LegalVersions
confirmadas, devido à transação; seu metadata preserva diagnóstico e número de
tentativas de retry, sem criar uma tabela de tentativas.

Concorrência é protegida pela unique natural do run. O serviço trata a colisão
como estado já existente, nunca como motivo para duplicar versões.

Transições permitidas, aplicadas pelo serviço com atualização condicional do
status corrente:

```text
novo → RUNNING
RUNNING → COMPLETED
RUNNING → FAILED
FAILED → RUNNING
```

São proibidas `COMPLETED → RUNNING`, `COMPLETED → FAILED` e
`FAILED → COMPLETED`. CHECKs validam apenas a combinação entre status e
timestamps; não se usam triggers para história temporal. No retry
`FAILED → RUNNING`, `started_at` recebe o início da nova tentativa,
`finished_at` volta a NULL e o metadata incrementa `retry_count`.

## 13. Unidade transacional

Estratégia mínima em três transações deliberadas:

1. **TX1:** inserir o run novo, ou transicionar FAILED para RUNNING, definir
   `started_at=now()` e `finished_at=NULL`; COMMIT;
2. verificar SHA e fazer decoding/parsing/validação em memória, sem criar versão
   ou elemento;
3. **TX2:** abrir uma única transação de materialização;
4. criar/buscar os LegalActs canônicos;
5. criar as duas LegalVersions inicialmente inativas;
6. inserir todas as árvores e notas;
7. executar invariantes e contagens no resultado persistido;
8. desativar versões anteriores dos dois atos;
9. ativar conjuntamente as duas novas versões;
10. marcar o run `COMPLETED`, preencher `finished_at` e COMMIT;
11. em qualquer falha antes do commit de TX2, executar ROLLBACK integral;
12. **TX3:** transicionar RUNNING para FAILED, preencher `finished_at` e o
    diagnóstico técnico; COMMIT.

A linha RUNNING/FAILED pode ser observada, mas nenhuma versão parcial fica
visível. O resultado se torna consultável somente no commit que contém árvores
completas, ativação e status COMPLETED.

Se a criação dos LegalActs for necessária, ela ocorre na transação de
materialização. Uma corrida usa a unicidade de `short_name` e retry transacional
controlado.

## 14. Integridade pai-filho

Proteção física congelada:

1. adicionar `UNIQUE(id, legal_version_id)` em `legal_elements`;
2. substituir a FK simples de `parent_id` por:

```text
FOREIGN KEY (parent_id, legal_version_id)
REFERENCES legal_elements (id, legal_version_id)
ON DELETE CASCADE
```

Isso garante `child.legal_version_id == parent.legal_version_id`. Como a versão
possui exatamente um `parsing_run_id`, também impede árvore entre runs distintos
sem duplicar essa FK no elemento.

Permanecem na aplicação:

- exatamente uma raiz;
- ausência de ciclos além do self-parent já protegido;
- compatibilidade de tipos pai-filho;
- sequência contígua;
- duas versões por run constitucional concluído.

Uma constraint recursiva contra ciclos completos exigiria trigger/CTE e não é
justificada no MVP1.

## 15. Proveniência mínima

Cada LegalElement recebe:

- `source_locator JSONB NOT NULL`;
- `parser_metadata JSONB NULL`.

Contrato mínimo de `source_locator`:

```json
{
  "block_index": 3423,
  "source_line": 29586,
  "tag": "p",
  "anchors": ["sadctart1", "adctart1", "art1adct", "dtart1"]
}
```

- `block_index` é a posição zero-based na sequência de blocos DOM linearizada
  pelo parser versionado e é o localizador principal;
- `source_line` é auxiliar, útil para auditoria, mas depende do backend;
- `tag` registra o nó original;
- `anchors` preserva todos os nomes/IDs relevantes em ordem, sem escolhê-los
  como identidade.

DOM path completo e byte offsets não são obrigatórios: o DOM foi reparado e tais
offsets não são confiáveis sem um scanner específico. O localizador é
reproduzível somente junto com SourceDocument, parser/runtime versionados e
regra de linearização.

`parser_metadata` guarda sinais locais necessários à auditoria, como intervalos
marcados por `strike`, forma canônica do rótulo, avisos e links ordenados. Não
deve copiar todo o DOM nem se tornar depósito de regra de negócio não modelada.

O localizador não substitui UUID, path ou document_order.

## 16. Notas e referências

### 16.1 Notas

**Decisão.** Notas relevantes são LegalElements `NOTE`, filhos do dispositivo
afetado ou da raiz, diferenciadas por `content_role`. Essa é a solução mínima:
preserva ordem, texto, proveniência e relação hierárquica sem criar tabela ou
grafo legislativo adicional.

Uma nota tem `text_status=NOT_APPLICABLE`. Seu `raw_text` preserva a projeção
textual original; `normalized_text` aplica somente normalização mecânica. Notas
não são incorporadas ao `normalized_text` normativo.

### 16.2 Hyperlinks

Links são preservados no `parser_metadata` do elemento que contém a âncora, como
lista ordenada mínima:

```json
{
  "links": [
    {
      "anchor_text": "Emenda Constitucional nº ...",
      "href_original": "../emendas/...",
      "resolved_url": "https://www.planalto.gov.br/..."
    }
  ]
}
```

Não há entidade de link nem `LegalRelationship` no MVP1. O documento de destino
não é ingerido ou validado. Preservar o href original evita que resolução futura
apague a proveniência editorial.

## 17. Backend HTML

**Decisão.** Usar `BeautifulSoup4` com backend explícito `html.parser` no parser
inicial.

Justificativa empírica:

- preservou os 4.338 parágrafos e a cauda após o fechamento prematuro;
- preservou o fim do ADCT e os 773 `strike` observados;
- forneceu `sourceline`;
- `lxml.html` direto reteve somente 476 parágrafos e perdeu conteúdo normativo.

Versionamento:

- registrar `sys.version`, versão de BeautifulSoup, backend e `parser_version`
  no metadata do run;
- manter Python e dependências no `uv.lock`/imagem Docker;
- qualquer atualização que altere o DOM reparado exige parser_version nova ou
  prova de equivalência pelas fixtures.

Invariantes de cobertura, sem transformar contagens atuais em direito material:

1. reconhecer os delimitadores sem usar a ocorrência do menu;
2. alcançar começo e fim dos dois domínios;
3. observar artigo 1º e o marcador final esperado em cada domínio conforme o
   perfil da captura analisada;
4. classificar ou contabilizar todos os blocos entre os delimitadores;
5. garantir presença de conteúdo antes e depois do `</html>` prematuro;
6. comparar fingerprint estrutural com tolerâncias/versionamento explícitos;
7. falhar fechado diante de queda abrupta de cobertura, não aceitar DOM parcial.

Os números empíricos são sentinelas de regressão para esta fixture/captura, não
regras universais sobre quantos artigos a Constituição deve possuir.

## 18. Estratégia de golden fixtures

Cada caso possui dois artefatos futuros:

1. HTML mínimo extraído fielmente, com identificação do SourceDocument, intervalo
   de origem e SHA-256 da fixture;
2. estrutura esperada declarativa, contendo tipos, pais lógicos, labels, ordem,
   status, roles, texto e referências relevantes.

As expectativas devem omitir atributos cosméticos irrelevantes, mas o HTML não
deve ser “limpo”. Classes, tags ou whitespace só entram na asserção quando forem
sinais necessários ao caso.

| Fixture | Deve validar |
|---|---|
| início/preâmbulo/art. 1º | ignorar menu homônimo; raiz, preâmbulo, título, artigo, CAPUT e incisos |
| hierarquia profunda/art. 12 | ARTICLE → CAPUT + INCISO → ALINEA e PARAGRAPH → INCISO; labels e ordem |
| redações históricas/art. 6º | ocorrências repetidas, HISTORICAL versus CURRENT, nenhuma perda de texto |
| revogação explícita | REVOKED somente com nota associada; NOTE/AMENDMENT_NOTE separado |
| notas e referências/art. 5º | múltiplas notas, roles e links na ordem original |
| fim da CF/transição ADCT | artigo 250, blocos editoriais, separador real e duas raízes/versões |
| ADCT complexo/art. 60 | subárvores históricas completas, incisos e alíneas ligados à ocorrência correta |
| artigo com sufixo | `116-A` preservado e canonicamente reconhecido |
| dispositivos recentes | classes `MsoNormal`/`dou-paragraph` não determinam semântica |
| fechamento prematuro | conteúdo relevante antes e depois do fechamento permanece acessível |

Além delas, um teste de captura integral opt-in/read-only valida cobertura contra
o SourceDocument persistido, sem nova ingestão.

## 19. Especificação exata da futura migration 004

Nome sugerido: `004_frozen_parsing_model`.

Esta seção especifica a migration; nenhum arquivo foi criado.
A revisão física final, incluindo nomes de todas as constraints, nullability e
ordem operacional sem ambiguidades, está em
`docs/42-revisao-consistencia-pre-migration.md` e prevalece em detalhes de DDL.

### 19.1 Nova tabela `parsing_runs`

Colunas:

- `id UUID PRIMARY KEY`;
- `source_document_id UUID NOT NULL`;
- `parser_name VARCHAR(100) NOT NULL`;
- `parser_version VARCHAR(50) NOT NULL`;
- `status VARCHAR(20) NOT NULL`, default de servidor `RUNNING`;
- `started_at TIMESTAMPTZ NOT NULL DEFAULT now()`;
- `finished_at TIMESTAMPTZ NULL`;
- `metadata JSONB NULL`.

Constraints:

- FK `source_document_id → source_documents.id ON DELETE RESTRICT`;
- `UNIQUE(source_document_id, parser_name, parser_version)`;
- `UNIQUE(id, source_document_id)` para referência composta;
- CHECK `status IN ('RUNNING', 'COMPLETED', 'FAILED')`;
- CHECK de terminalidade:
  `(status = 'RUNNING' AND finished_at IS NULL) OR
   (status IN ('COMPLETED', 'FAILED') AND finished_at IS NOT NULL)`.

Índices adicionais: nenhum. A unique natural atende busca idempotente por
documento/parser.

### 19.2 Alterações em `legal_versions`

Adicionar:

- `parsing_run_id UUID NOT NULL`;
- `UNIQUE(parsing_run_id, legal_act_id)`;
- FK composta
  `(parsing_run_id, source_document_id) →
   parsing_runs(id, source_document_id) ON DELETE RESTRICT`. Esta é a única FK
  para o run; ela garante simultaneamente sua existência e a igualdade do
  SourceDocument, sem FK simples redundante;
- índice único parcial em `legal_act_id WHERE is_active_for_query`, com nome
  explícito, garantindo no máximo uma versão ativa por ato.

Alterar:

- default de servidor de `is_active_for_query` de `true` para `false`.

Manter:

- `source_document_id` e sua FK existente;
- `version_label`, `parsed_at` e `metadata`.

Como `legal_versions` está vazia no checkpoint, `parsing_run_id` pode ser criado
diretamente como NOT NULL, sem sentinel ou backfill.

### 19.3 Alterações em `legal_elements`

Adicionar:

- `document_order BIGINT NOT NULL`;
- `text_status VARCHAR(20) NOT NULL DEFAULT 'UNRESOLVED'`;
- `content_role VARCHAR(30) NOT NULL DEFAULT 'NORMATIVE'`;
- `source_locator JSONB NOT NULL`;
- `parser_metadata JSONB NULL`.

Remover:

- `ordinal`;
- `is_revoked`.

Constraints:

- CHECK `element_type IN ('DOCUMENT_ROOT', 'PREAMBLE', 'TITLE', 'CHAPTER',
  'SECTION', 'SUBSECTION', 'ARTICLE', 'CAPUT', 'PARAGRAPH', 'INCISO', 'ALINEA',
  'ITEM', 'NOTE')`;
- CHECK `text_status IN ('CURRENT', 'HISTORICAL', 'REVOKED', 'UNRESOLVED',
  'NOT_APPLICABLE')`;
- CHECK `content_role IN ('NORMATIVE', 'AMENDMENT_NOTE', 'REFERENCE_NOTE',
  'EDITORIAL_NOTE')`;
- CHECK de compatibilidade:
  `(content_role = 'NORMATIVE' AND text_status <> 'NOT_APPLICABLE') OR
   (content_role <> 'NORMATIVE' AND text_status = 'NOT_APPLICABLE')`;
- CHECK `document_order >= 1`;
- `UNIQUE(legal_version_id, document_order)`;
- `UNIQUE(id, legal_version_id)`;
- substituir FK simples de `parent_id` pela FK composta
  `(parent_id, legal_version_id) → legal_elements(id, legal_version_id)
  ON DELETE CASCADE`;
- manter CHECK `parent_id <> id`.

Índices:

- a unique de `(legal_version_id, document_order)` cobre a travessia ordenada;
- manter índices existentes de `legal_version_id`, `parent_id` e `path`, mesmo
  que alguns possam ser redundantes, deixando otimização para medição posterior;
- não criar GIN em JSONB nesta fase.

### 19.4 Ordem operacional do upgrade

1. criar `parsing_runs` e constraints;
2. adicionar `legal_versions.parsing_run_id` e suas constraints;
3. alterar default de ativação e criar índice parcial;
4. adicionar novas colunas de `legal_elements`;
5. remover FK simples pai-filho;
6. criar unique composta e FK pai-filho composta;
7. criar CHECKs e unique de ordem;
8. remover `ordinal` e `is_revoked`.

### 19.5 Downgrade seguro

O downgrade deve abortar explicitamente se existir qualquer `parsing_run`,
`legal_version` ou `legal_element`, pois remover status, proveniência e vínculo do
run destruiria informação sem conversão fiel.

Somente com essas tabelas vazias, reverter em ordem:

1. remover constraints/índices novos;
2. restaurar FK simples de `parent_id`;
3. recriar `ordinal INTEGER NULL`;
4. recriar `is_revoked BOOLEAN NOT NULL DEFAULT false`;
5. remover colunas novas de LegalElement;
6. restaurar default `true` de `is_active_for_query` para equivalência com 003;
7. remover `parsing_run_id` de LegalVersion;
8. remover `parsing_runs`.

Não existe conversão segura de `text_status` para `is_revoked` que preserve
CURRENT/HISTORICAL/UNRESOLVED. O guard de ausência de dados é, portanto,
obrigatório.

### 19.6 Compatibilidade com o banco atual

O checkpoint possui `legal_versions = 0` e, por consequência, nenhum
LegalElement. A migration proposta não toca `sources`, `source_documents` ou
`raw_bytes`, não requer reingestão e pode adicionar os campos NOT NULL sem
backfill jurídico.

## 20. Riscos residuais

- o DOM reparado pode mudar com runtime/dependência;
- contagens empíricas não substituem validação semântica estrutural;
- `source_locator` depende da versão da linearização;
- status editorial ainda depende de regras conservadoras e pode ficar
  UNRESOLVED;
- a cardinalidade exata CF+ADCT por run é garantida pelo serviço, não por CHECK;
- ativação somente após COMPLETED é uma invariante transacional entre tabelas;
- metadata JSONB preserva flexibilidade, mas exige contrato validado na aplicação;
- o índice de uma única versão ativa por ato deve ser coordenado na troca
  atômica;
- notes como LegalElement simplificam o MVP, mas poderão demandar entidade
  própria se consultas editoriais se tornarem complexas;
- retry de run FAILED preserva somente o diagnóstico consolidado no metadata,
  não um histórico relacional de tentativas.

## 21. Decisões explicitamente adiadas

- implementação e API interna do parser;
- migration 004 e modelos SQLAlchemy;
- conteúdo exato e extração das fixtures;
- thresholds finais de fingerprint/cobertura da captura integral;
- estratégia de chunking;
- inclusão opt-in de texto histórico em busca;
- FTS, embeddings, retrieval e reranking;
- EvidenceBuilder, EvidenceValidator e CitationValidator;
- representação genérica de relações legislativas;
- ingestão e modelagem das Emendas, leis, ADIs e regulamentos referenciados;
- canonicalização futura de conteúdo derivado;
- LLM/Ollama;
- política além do MVP para múltiplos corpus e outros tipos de ato.

## 22. Critérios de aceite da futura Fase 4B

1. revisão humana aprova este congelamento e autoriza explicitamente migration
   004 e parser;
2. migration 004 corresponde exatamente à seção 19 e possui upgrade/downgrade
   seguros testados em banco descartável;
3. modelos e schema físico permanecem alinhados;
4. parser verifica SHA-256 e usa decoding estrito sem tocar `raw_bytes`;
5. BeautifulSoup + `html.parser` e versões são registrados no run;
6. todas as golden fixtures possuem HTML fiel e resultado esperado declarativo;
7. teste de regressão prova cobertura antes/depois do fechamento prematuro;
8. uma execução materializa CF e ADCT atomicamente;
9. CAPUT explícito e taxonomia congelada são respeitados;
10. `document_order` é total, contíguo, único e determinístico;
11. `ordinal` e `is_revoked` não permanecem como fontes concorrentes;
12. status e roles obedecem aos CHECKs e à política conservadora;
13. notas e links são preservados conforme seção 16;
14. pai e filho da mesma árvore pertencem fisicamente à mesma LegalVersion;
15. run v1 repetido é idempotente; v2 não mistura nem apaga v1;
16. somente versões completas de run COMPLETED são consultáveis;
17. falha em qualquer dispositivo não deixa versão ou elementos parciais;
18. nenhuma etapa de chunking, retrieval, evidence, citation ou LLM é incluída;
19. suíte unitária, testes de banco, Ruff e validação Docker passam;
20. captura real permanece byte a byte intacta.

## 23. Registro arquitetural

Esta especificação comporta todas as decisões necessárias ao checkpoint 4A.1;
por isso nenhum ADR separado é criado agora.

ADR futuro recomendado: **Separação entre captura documental, versão jurídica,
execução de parsing e status editorial do texto constitucional**. Ele deve ser
criado junto da autorização da migration 004, quando as decisões desta
especificação forem formalmente aceitas, para registrar consequências de longo
prazo sem duplicar o conteúdo investigativo.
