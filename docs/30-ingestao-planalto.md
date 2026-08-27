# Ingestão do Planalto — Fase 3

## Escopo

A Fase 3 captura exclusivamente a Constituição Federal de 1988 e o ADCT a
partir de uma única representação física oficial:

`https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm`

O texto compilado alternativo e o PDF do Diário Oficial não fazem parte desta
fase. A captura não cria versões jurídicas, elementos, chunks ou embeddings.

## Fluxo

```text
Official URL
  → GET HTTP e redirects
  → eventual descompressão de Content-Encoding pelo httpx
  → bytes canônicos, ainda sem decoding de charset
  → SHA-256
  → SourceDocument.raw_bytes (BYTEA)
  → parsing posterior
```

`response.text`, BeautifulSoup e lxml não participam da aquisição.

## Política HTTP

| Configuração | Variável | Default |
|---|---|---:|
| Connect timeout | `INGESTION_CONNECT_TIMEOUT` | 10s |
| Read timeout | `INGESTION_READ_TIMEOUT` | 30s |
| Write timeout | `INGESTION_WRITE_TIMEOUT` | 10s |
| Pool timeout | `INGESTION_POOL_TIMEOUT` | 10s |
| Tentativas máximas | `INGESTION_MAX_ATTEMPTS` | 3 |
| Backoff inicial | `INGESTION_BACKOFF_SECONDS` | 0,5s |
| Limite de Retry-After | `INGESTION_RETRY_AFTER_MAX_SECONDS` | 5s |
| Tamanho mínimo | `INGESTION_MIN_BYTES` | 1.024 bytes |
| Tamanho máximo | `INGESTION_MAX_BYTES` | 10 MiB |
| User-Agent Planalto | `PLANALTO_USER_AGENT` | browser-compatible |

O downloader usa `GET`, segue redirects e solicita `Accept-Encoding: identity`.
Falhas de transporte, timeouts e status 408, 429, 500, 502, 503 e 504 são
transitórios. Outros status não são repetidos. `Retry-After` é respeitado até o
limite configurado. Não há biblioteca externa de retry.

Antes da persistência são verificados apenas status 2xx, Content-Type HTML,
corpo não vazio e limites mínimo/máximo. Nenhum termo ou estrutura jurídica é
procurado no conteúdo.

### User-Agent observado no Planalto

Em diagnóstico real realizado em 2026-08-15, o Planalto apresentou respostas
diferentes conforme o User-Agent:

- `consultor-juridico/0.1`: conexão encerrada pelo servidor;
- User-Agent padrão do curl: TLS estabelecido, mas sem resposta até o timeout;
- User-Agent compatível com navegador: HTTP 200, `Content-Type: text/html` e
  `Content-Length: 1839482`.

Por isso, o adapter usa por default:

```text
Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/151 Safari/537.36
```

O valor é centralizado e substituível por `PLANALTO_USER_AGENT`. Não são usados
browser automation, cookies manuais, proxy especial ou bypass de TLS.

## Raw storage, hash e encoding

`SourceDocument.raw_bytes` é `BYTEA`. O SHA-256 é calculado diretamente sobre
o mesmo objeto `bytes` persistido. Charset declarado é apenas metadado; não há
decoding na Fase 3. `Content-Encoding` também é registrado, mesmo que o payload
já tenha sido descomprimido pela camada HTTP.

## Idempotência e proveniência

A constraint física é:

```text
UNIQUE (source_id, content_hash_sha256)
```

- mesma fonte e mesmo hash: `ALREADY_KNOWN`;
- mesma fonte e hash diferente: nova captura;
- fonte diferente e mesmo hash: documentos distintos.

`Source.base_url` é única e constitui a identidade técnica canônica da fonte.
O repository trata violações concorrentes das duas constraints por savepoint e
nova consulta.

Captura diferente não implica automaticamente uma nova versão jurídica.

### Conditional GET

Antes de nova aquisição, o repository recupera a captura mais recente da mesma
`Source` e `url_source`. Quando presentes em seus metadados, envia:

- `ETag` como `If-None-Match`;
- `Last-Modified` como `If-Modified-Since`;
- ambos preferencialmente quando disponíveis.

O suporte foi confirmado no Planalto com os validators observados:

```text
ETag: "1c0b63-6584ba7465d85"
Last-Modified: Wed, 05 Aug 2026 12:10:12 GMT
```

Ambos produziram `HTTP/1.1 304 Not Modified` em requisições condicionais.
Um `304` retorna `ALREADY_KNOWN`, reutiliza o `SourceDocument` anterior e não
persiste corpo. Um `200` percorre integralmente hash, sanity checks e
persistência.

ETag e Last-Modified são validators fornecidos pelo servidor; não substituem o
SHA-256. O hash continua comprovando a integridade dos bytes efetivamente
persistidos.

## Metadados

`url_source` mantém a URL solicitada. O JSONB `metadata` registra `final_url`,
`redirect_chain`, `status_code`, `content_type`, `declared_charset`,
`content_length_declared`, `received_bytes`, `content_encoding`, `attempts`,
`duration_ms` e `adapter_version`.

Quando disponíveis, também são registrados `etag` e `last_modified`.

Headers são armazenados em `http_headers` como lista ordenada de pares para
preservar ocorrências repetidas.

## CLI

```bash
consultor-juridico ingest constituicao
consultor-juridico ingest status
```

A CLI delega toda a operação ao serviço de aplicação. `ingest status` descreve
capturas documentais e não declara versões jurídicas.

## Integração real

A suíte padrão não acessa a internet. A integração explícita é executada com:

```bash
RUN_PLANALTO_INTEGRATION=1 uv run pytest -m planalto_integration
```

Ela baixa o documento oficial, persiste, relê e compara os bytes, valida o hash
e confirma `ALREADY_KNOWN` na segunda execução. Falhas de rede, proxy, TLS ou da
fonte são reportadas como externas e não flexibilizam as invariantes.

## Limitações

- A resposta depende da disponibilidade e comportamento HTTP do Planalto.
- O downgrade de `BYTEA` para `TEXT` só é possível para bytes UTF-8 válidos e
  falha explicitamente em vez de converter dados arbitrários silenciosamente.
- Encoding textual e semântica jurídica pertencem à Fase 4.
- Duas respostas reais de 1.839.482 bytes apresentaram SHA-256 diferentes por
  causa do valor variável `f5_p` no script de infraestrutura `f5_cspm`.
- Esse script permanece integralmente em `raw_bytes`. A Fase 3 não remove,
  normaliza ou canonicaliza conteúdo F5; conditional GET evita downloads
  desnecessários quando os validators confirmam que o recurso não mudou.
