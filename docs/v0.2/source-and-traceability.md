# Fonte e rastreabilidade do corpus v0.2

## Cadeia principal

```text
Answer
  -> Evidence ID
  -> SearchUnit
  -> Provision
  -> ActVersion
  -> SourceSnapshot
  -> Source
```

Uma `SearchUnit` pode ser derivada de vários Provisions; a tabela associativa
`search_unit_provisions` registra essa composição. A unidade preserva uma
âncora quando existe, enquanto cada Provision mantém texto citável, posição e
localizador próprios.

## Aquisição, materialização e reprojeção

As fronteiras são deliberadamente separadas:

```text
ACQUISITION
fonte remota -> SourceSnapshot imutável

MATERIALIZATION
SourceSnapshot -> parser/projeção -> ActVersion -> Provision -> SearchUnit

REPROJECTION
SourceSnapshot existente -> novo parser/projeção -> novo corpus materializado
```

A aquisição HTTP é responsável somente por obter uma captura nova. A
materialização consome uma `SourceCapture` independente de HTTP e SQLAlchemy.
Na reprojeção explícita, o adapter lê os `raw_bytes` exatos do snapshot
persistido, recalcula SHA-256 antes do parsing e falha se a captura não existir
ou se houver divergência de integridade. Não há fallback para aquisição remota.

O mesmo snapshot pode originar versões de CF/88 e ADCT para diferentes versões
do parser. `ActVersion.version_hash` distingue ato, SHA do snapshot e versão do
parser; `Source`, `SourceSnapshot` e `LegalAct` continuam sendo reutilizados por
identidade natural. A versão anterior permanece preservada e a nova só se torna
ativa no commit atômico de suas Provisions e SearchUnits.

## Redações históricas incorporadas à página consolidada

O HTML oficial pode apresentar, lado a lado, ocorrências históricas,
revogadas, editoriais e a ocorrência corrente de uma mesma identidade
normativa. O parser preserva essa distinção documental; o adapter do corpus
ativo seleciona deterministicamente a única ocorrência `CURRENT`. Na ausência
de uma corrente, uma única `UNRESOLVED` pode ser preservada de forma
conservadora. Múltiplas candidatas correntes ou unresolved bloqueiam a
materialização antes do banco, com os dois locators no diagnóstico.

Para fatos documentais que não pertencem à árvore normativa, a cadeia é:

```text
Answer
  -> Evidence ID
  -> SearchUnit(DOCUMENT_METADATA)
  -> ActVersion
  -> SourceSnapshot
  -> Source
```

Assim, a data de promulgação é indexável somente quando extraída de um bloco da
captura oficial. O `source_locator` registra esse bloco. A data não é uma base
manual de conhecimento nem um valor presumido pelo sistema.

## Integridade

- `raw_bytes` e SHA-256 identificam a captura imutável;
- `ActVersion.version_hash` deriva do ato, snapshot e versão do parser;
- `Provision.stable_key` deriva do caminho normativo, sem UUID;
- `SearchUnit.content_hash` deriva de tipo, versão, âncora e texto de busca;
- `search_unit_embeddings` identifica provider, modelo, dimensão e hash do
  conteúdo, permitindo refresh somente da projeção obsoleta;
- `document_order` torna árvores e projeções reproduzíveis.

## Retry e fronteiras transacionais

`Source.official_url`, `SourceSnapshot.sha256`, `LegalAct.code` e
`ActVersion(legal_act_id, version_hash)` são identidades naturais reutilizadas
em retries. A materialização de Snapshot, ActVersions, Provisions e SearchUnits
ocorre em uma transação serializada por advisory lock transacional do
PostgreSQL. Assim, dois bootstraps concorrentes não tentam criar o mesmo
aggregate; o segundo aguarda e reavalia o estado commitado.

Uma falha nessa materialização reverte todo o aggregate. Depois do commit, o
corpus pode sobreviver legitimamente a uma falha posterior de embeddings: ele é
reutilizável, mas o bootstrap permanece incompleto até o índice terminar. As
ActVersions somente ficam visíveis como ativas junto com suas Provisions e
SearchUnits commitadas.

O localizador atual identifica deterministicamente o bloco e, nos elementos
estruturais, preserva os dados disponíveis do parser. Ele não pretende modelar
ou reserializar integralmente o DOM.

Os IDs `E1`, `E2` etc. existem somente durante uma requisição. A referência
estável exibida e validada é derivada do ato e caminho normativo; UUIDs não são
apresentados ao modelo como identidade jurídica.
