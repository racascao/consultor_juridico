# Fundação e corpus v0.2

## Escopo

A Fase 0 materializa um corpus auditável da Lei nº 9.784/1999 sem implementar
retrieval, FTS, embeddings ou LLM. O PostgreSQL `consultor_juridico_v02`, na
porta 5434, é isolado do banco legado.

## Schema

O baseline `001_v02_foundation_corpus` cria somente:

- `sources`;
- `source_snapshots`;
- `legal_acts`;
- `act_versions`;
- `provisions`;
- `search_units`;
- `search_unit_provisions`;
- `alembic_version`.

As migrations do MVP1 não compõem o histórico ativo da branch v0.2; continuam
preservadas pela tag imutável `v0.1.0`. Não há upgrade in-place do banco
legado.

## Captura e imutabilidade

`SourceSnapshot.raw_bytes` contém exatamente os bytes HTTP. Seu identificador
natural é `(source_id, sha256(raw_bytes))`; ETag e Last-Modified são somente
metadados para conditional GET. Uma resposta `304` reutiliza a captura sem
alterá-la. Uma resposta `200` com SHA conhecido também reutiliza a linha.

O banco verifica formato do SHA, comprimento de bytes e bloqueia `UPDATE` e
`DELETE` de snapshots por um trigger dedicado. Não existe hash canônico ou
semântico paralelo.

## Parser e cobertura

O contrato da fonte declara `windows-1252`; o decoding é estrito. O parser
`planalto-lei-structural/1` recebe bytes e encoding, não conhece HTTP, SQLAlchemy
ou PostgreSQL, e opera somente até o primeiro `</html>`. A cauda posterior é
preservada nos bytes, mas não integra a árvore.

A taxonomia fechada é `DOCUMENT_ROOT`, `CHAPTER`, `ARTICLE`, `CAPUT`,
`PARAGRAPH` e `INCISO`. `ARTICLE` é contêiner sem `citation_text`; `CAPUT`
contém o texto oficial principal. O status inicial é `IN_FORCE`; somente uma
marcação literal e inequívoca `(VETADO)` produz `VETOED`.

Cada parágrafo do DOM recebe exatamente um registro de cobertura: consumido
por uma Provision ou ignorado por uma razão fechada. Texto potencialmente
jurídico não reconhecido gera `UnsupportedSourceStructure`; não existe ignore
genérico. Na captura investigada, a cobertura é:

```text
total DOM paragraphs:          260
non-empty paragraphs:          251
consumed paragraphs:           246
explicitly ignored paragraphs: 14
unaccounted legal paragraphs:  0
```

O texto oficial sofre apenas conversão de entidades HTML e normalização de
whitespace de apresentação. Não há lowercase, stemming, remoção de acentos,
síntese ou paráfrase. `Provision.content_hash` é SHA-256 do `citation_text`
UTF-8, usando string vazia para elementos estruturais sem texto.

## Identidade e versionamento

As `stable_key`s são hierárquicas, determinísticas e independentes de UUID. O
caminho do inciso inclui seu ancestral, distinguindo inciso de CAPUT e de
parágrafo. `document_order` reproduz a ordem linear da fonte.

O `version_hash` é SHA-256 de JSON canônico contendo a chave natural do ato,
SHA do snapshot, parser name/version e projection name/version. Não existe
flag de versão ativa, atual ou preferida.

## Projeção e materialização

A projeção `provision-text/1` cria uma SearchUnit por Provision textual:

```text
search_text = citation_text
unit_key = stable_key
SearchUnitProvision.position = 0
```

Não há contexto artificial ou enriquecimento para retrieval. O N:N do schema
permite reprojeções futuras, mas a versão 1 é deliberadamente 1:1.

Parser, cobertura e projeção são validados em memória antes da transação. A
transação persiste ato, versão, provisions, unidades e links atomicamente;
qualquer falha causa rollback. A identidade natural torna a reexecução
idempotente.

Reprojeção recebe obrigatoriamente um SHA de snapshot persistido. O caso de
uso não possui `SourceAcquirer`, cliente HTTP nem fallback remoto.

## Auditoria e proveniência

A auditoria recalcula SHA e `version_hash`, hashes de conteúdo, cobertura,
locators, chaves, ordem, pais, links e contagens materializadas. O locator é
um objeto tipado com intervalo zero-based de parágrafos e anchor opcional.

O comando `corpus rastrear` mostra a cadeia da SearchUnit para a Provision,
ActVersion, SourceSnapshot e URL oficial. A aceitação da Fase 0 permanece
pendente até o usuário conferir cinco amostras distribuídas na ordem documental.
