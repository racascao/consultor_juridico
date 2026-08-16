# Implementação da Migration 005 — identidade normativa e ocorrências

## Objetivo

A migration `005_normative_identity_occurrences` implementa mecanicamente o
modelo congelado nos documentos 48–50. `LegalProvision` passa a representar a
identidade normativa estável dentro de um `LegalAct`; `LegalElement` permanece a
ocorrência documental, textual e ordenada dentro de uma `LegalVersion`.

Esta etapa não adapta o parser e não materializa dispositivos da captura real.

## Schema implementado

`legal_provisions` contém UUID, ato, parent opcional, tipo, rótulo, chave de
identidade e timestamp. O banco garante:

- identidade única por `(legal_act_id, identity_key)`;
- pai e filho no mesmo ato;
- tipo normativo válido, sem `NOTE`;
- somente `DOCUMENT_ROOT` sem pai;
- no máximo um root por ato;
- rótulos obrigatórios para tipos numerados.

`legal_elements` recebeu `legal_act_id NOT NULL` e
`legal_provision_id NULL`. A FK composta versão/ato impede divergência entre a
ocorrência e sua versão. A FK provision/ato/tipo impede divergência entre a
ocorrência e sua identidade. `NOTE` exige provision nula; todo elemento normativo
exige provision. Um índice parcial permite no máximo uma ocorrência `CURRENT +
NORMATIVE` por provision e versão, sem limitar redações históricas, revogadas ou
não resolvidas.

## Guards e downgrade

O upgrade aborta se existirem `legal_elements`, porque não há backfill aprovado.
ParsingRuns e LegalVersions sem elementos são preservados e não bloqueiam a
evolução.

O downgrade aborta se existirem `legal_provisions` ou `legal_elements`. Nenhum
dado é removido ou convertido automaticamente. Com essas tabelas vazias, o
schema de domínio retorna à revision 004 em ordem inversa segura.

## Acomodação técnica da tabela alembic_version

Antes da 005, `alembic_version.version_num` era `VARCHAR(32)`. O revision ID
`005_normative_identity_occurrences` possui 34 caracteres; por isso o upgrade
amplia a coluna para `VARCHAR(64)` antes de o Alembic registrar a nova revision.

O downgrade não reduz a coluna. Durante a execução de `downgrade()`, o ID longo
da 005 ainda está armazenado, e uma redução antecipada seria inválida. A
ampliação é administrativa, monotônica e não altera o domínio. Após downgrade,
o valor é `004_frozen_parsing_model`, mas o tipo permanece `VARCHAR(64)`.

O teste descartável comprova:

```text
004 / VARCHAR(32)
→ 005 / VARCHAR(64)
→ 004 / VARCHAR(64)
→ 005 / VARCHAR(64)
```

ParsingRuns e LegalVersions usados para verificar preservação permanecem
íntegros durante o ciclo.

## ORM

O SQLAlchemy contém o model `LegalProvision`, relacionamentos com `LegalAct`,
parent/children e occurrences, além das relações compostas de `LegalElement`.
Migration e metadata usam os mesmos nomes explícitos de constraints e índices.
Os mappers são configurados sem warnings de sobreposição.

## Testes

Os testes cobrem catálogo físico, ciclo de migration em bancos descartáveis,
guards, identidade por ato, parent composto, taxonomias, correspondência de ato
e tipo, presença de provision, notas, unicidade de ocorrência corrente,
múltiplas ocorrências históricas e relationships ORM com INSERTs reais no
PostgreSQL.

## Estado e próximo checkpoint

A Migration 005 apenas habilita a representação física decidida. O gate 4B.4
continua bloqueado até a Fase 4B.3.4 adaptar o parser em memória ao catálogo de
identidades e reexecutar a auditoria. Nenhuma materialização jurídica ocorreu.
