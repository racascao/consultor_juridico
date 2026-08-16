# Consistência física da identidade normativa

## 1. Problema e decisão

A FK anteriormente proposta `(legal_provision_id, element_type)` garantia tipo,
mas permitiria uma ocorrência da CF apontar para provision do ADCT. A solução
mínima é adicionar `legal_elements.legal_act_id UUID NOT NULL` como redundância
controlada e usar duas FKs compostas.

A autoridade semântica do ato da ocorrência continua sendo
`LegalVersion.legal_act_id`. A coluna repetida não é editável como conceito
independente; existe para que PostgreSQL prove simultaneamente:

```text
LegalElement.legal_act_id
  = LegalVersion.legal_act_id
  = LegalProvision.legal_act_id
```

## 2. Candidate keys e FKs finais

### LegalVersion

- `uq_legal_versions_id_legal_act UNIQUE(id, legal_act_id)`.

### LegalProvision

- `uq_legal_provisions_act_identity_key UNIQUE(legal_act_id, identity_key)`;
- `uq_legal_provisions_id_legal_act UNIQUE(id, legal_act_id)`, alvo da FK parent;
- `uq_legal_provisions_id_legal_act_type UNIQUE(id, legal_act_id, element_type)`,
  alvo da FK de occurrence.

As duas últimas são logicamente redundantes com a PK UUID, mas ambas são
necessárias porque PostgreSQL exige uma candidate key que corresponda exatamente
às colunas referenciadas por cada FK.

FKs da futura 005:

```text
fk_legal_provisions_legal_act_id_legal_acts
  legal_provisions(legal_act_id)
  → legal_acts(id)
  ON DELETE RESTRICT ON UPDATE NO ACTION

fk_legal_provisions_parent_act
  legal_provisions(parent_id, legal_act_id)
  → legal_provisions(id, legal_act_id)
  ON DELETE RESTRICT ON UPDATE NO ACTION

fk_legal_elements_version_act
  legal_elements(legal_version_id, legal_act_id)
  → legal_versions(id, legal_act_id)
  ON DELETE CASCADE ON UPDATE NO ACTION

fk_legal_elements_provision_act_type
  legal_elements(legal_provision_id, legal_act_id, element_type)
  → legal_provisions(id, legal_act_id, element_type)
  ON DELETE RESTRICT ON UPDATE NO ACTION
```

A FK simples atual `legal_elements.legal_version_id → legal_versions.id` deve ser
substituída pela composta, evitando dois caminhos referenciais redundantes.

## 3. LegalProvision tree

Campos congelados:

| Coluna | Tipo | Nullable | Default |
|---|---|---:|---|
| id | UUID | não | aplicação |
| legal_act_id | UUID | não | nenhum |
| parent_id | UUID | sim | nenhum |
| element_type | VARCHAR(50) | não | nenhum |
| number_label | VARCHAR(100) | sim | nenhum |
| identity_key | VARCHAR(1000) | não | nenhum |
| created_at | TIMESTAMPTZ | não | now() |

Tipos permitidos: DOCUMENT_ROOT, PREAMBLE, TITLE, CHAPTER, SECTION, SUBSECTION,
ARTICLE, CAPUT, PARAGRAPH, INCISO, ALINEA e ITEM. NOTE é proibido.

`parent_id` nulo é permitido somente para DOCUMENT_ROOT. A FK composta garante
parent e child no mesmo ato. O índice parcial
`uq_legal_provisions_one_root_per_act` em `legal_act_id WHERE element_type =
'DOCUMENT_ROOT'` garante no máximo uma raiz; existência é invariante do serviço.

## 4. NOTE e occurrences normativas

`legal_act_id` é NOT NULL para todas as occurrences, inclusive NOTE. NOTE pertence
à LegalVersion/LegalAct, mas não possui identidade normativa.

CHECK final:

```sql
(
  element_type = 'NOTE' AND legal_provision_id IS NULL
) OR (
  element_type <> 'NOTE' AND legal_provision_id IS NOT NULL
)
```

