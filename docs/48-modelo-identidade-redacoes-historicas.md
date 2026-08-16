# Modelo de identidade normativa e redações históricas

## 1. Problema e evidências

A auditoria das Fases 4B.3.1–4B.3.2 comprovou que `LegalElement` concentra duas
responsabilidades incompatíveis: identidade jurídica estável e ocorrência física
de uma redação em uma captura. O HTML aceito contém 65 grupos de ARTICLE com a
mesma chave estrutural e quatro rubricas alternativas. O modelo 004, interpretando
ARTICLE como identidade, não consegue preservar essas ocorrências sem duplicar a
identidade, criar vários CAPUTs ou perder texto normativo.

Evidências obrigatórias:

- CF Art. 6º: quatro ocorrências nos blocos 156–159, com redações `UNRESOLVED`,
  duas `HISTORICAL` e uma `CURRENT`;
- ADCT Art. 60: quatro ocorrências nos blocos 3668, 3670, 3678 e 3715, incluindo
  subárvores distintas de parágrafos, incisos, alíneas e notas;
- ADCT Art. 117: bloco 4185 `HISTORICAL` e bloco 4186 `CURRENT`, sendo a segunda
  ocorrência acompanhada de incisos;
- headings: rubricas anteriores/correntes de servidores públicos, militares,
  advocacia pública e família também aparecem como ocorrências alternativas.

Logo, uma redação não pertence apenas ao CAPUT: ela pode ser a ocorrência de uma
subárvore inteira, começando em ARTICLE, SECTION ou outro elemento normativo.

## 2. Requisitos

1. Uma identidade normativa sobrevive a mudança textual, reparse e nova captura.
2. Cada ocorrência preserva texto, árvore, ordem, status, notas, links e locator.
3. CF Art. 1º e ADCT Art. 1º permanecem identidades distintas.
4. Histórico pode ter N ocorrências; CURRENT pode ter no máximo uma ocorrência
   por identidade dentro de uma LegalVersion.
5. Incerteza de matching ou status falha fechada e impede materialização.
6. A cadeia futura deve citar a ocorrência textual que fundamentou a resposta e
   alcançar também sua identidade abstrata.
7. Não se introduzem datas de vigência inferidas, eventos de EC ou temporalidade
   bitemporal no MVP1.

## 3. Conceitos finais

### 3.1 LegalProvision

`LegalProvision` é a identidade normativa estável de um nó da CF ou do ADCT. Não
carrega texto, `document_order`, status ou proveniência física. Forma uma árvore
de identidades e possui UUID persistente, reconciliado por chave natural auxiliar.

Exemplos: CF/ARTICLE/6, ADCT/ARTICLE/60, CAPUT do CF/ARTICLE/6 e SECTION V-A sob
seu ancestral normativo. O ato faz parte do escopo: CF/ARTICLE/1 e
ADCT/ARTICLE/1 nunca colidem.

### 3.2 LegalElement

`LegalElement` passa a representar uma ocorrência documental/versionada de uma
identidade normativa dentro de uma LegalVersion. Mantém a árvore física já
existente e seus campos `raw_text`, `normalized_text`, `document_order`,
`text_status`, `content_role`, `source_locator`, `parser_metadata` e `path`.

Todo elemento normativo aponta para exatamente um `LegalProvision`. NOTE não é
identidade normativa e não aponta para provision. Uma redação é representada
pela ocorrência raiz relevante e sua subárvore de ocorrências; não se cria uma
tabela `LegalRedaction` no MVP1.

Assim, “redação” é uma propriedade estrutural do conjunto de ocorrências, não um
atributo exclusivo do CAPUT nem uma nova entidade temporal.

## 4. Alternativas consideradas

### A — múltiplos LegalElement como identidades

É a situação atual. Preserva o HTML com pouca implementação, mas torna ambíguos
retrieval, relacionamento, citação e matching entre capturas. Quatro UUIDs para
o Art. 6º parecem quatro dispositivos. Rejeitada.

### B — múltiplos CAPUTs sob ARTICLE único

Resolve somente alterações do caput, viola a invariante congelada e não representa
subárvores históricas do Art. 60 nem rubricas de SECTION. Rejeitada.

### C — REDACTION como novo element_type

