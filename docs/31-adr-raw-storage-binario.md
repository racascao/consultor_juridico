# ADR 003 — Raw storage binário e identidade da captura

- Status: aceito
- Data: 2026-08-15

## Contexto

Uma URL oficial pode devolver conteúdos diferentes ao longo do tempo. Texto
decodificado não preserva necessariamente o payload adquirido, e o documento
capturado não deve ser confundido com uma versão juridicamente interpretada.

## Decisão

Os bytes canônicos são o payload HTTP após eventual descompressão de
`Content-Encoding` realizada pela camada HTTP, mas antes de decoding de charset,
parsing ou normalização. O sistema solicita `Accept-Encoding: identity`, porém a
correção não depende de o servidor respeitar esse pedido.

O downloader usa `response.content`, que representa esse payload descomprimido
em `bytes`. O SHA-256 é calculado imediatamente sobre esses bytes. Exatamente os
mesmos bytes são persistidos em `SourceDocument.raw_bytes`, uma coluna `BYTEA`.
`response.text` nunca é usado para hash ou raw storage.

`Content-Type`, charset declarado e `Content-Encoding` são metadados. Charset
não altera os bytes da captura e será tratado somente pelo parser posterior.

A identidade técnica idempotente é `(source_id, content_hash_sha256)`. A
identidade de `Source` é sua `base_url` canônica. Assim, bytes iguais em fontes
diferentes preservam proveniências distintas.

Uma nova captura documental indica apenas que outro payload foi observado. Ela
não cria nem ativa automaticamente uma `LegalVersion`.

## Validators HTTP e variabilidade F5

O Planalto confirmou suporte a `ETag`/`If-None-Match` e
`Last-Modified`/`If-Modified-Since`, respondendo `304 Not Modified`. Esses
valores são validators atribuídos pelo servidor e orientam requisições
condicionais; não são provas criptográficas do payload armazenado.

O SHA-256 de `raw_bytes` permanece a verificação criptográfica da captura. Um
validator não substitui o hash e o hash não pode ser conhecido antes do
download.

Aquisições reais sem conditional GET retornaram o mesmo tamanho, 1.839.482
bytes, mas hashes distintos. A diferença observada estava no valor dinâmico
`f5_p` do script de infraestrutura F5 identificado por `f5_cspm`, sem alteração
jurídica material aparente.

Apesar disso, `raw_bytes` não é canonicalizado. Nenhum script é removido ou
modificado, e o SHA-256 é sempre calculado sobre o payload integral recebido.
Uma eventual canonicalização futura é uma decisão distinta, determinística e
dependente de aprovação explícita.

Para evitar a política diferenciada do servidor contra User-Agents não usuais,
o adapter Planalto utiliza um User-Agent browser-compatible configurável. Isso
não introduz browser automation, cookies, proxy ou bypass de TLS.

## Consequências

- Aquisição e interpretação jurídica permanecem separadas.
- Bytes arbitrários, inclusive não UTF-8, são preserváveis.
- Respostas comprimidas e não comprimidas com o mesmo payload descomprimido têm
  a mesma identidade dentro da mesma fonte.
- O downgrade para `TEXT` falha se houver bytes que não formem UTF-8 válido;
  essa falha é intencional para impedir perda silenciosa.
- Um `304` referencia a captura anterior e não cria raw storage vazio.
