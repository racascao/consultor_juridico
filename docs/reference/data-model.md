# Modelo de dados

O schema efetivo do MVP2 é criado pelas migrations
`001_v02_foundation_corpus` e `002_v02_postgresql_fts`.

```text
Source → SourceSnapshot → ActVersion ← LegalAct
                           ↓
                       Provision (hierarquia)
                           ↓
                SearchUnitProvision ← SearchUnit
```

| Entidade | Responsabilidade |
|---|---|
| `sources` | identidade e URL da autoridade oficial |
| `source_snapshots` | bytes imutáveis, tamanho, hash e metadados HTTP |
| `legal_acts` | identidade estável do ato normativo |
| `act_versions` | materialização por snapshot, parser e projeção |
| `provisions` | ocorrência jurídica hierárquica e ordenada |
| `search_units` | texto recuperável da versão |
| `search_unit_provisions` | proveniência entre unidade e provision |

`Provision` possui `stable_key`, `parent_id`, `document_order`, status, locator
e hash. A FK composta impede pai em outra `ActVersion`. Snapshots são imutáveis
por trigger; hashes e identidades naturais tornam reprocessamento auditável.

No MVP2, evidências, respostas e citações são contratos em memória do pipeline,
não tabelas persistidas. Isso difere do modelo histórico do MVP1.