Permite `ARTICLE → REDACTION → CAPUT`, mas mistura um agrupador editorial com a
taxonomia jurídica, aumenta profundidade, exige regras especiais para headings e
faz Citation/Chunk decidir entre ARTICLE, REDACTION e texto. Rejeitada para o MVP.

### D — identidade e ocorrência em entidades distintas

`LegalProvision` identifica; `LegalElement` documenta uma ocorrência. Resolve
artigos, subdivisões e headings com uma regra uniforme, preserva a árvore física e
mantém Chunk/Evidence ligados ao texto exato. Recomendada.

### Alternativa adicional — LegalRedaction + árvore de ocorrências

Uma terceira tabela agruparia formalmente cada redação. É expressiva, porém
redundante para a captura atual: a raiz da ocorrência já delimita a subárvore e
cada nó possui status/proveniência. Fica adiada até existir caso que não possa ser
reconstruído pelas ocorrências.

| Critério | A | B | C | D |
|---|---|---|---|---|
| Identidade estável | baixa | parcial | parcial | alta |
| Subárvore histórica | ambígua | não | sim | sim |
| Headings históricos | ambíguo | não | especial | uniforme |
| Impacto downstream | ambíguo | alto | alto | baixo |
| Evolução entre capturas | fraca | fraca | média | forte |
| Complexidade MVP | baixa enganosa | média | média/alta | média e localizada |

## 5. Modelo conceitual e cardinalidades

```text
LegalAct 1 ── N LegalProvision
LegalProvision 0..1 ── N LegalProvision       (árvore de identidade)

SourceDocument 1 ── N ParsingRun
ParsingRun 1 ── N LegalVersion
LegalAct 1 ── N LegalVersion
LegalVersion 1 ── N LegalElement              (árvore documental)
LegalProvision 1 ── N LegalElement normativo  (ocorrências)
LegalElement 0..1 ── N LegalElement           (árvore da ocorrência)
```

`LegalVersion` continua sendo o snapshot estruturado do ato inteiro derivado de
um SourceDocument por uma ParsingRun. `LegalVersion != redação`: uma versão contém
ocorrências correntes, históricas, revogadas e unresolved apresentadas naquela
captura.

`ParsingRun` permanece inalterado. Ele identifica o processamento lógico; não é
repetido em LegalProvision nem diretamente em LegalElement.

## 6. Identidade normativa e chave auxiliar

A PK de LegalProvision é UUID. A chave auxiliar determinística é escopada pelo
LegalAct e construída da cadeia de identidades, nunca de texto ou locator:

```text
legal_act + parent identity + element_type + canonical number_label/singleton
```

Exemplos conceituais:

```text
CF88/DOCUMENT_ROOT
CF88/.../ARTICLE:6
CF88/.../ARTICLE:6/CAPUT
ADCT/DOCUMENT_ROOT/ARTICLE:1
```

Para tipos numerados, o label factual é canonicalizado somente para matching
(`116-A`, romanos e alíneas), preservando o label original na ocorrência. Root,
PREAMBLE e CAPUT usam tokens singleton definidos pelo parser. Rubrica textual não
participa da chave; por isso renomear “Dos Servidores Públicos Civis” para “Dos
Servidores Públicos” não cria outra SECTION quando marker e ancestral normativos
são os mesmos.

Essa chave não é PK nem prova jurídica autônoma. Se uma emenda mover um dispositivo
entre ancestrais ou produzir colisão/ambiguidade, o parser não cria identidade
silenciosamente: registra conflito de reconciliação e bloqueia o gate. Matching
manual e eventos legislativos ficam adiados.

## 7. Onde residem ordem, status, role e proveniência

| Dado | Entidade | Motivo |
|---|---|---|
| UUID estável, tipo, label canônico, parent normativo | LegalProvision | identidade abstrata |
| `document_order` | LegalElement | cada ocorrência possui posição física própria |
| `source_locator` e `parser_metadata` | LegalElement | pertencem à captura e ao parser |
| `raw_text`, `normalized_text`, `path` | LegalElement | projeção documental/versionada |
| `text_status` | LegalElement | CURRENT/HISTORICAL/REVOKED descreve ocorrência |
| `content_role` | LegalElement | diferencia ocorrência normativa e NOTE |

Um LegalProvision não é CURRENT. CURRENT é uma ocorrência daquele provision em
uma LegalVersion. NOTE permanece `NOT_APPLICABLE`, não normativa e sem provision.

