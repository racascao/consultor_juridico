# Fase 5 — chunking, FTS, embeddings e retrieval híbrido

## Escopo e resultado

A Fase 5 indexa somente ocorrências `CURRENT + NORMATIVE` das duas
`LegalVersion`s ativas. Não cria EvidenceSet, EvidenceItem, Claim, Citation nem
resposta generativa.

O corpus real resultou em 3.389 chunks, 3.389 vínculos primários e 3.389
embeddings de 768 dimensões. A segunda indexação retornou `ALREADY_INDEXED`.

## Estratégia de chunking

A estratégia `legal_occurrence_current_v1` cria um chunk por ocorrência textual
dos tipos PREAMBLE, TITLE, CHAPTER, SECTION, SUBSECTION, CAPUT, PARAGRAPH,
INCISO, ALINEA e ITEM. ARTICLE permanece container e não duplica seu CAPUT.

Cada chunk contém o ato, a `identity_key` e o `normalized_text`. O vínculo
`ChunkLegalElement` aponta para a ocorrência exata e é marcado como primário.
`token_count` é uma contagem diagnóstica por whitespace, não um tokenizer de LLM.

## FTS

`tsv_content` é preenchido com `to_tsvector('portuguese', chunk_text)`. A busca
usa `websearch_to_tsquery('portuguese', query)` e `ts_rank_cd`, com desempate por
ordem documental e UUID. Todos os 3.389 chunks possuem TSVECTOR e o índice GIN
existente permanece em uso pelo PostgreSQL conforme o plano escolhido.

## Embeddings

O provider é `ollama`, modelo `nomic-embed-text`, versão persistida `latest` e
dimensão observada 768. Documentos usam o prefixo `search_document:` e consultas
usam `search_query:`. Provider/model/version/dimensão são filtros obrigatórios da
busca vetorial, impedindo mistura silenciosa de espaços vetoriais.

A coluna `vector` atual não fixa typmod. Por isso a busca inicial usa distância
de cosseno exata, sem índice HNSW. Para 3.389 vetores o comportamento é adequado
ao MVP; fixar dimensão e HNSW exigiria migration e benchmark próprios.

## Retrieval híbrido

LexicalRetriever e SemanticRetriever produzem ranks independentes. O híbrido usa
Reciprocal Rank Fusion com `k=60`:

```text
score = Σ 1 / (60 + rank)
```

O resultado preserva rank e score lexical, rank e similaridade vetorial, score
RRF, chunk, occurrence, provision, ato, tipo, rótulo e identity_key.

Filtros explícitos disponíveis: ato e tipos de elemento. Status e papel também
fazem parte do contrato interno e têm defaults conservadores `CURRENT` e
`NORMATIVE`.

## Atomicidade e idempotência

Chunks, vínculos, FTS e embeddings são criados numa única transação. Falha
injetada do provider produziu rollback completo em PostgreSQL descartável.
Índice completo existente retorna `ALREADY_INDEXED`; índice parcial é recusado em
vez de ser aceito silenciosamente.

## Avaliação básica

Uma integração opt-in avalia cinco consultas e exige a provision esperada no
top-10 híbrido:

- manifestação do pensamento — art. 5º, IV;
- educação como direito de todos — art. 205;
- meio ambiente ecologicamente equilibrado — art. 225;
- voto direto e secreto — art. 14;
- poderes independentes e harmônicos — art. 2º.

Resultado observado: 5/5 no top-10, além de filtro lexical CF/88 + INCISO
retornando art. 5º, IV na primeira posição.

## CLI

```text
consultor-juridico index build
consultor-juridico index status
consultor-juridico retrieval search "manifestação do pensamento" --mode lexical
consultor-juridico retrieval search "manifestação do pensamento" --mode vector
consultor-juridico retrieval search "manifestação do pensamento" --mode hybrid
```

Também são aceitos `--act` e `--element-types` para diagnóstico jurídico.

## Limitações

- sem HNSW nesta escala inicial;
- `token_count` não representa tokens de um modelo generativo;
- somente snapshot ativo e texto corrente/normativo é indexado;
- RRF não aplica reranker neural adicional;
- avaliação atual é pequena e diagnóstica, não substitui a Fase 7;
- Evidence, Citation e geração permanecem fora do escopo.
