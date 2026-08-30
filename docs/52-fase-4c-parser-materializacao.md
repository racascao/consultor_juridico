# Fase 4C — parser final, identidade normativa e materialização

## Objetivo e resultado

A Fase 4C conecta o parser em memória ao modelo físico da Migration 005 sem
alterar `raw_bytes`. O pipeline valida SHA-256, decodifica, constrói DOM e blocos,
segmenta CF/ADCT, gera árvores e identidades, executa a auditoria e somente então
materializa o resultado. A captura real foi aprovada sem blockers.

## Identidade normativa

`LegalProvision` é a identidade estável e `LegalElement` é uma ocorrência numa
`LegalVersion`. As chaves são determinísticas e hierárquicas dentro de cada ato:

- roots: `CF88/@root` e `ADCT/@root`;
- filhos: `<parent>/<ELEMENT_TYPE>:<TOKEN>`;
- `PREAMBLE` e `CAPUT` usam tokens singleton;
- tipos numerados usam rótulo factual normalizado conservadoramente;
- `NOTE` não possui identidade normativa.

Redações corrente, histórica, revogada ou não resolvida podem apontar para a
mesma provision. A auditoria impede ocorrência normativa sem identidade,
divergência de ato/tipo e mais de uma ocorrência `CURRENT` por provision/version.
Não existe fuzzy matching.

## Auditoria da captura real

```text
gate=APPROVED_FOR_MATERIALIZATION
blockers=0
CF88: provisions=3133 elements=5063
ADCT: provisions=963 elements=1712
audit_fingerprint=d548adad4f12b4361aff3739ddbda687238b36f2ca53708fc083a5ada9a102bb
cf88_tree_fingerprint=791fe6cebfbf98c68ced8a28db7b3793d56ef7b32e3903625336dfa4a51305a1
adct_tree_fingerprint=57e6aee778c04d4d8e0e3efdf5a3141371bc43e24a3f3459965910348219dd71
```

Sete blocos não estruturais da CF permanecem diagnosticados como warnings;
nenhum é `PARSER_MISSED_STRUCTURE`. Estados `UNRESOLVED` são preservados.

## Transações e falhas

TX1 cria ou reutiliza a `ParsingRun` lógica em `RUNNING`. Parsing e auditoria
ocorrem em memória. TX2 cria conjuntamente atos, versões, provisions e
occurrences, ativa CF/ADCT e marca a run `COMPLETED` num único commit. Qualquer
falha causa rollback integral e TX3 registra `FAILED`.

Teste com falha injetada comprovou que nenhum dado derivado parcial sobrevive.
O retry reutiliza a mesma run lógica e pode concluir.

## Idempotência e CLI

`consultor-juridico parse constitution` seleciona a captura mais recente ou
aceita `document_id`. A primeira execução real retornou `CREATED`; a segunda
retornou `ALREADY_PARSED`, sem alterar contagens.

`consultor-juridico parse status` informa contagens, estado e fingerprint.

## Estado persistido validado

```text
sources=1
source_documents=1
parsing_runs=1 COMPLETED
legal_acts=2
legal_versions=2 ACTIVE
legal_provisions=4096
legal_elements=6775
```

CF/88 possui 3.133 provisions e 5.063 occurrences; ADCT possui 963 e 1.712. Não
há occurrence normativa sem provision, NOTE com provision, divergência ato/tipo
ou colisão de ocorrência corrente.

## Limites

Esta fase não implementa chunking, FTS, embeddings, retrieval, Evidence,
Citation ou LLM. Warnings e textos `UNRESOLVED` permanecem auditáveis.