## 8. ARTICLE/CAPUT, subárvores e rubricas

A invariante passa a ser: cada ocorrência ARTICLE possui exatamente um CAPUT.
Várias ocorrências ARTICLE podem apontar para a mesma identidade ARTICLE; seus
CAPUTs apontam para a mesma identidade CAPUT e cada ocorrência mantém sua própria
subárvore.

Para headings, ocorrências SECTION históricas e corrente apontam para a mesma
LegalProvision SECTION. O `raw_text` de cada ocorrência preserva sua rubrica. A
árvore de provisions não duplica o heading por mudança de texto.

## 9. Casos reais

### CF Art. 6º

```text
Provision CF/ARTICLE:6
├── Element bloco 156 UNRESOLVED ── CAPUT occurrence
├── Element bloco 157 HISTORICAL ── CAPUT occurrence
├── Element bloco 158 HISTORICAL ── CAPUT occurrence
└── Element bloco 159 CURRENT ───── CAPUT + parágrafo/notes
```

Os quatro ARTICLE elements apontam para um provision; cada CAPUT occurrence
aponta para o provision CAPUT filho.

### ADCT Art. 60

Um LegalProvision ARTICLE:60 recebe quatro ARTICLE occurrences. Cada uma conserva
sua própria subárvore de parágrafos/incisos/alíneas e cada descendente é reconciliado
com seu provision correspondente. Não se reduz a mudança ao CAPUT.

### ADCT Art. 117

O provision ARTICLE:117 possui uma ocorrência HISTORICAL (bloco 4185) e outra
CURRENT (4186). A segunda mantém seus três incisos. A unique parcial de CURRENT
permite essa combinação e rejeita duas correntes para a mesma identidade/versão.

### Rubrica histórica

SECTION sob o mesmo parent e label produz um provision. A ocorrência antiga
preserva “Dos Servidores Públicos Civis” e status histórico/unresolved; a corrente
preserva “Dos Servidores Públicos”. Ambas podem ter subárvore própria.

### CF Art. 1º versus ADCT Art. 1º

Os provisions pertencem a LegalActs diferentes e possuem chaves/UUIDs diferentes,
mesmo que tipo e label coincidam.

## 10. Nova captura futura

SourceDocument Y e parser v1 geram novas LegalVersions CF/ADCT. O reconciliador
encontra o provision existente do Art. 6º pela chave auxiliar e cria novas
LegalElement occurrences ligadas a Y por LegalVersion. A ocorrência antiga
permanece auditável na versão de X; a nova captura pode apresentar outra CURRENT.

“No máximo uma CURRENT” é escopado por `(legal_version_id, legal_provision_id)`,
não globalmente. A ativação da LegalVersion continua determinando o snapshot usado
por retrieval padrão. Não há deduplicação de occurrences entre SourceDocuments:
cada captura é evidência documental própria.

## 11. Rastreabilidade, chunking e citation

A cadeia futura fica:

```text
Claim → Citation → EvidenceItem → Chunk
      → LegalElement occurrence → LegalProvision identity
      → LegalVersion → ParsingRun → SourceDocument → Source
```

Chunk continua apontando para LegalElement, pois o texto indexado pertence a uma
ocorrência específica. A identidade é alcançada pela nova FK. Retrieval padrão
filtra LegalVersion ativa, `NORMATIVE + CURRENT`; consulta histórica poderá incluir
outros status explicitamente. EvidenceItem mantém snapshot e occurrence exatos.
Citation consegue exibir “Art. 6º da Constituição” pela identidade e provar qual
redação, captura, parser, locator e texto fundamentaram a resposta.

Nenhuma alteração em Chunk, EvidenceItem ou Citation é necessária na migration
005.

## 12. Invariantes

1. LegalProvision pertence exatamente a um LegalAct.
2. Identidade não depende de texto, UUID de run, ordem, path ou locator.
3. Parent e filho de provision pertencem ao mesmo LegalAct.
4. `(legal_act_id, identity_key)` é único.
5. LegalElement normativo aponta para exatamente um provision do mesmo ato e tipo.
6. NOTE não aponta para provision.
7. LegalElement, LegalVersion e LegalProvision pertencem fisicamente ao mesmo ato
   por FKs compostas e redundância controlada de `legal_act_id`.