Nome: `ck_legal_elements_provision_presence`. O CHECK existente de NOTE/role já
garante que NOTE é não normativa e os demais tipos são normativos; não se duplica
essa parte na nova expressão.

Com `MATCH SIMPLE`, a FK tripla não exige alvo quando `legal_provision_id IS NULL`,
mas continua exigindo `legal_act_id` para a FK da LegalVersion.

## 5. Identity key e singleton tokens

Contrato congelado:

```text
identity_key(root) = <ACT>/@root
identity_key(child) = identity_key(parent) + /<TYPE>:<TOKEN>
```

Tokens singleton:

- DOCUMENT_ROOT: `@root`;
- PREAMBLE: `@preamble`;
- CAPUT: `@caput`.

Demais tipos usam `number_label` canonicalizado por NFC, trim, compressão de
whitespace e uppercase, preservando hífen e acentos. `Parágrafo único` usa seu
label factual canonicalizado `ÚNICO`. Nenhum token depende de `raw_text`, rubrica,
path, block index, source line, document order, SourceDocument ou ParsingRun.

Rubricas históricas de TITLE/CHAPTER/SECTION/SUBSECTION compartilham provision
quando ato, parent identity, tipo e label canônico coincidem. Mudança real de
ancestralidade gera chave diferente; matching entre elas não é inferido e a
reconciliação fica bloqueada para revisão.

Em captura futura, buscar por `(legal_act_id, identity_key)`: reutilizar quando
existe; criar quando ausente; bloquear diante de colisão. Não há fuzzy matching.

## 6. CURRENT e localização documental

Índice único parcial:

```sql
CREATE UNIQUE INDEX uq_legal_elements_one_current_per_version_provision
ON legal_elements (legal_version_id, legal_provision_id)
WHERE text_status = 'CURRENT'
  AND content_role = 'NORMATIVE'
  AND legal_provision_id IS NOT NULL;
```

HISTORICAL, REVOKED e UNRESOLVED podem repetir. O predicado inclui role e presença
para documentar exatamente o contrato, embora os CHECKs tornem parte dele
redundante.

`document_order`, `source_locator`, `text_status` e `content_role` pertencem
exclusivamente a LegalElement occurrence. LegalProvision não possui posição,
locator, status ou role.

## 7. ARTICLE/CAPUT e duas árvores

LegalProvision forma a árvore de identidade; LegalElement forma a árvore das
occurrences. Cada ARTICLE occurrence possui exatamente um CAPUT occurrence, mas
um ARTICLE provision pode possuir várias ARTICLE occurrences.

Compatibilidade entre parent occurrence e parent provision exige comparação
recursiva entre árvores e permanece no parser/auditoria. FKs garantem localmente
ato, versão e tipo; não serão criados triggers ou colunas extras de parent
provision em LegalElement.

## 8. Índices e CHECKs finais

Índices novos:

- unique `(legal_act_id, identity_key)` atende reconciliation e consultas por ato;
- `ix_legal_provisions_parent_act(parent_id, legal_act_id)` atende a FK/tree;
- `ix_legal_elements_legal_provision_id(legal_provision_id)` atende lookup/FK;
- partial unique CURRENT descrito acima.

Não criar índice isolado de `legal_provisions.legal_act_id`: ele é prefixo da
unique de identity_key. A indexação existente por legal_version_id atende a FK
composta no lado filho.

CHECKs de LegalProvision:

- `ck_legal_provisions_element_type`: enumeração normativa sem NOTE;
- `ck_legal_provisions_identity_key_nonempty`: `btrim(identity_key) <> ''`;
- `ck_legal_provisions_no_self_parent`: `parent_id <> id`;
- `ck_legal_provisions_root_shape`: DOCUMENT_ROOT iff parent nulo;
- `ck_legal_provisions_number_label`: tipos numerados exigem label não vazio;
- `ck_legal_elements_provision_presence` em LegalElement.

Compatibilidade de tipo já é garantida pela FK tripla e não recebe CHECK
duplicado.

## 9. Migration 005 final — somente especificação