8. Cada ocorrência pertence a uma LegalVersion e mantém ordem/proveniência.
9. Há no máximo uma ocorrência CURRENT por provision em uma LegalVersion.
10. Histórico/revogado/unresolved podem possuir N ocorrências.
11. Cada ARTICLE occurrence possui exatamente um CAPUT occurrence.
12. Parent occurrence e child occurrence continuam na mesma LegalVersion.
13. A árvore de occurrences reconstrói a ordem documental integral.
14. Matching ambíguo de identity_key bloqueia a materialização.

## 13. Migration 005 proposta — somente especificação

Nome candidato:

```text
005_normative_identity_occurrences
```

### 13.1 Nova tabela `legal_provisions`

| Coluna | PostgreSQL | Nullable | Default |
|---|---|---:|---|
| `id` | UUID | não | aplicação |
| `legal_act_id` | UUID | não | nenhum |
| `parent_id` | UUID | sim | nenhum |
| `element_type` | VARCHAR(50) | não | nenhum |
| `number_label` | VARCHAR(100) | sim | nenhum |
| `identity_key` | VARCHAR(1000) | não | nenhum |
| `created_at` | TIMESTAMPTZ | não | `now()` |

Constraints e índices candidatos:

- PK `pk_legal_provisions`;
- FK `fk_legal_provisions_legal_act_id_legal_acts`, `ON DELETE RESTRICT`;
- unique `uq_legal_provisions_act_identity_key(legal_act_id, identity_key)`;
- unique `uq_legal_provisions_id_legal_act(id, legal_act_id)`;
- unique `uq_legal_provisions_id_legal_act_type(id, legal_act_id, element_type)`;
- FK composta `fk_legal_provisions_parent_act(parent_id, legal_act_id) →
  legal_provisions(id, legal_act_id) ON DELETE RESTRICT`;
- CHECK `ck_legal_provisions_no_self_parent(parent_id <> id)`;
- CHECK `ck_legal_provisions_element_type` com todos os tipos normativos da 004,
  exceto NOTE;
- CHECK `ck_legal_provisions_identity_key_nonempty`;
- CHECK de labels equivalente aos tipos numerados da 004;
- CHECK root/parent: somente DOCUMENT_ROOT possui `parent_id IS NULL`;
- índice único parcial `uq_legal_provisions_one_root_per_act`;
- índice `ix_legal_provisions_parent_id`.

`identity_key` de até 1000 caracteres é suficiente para a profundidade observada;
o parser valida o limite antes do INSERT. Não se armazena hash isolado como chave,
evitando identidade opaca e colisão silenciosa.

### 13.2 Alterações em `legal_elements`

Adicionar:

- `legal_act_id UUID NOT NULL`, redundância cuja autoridade semântica permanece
  em `LegalVersion.legal_act_id`;
- `legal_provision_id UUID NULL` — NULL somente para NOTE;
- FK composta
  `fk_legal_elements_version_act(legal_version_id, legal_act_id) →
  legal_versions(id, legal_act_id) ON DELETE CASCADE ON UPDATE NO ACTION`;
- FK composta
  `fk_legal_elements_provision_act_type(legal_provision_id, legal_act_id,
  element_type) → legal_provisions(id, legal_act_id, element_type)
  ON DELETE RESTRICT ON UPDATE NO ACTION`;
- CHECK `ck_legal_elements_provision_presence`: NOTE exige provision NULL e
  qualquer outro tipo exige provision não nulo;
- índice `ix_legal_elements_legal_provision_id`;
- índice único parcial `uq_legal_elements_one_current_per_version_provision` em
  `(legal_version_id, legal_provision_id) WHERE text_status='CURRENT' AND
  content_role='NORMATIVE'`.

Permanecem em LegalElement: árvore por parent, document_order, textos, status,
role, locator, metadata, path e todas as constraints 004. A regra de exatamente
um CAPUT continua na aplicação/auditoria, agora por ARTICLE occurrence.

Adicionar em `legal_versions` a candidate key
`uq_legal_versions_id_legal_act(id, legal_act_id)`. Em `legal_provisions`, usar
`uq_legal_provisions_id_legal_act_type(id, legal_act_id, element_type)`. A FK
simples existente de LegalElement para LegalVersion é substituída pela composta.
Não se move coluna nem se altera Chunk/Evidence/Citation.

### 13.3 Ordem de upgrade

1. guard: abortar se `legal_elements > 0`, pois não há backfill aprovado;
2. criar candidate key de LegalVersion;
3. criar `legal_provisions` e suas constraints/índices;
4. adicionar `legal_elements.legal_act_id` e `legal_provision_id`;
5. substituir a FK simples de versão pela FK composta de ato;
6. criar FK tripla de provision, CHECK, índice e unique parcial;
7. manter integralmente dados de SourceDocument e ParsingRun.

O banco atual, sem dados derivados, é compatível. LegalVersions vazias de elementos
não exigem bloqueio técnico, embora o checkpoint atual também tenha zero versões.

### 13.4 Downgrade

O downgrade 005 → 004 deve abortar antes do DDL se existir qualquer
`legal_provision` ou `legal_element`: remover a identidade quebraria a semântica e
as FKs. LegalVersions/ParsingRuns sem provisions/elements não são transformados
pela 005 e não precisam bloquear.

Com o guard satisfeito, remover em ordem: unique parcial e índice de element;
CHECK e FK de provision; coluna `legal_provision_id`; índices/FK/checks/uniques de
`legal_provisions`; tabela `legal_provisions`. Nenhum dado é convertido ou apagado.

## 14. Impacto futuro no ORM, parser e auditoria

ORM:

- criar model `LegalProvision` com parent/children e occurrences;
- adicionar `LegalAct.provisions`;
- adicionar `LegalElement.legal_provision` nullable somente para NOTE;
- manter ParsingRun e LegalVersion sem alteração semântica.

Parser em memória:

- produzir catálogo/árvore de `ParsedLegalProvision` e árvore de
  `ParsedLegalElement` occurrences;
- atribuir `identity_key` deterministicamente;
- reconciliar todas as ocorrências repetidas com um provision;
- preservar subárvores, sem colapsar texto ou ordem;
- emitir conflito fechado para identidade ambígua.

Auditoria:

- substituir “ARTICLE label repetido” por validação de um provision por chave;
- exigir que ocorrências repetidas legítimas apontem para o mesmo provision;
- validar tipo e ato entre occurrence/provision;
- validar no máximo uma CURRENT por provision/LegalVersion;
- manter ARTICLE/CAPUT por ocorrência, cobertura, ordem, hierarchy e provenance;
- confirmar que as quatro rubricas foram materialmente preservadas como
  ocorrências do heading correto.

Novos critérios mínimos do gate:

```text
IDENTITY_KEY_COLLISION = 0
UNMATCHED_NORMATIVE_OCCURRENCE = 0
ACT_OR_TYPE_IDENTITY_MISMATCH = 0
MULTIPLE_CURRENT_PER_VERSION_PROVISION = 0
PARSER_MISSED_STRUCTURE = 0
blocks_without_audit_record = 0
ARTICLE/CAPUT occurrence invariants = OK
order/hierarchy/provenance/determinism = OK
```

## 15. Riscos e decisões adiadas

Riscos:

- mudança real de ancestralidade pode exigir reconciliação humana;
- status do Planalto continua editorial e pode permanecer UNRESOLVED;
- identity_key depende de regras versionadas e precisa de testes de estabilidade;
- as candidate keys compostas são redundantes em relação às PKs, mas necessárias
  como alvos exatos das FKs que congelam ato e tipo;
- uma future necessidade de agrupar redações que não coincidem com uma subárvore
  observável poderá justificar LegalRedaction.

Adiados: datas de vigência, eventos/entidades de EC, temporalidade bitemporal,
matching manual persistido, consulta histórica de produto, chunking, retrieval,
Evidence/Citation e alterações legislativas genéricas.

## 16. Critérios de aceite da próxima fase

1. revisão humana aprova LegalProvision + LegalElement occurrence;
2. migration 005 implementa somente a seção 13 e passa ciclo isolado;
3. ORM e schema permanecem alinhados;
4. parser produz identities e occurrences determinísticas;
5. casos Art. 6, Art. 60, Art. 117 e rubricas passam sem perda;
6. auditoria satisfaz os novos critérios de gate;
7. banco real continua sem dados derivados até materialização autorizada;
8. Fase 4B.4 permanece bloqueada até migration, adaptação e reauditoria.