Nome: `005_normative_identity_occurrences`; down revision:
`004_frozen_parsing_model`.

Upgrade, em ordem:

1. abortar antes do DDL se `legal_elements > 0`;
2. criar `uq_legal_versions_id_legal_act`;
3. criar `legal_provisions`, PK, FKs, uniques e CHECKs;
4. criar partial unique root e índice parent;
5. adicionar `legal_elements.legal_act_id UUID NOT NULL` sem default;
6. adicionar `legal_elements.legal_provision_id UUID NULL` sem default;
7. remover a FK simples de LegalVersion;
8. criar `fk_legal_elements_version_act`;
9. criar `fk_legal_elements_provision_act_type`;
10. criar `ck_legal_elements_provision_presence`;
11. criar índice de provision e partial unique CURRENT.

LegalVersions e ParsingRuns existentes, sem LegalElements, não exigem backfill e
não bloqueiam upgrade. A política mínima protege somente dados que precisariam das
novas colunas e da identidade.

Downgrade 005 → 004 aborta antes do DDL se `legal_provisions > 0` ou
`legal_elements > 0`. LegalVersions/ParsingRuns sem dados nessas tabelas podem
permanecer. Com guard satisfeito, remover na ordem inversa: partial CURRENT,
índice, CHECK, FKs compostas; restaurar FK simples de versão; remover colunas;
remover índices/constraints/tabela provisions; remover candidate key da versão.
Nenhum dado é apagado ou convertido.

## 10. Testes futuros e casos mentais

Resultados esperados:

| Caso | Resultado |
|---|---|
| quatro ARTICLE occurrences CF Art. 6, uma CURRENT | aceito |
| quatro ARTICLE occurrences ADCT Art. 60 | aceito |
| CF Art. 1 e ADCT Art. 1 com keys iguais sob atos distintos | aceito |
| occurrence CF → provision ADCT | rejeitado pela FK tripla |
| occurrence ARTICLE → provision CAPUT | rejeitado pela FK tripla |
| occurrence CF → LegalVersion ADCT | rejeitado pela FK version/act |
| NOTE com provision | rejeitado pelo CHECK |
| NOTE sem provision e com ato/versão coerentes | aceito |
| normativo sem provision | rejeitado pelo CHECK |
| dois CURRENT na mesma version/provision | rejeitado pelo índice parcial |
| provision parent em outro ato | rejeitado pela FK parent/act |
| identity_key duplicada no mesmo ato | rejeitado pela unique |
| mesma identity_key em atos diferentes | aceito |
| provision NOTE | rejeitado pelo CHECK de tipo |
| captura futura reutilizando provision pela key | aceito |

Testes de migration deverão também cobrir upgrade/downgrade em banco descartável,
guards, catálogo físico, ações ON DELETE/UPDATE e ausência de warnings ORM.

## 11. Impactos futuros

ORM: criar LegalProvision e relationships `LegalAct.provisions`,
`LegalProvision.legal_act/parent/children/occurrences`; adicionar a LegalElement
`legal_act_id`, `legal_provision_id` e `legal_provision`. Joins compostos exigirão
`foreign_keys`/`primaryjoin` explícitos e `overlaps` apenas quando tecnicamente
necessário, sem silenciar warnings globalmente.

Parser 4B.3.4: produzir `ParsedLegalProvision` e occurrences; toda occurrence
normativa recebe identity key, NOTE não. Auditoria: validar collisions, unmatched,
act/type mismatch, múltiplos CURRENT e compatibilidade entre as duas árvores,
mantendo ARTICLE/CAPUT, order, hierarchy, provenance, coverage e determinismo.

## 12. Decisões congeladas e riscos

Congelados: redundância de ato, quatro FKs acima, identity algorithm, singleton
tokens, rubrica fora da identidade, reconciliation exata e partial unique CURRENT.

Riscos residuais: mudanças reais de ancestry bloqueiam reconciliation; identity
key é regra versionada; compatibilidade recursiva entre árvores permanece na
auditoria; status editorial pode ficar UNRESOLVED.
