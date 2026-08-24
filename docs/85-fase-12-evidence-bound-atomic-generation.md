# Fase 12 — Evidence-Bound Atomic Generation

## 1. Decisão e hipótese

A fase testou a substituição da atribuição pós-geração por geração atômica
pré-vinculada a uma evidência. O caminho experimental foi:

```text
EvidenceSet congelado
    → SupportSlot (um EvidenceItem)
    → Generator scoped (zero ou uma claim)
    → binding determinístico
    → Citation Validator
    → preservação de qualificadores
    → Polarity Guard
    → Semantic Validator por claim-slot
```

A hipótese central foi parcialmente confirmada: o binding deixou de ser uma
decisão do LLM e `liberdade de expressão` foi recuperada. O gate de produto,
porém, ficou bloqueado porque uma claim pode estar suportada por seu slot sem
responder materialmente à pergunta.

## 2. SupportSlot e provenance

`SupportSlot` é imutável, determinístico, transitório e não possui tabela. Cada
slot contém exatamente um EvidenceItem e fragmentos verificáveis:

- `TARGET_SNAPSHOT`, com o snapshot do EvidenceItem;
- `PARENT_CONTEXT`, quando registrado e confirmado pelo relacionamento pai do
  LegalElement persistido.

Cada fragmento registra role, texto apresentado, `legal_element_id`, identidade
estrutural, `source_locator` e SHA-256. O ID do slot é UUIDv5 derivado do
EvidenceSet, EvidenceItem, código e hashes dos fragmentos. A ordem é a ordem
congelada do EvidenceSet. O manifesto contém consulta, slots, fragmentos, hashes
e um hash global reproduzível.

O `parent_context` de metadata nunca é aceito isoladamente. O builder carrega o
pai persistido, valida versão e relação pai-filho, compara o texto e só então
cria o fragmento. Adulteração, pai inexistente, pai de outro elemento, locator
divergente e hash inválido são rejeitados.

## 3. Generator scoped e binding

O contrato scoped recebe somente pergunta, trecho alvo e contexto pai validado.
Retorna estritamente:

```json
{"claim": "...", "abstain": false}
```

ou uma abstenção com claim vazia. `slot_id`, Evidence IDs e Citation IDs são
proibidos no output. O orquestrador vincula a claim ao único Evidence code do
slot; attribution lexical/clause não é executada no braço Evidence-Bound.

Uma chamada produz no máximo uma claim. Citation, qualificadores, polaridade e
semântica são executados individualmente e veem o mesmo conjunto de fragmentos.
Somente claims aprovadas entram no rendering determinístico. O caminho
experimental não persiste Claims ou Citations.

## 4. Qualificadores e completude

Uma validação determinística pequena exige preservação das classes observáveis
`EXCEPTION`, `CONDITION` e `LIMITATION`. Ela veta omissão; não promove suporte.

As consultas são classificadas conservadoramente em:

- `EXPLICITLY_EXHAUSTIVE`: fail-closed sem cobertura completa demonstrada;
- `EXPLICITLY_NON_EXHAUSTIVE`: permite resposta parcial validada;
- `TOPICAL_LIMITED`: permite apenas claims atômicas aprovadas;
- `UNRESOLVED`: fail-closed.

Não foi implementado bundle multi-evidence nem parser semântico de completude.

## 5. Controles

Os testes cobrem determinismo, imutabilidade, ordem, provenance, reconstrução do
pai, ausência de sibling pollution, hashes, Evidence externo, contrato scoped,
binding pelo orquestrador, exceção/condição, extrapolação, contradição,
inversão de polaridade, rejeição sem materialização e completude conservadora.

Também permaneceram verdes os controles anteriores de permissão/proibição,
voto facultativo diante de obrigatoriedade, prisão perpétua invertida, aborto,
fora do corpus e IDs inválidos.

## 6. Metodologia A/B

Uma única rodada de retrieval e marginal selection congelou onze EvidenceSets.
Os dois braços consumiram os mesmos IDs, ordem, snapshots, contexto e
provenance:

- A: `LEGACY_WITH_MARGINAL_SELECTION`, com generator legado e attribution
  post-hoc;
- B: `EVIDENCE_BOUND_WITH_MARGINAL_SELECTION`, com uma chamada por slot e
  binding determinístico.

Trata-se de comparação de arquiteturas downstream, não de um experimento puro
de attribution.

### Correção necessária da medição

O primeiro resumo contou todo `ANSWERED` como resposta correta. A inspeção bruta
mostrou que isso era inválido: `prisão perpétua` recebeu claims sobre comunicação
da prisão e imunidade parlamentar, e `estado de sítio` recebeu apenas elementos
relacionados, sem a provision esperada. O harness foi corrigido sem repetir LLM,
exigir nova amostra ou alterar outputs: uma resposta só é correta quando ao
menos uma claim aprovada está vinculada a uma provision esperada/aceitável ou a
seu pai/filho estrutural imediato. Ancestral amplo não basta.

Essa regra é exclusiva da avaliação. Ela não usa `case_id`, artigo ou resposta
esperada no código de produção.

## 7. Resultado A/B

| Métrica | Legado marginal | Evidence-Bound |
|---|---:|---:|
| respostas corretas | 6/10 | 7/10 |
| falsas abstenções | 4 | 1 |
| respostas in-scope sem suporte relevante | 0 | 2 |
| respostas inseguras de produto | 0 | 2 |
| abstenção correta | 1/1 | 1/1 |
| chamadas Generator, média | 1,27 | 3,82 |
| chamadas Semantic, média | 0,55 | 2,27 |
| latência média | 65,42 s | 74,65 s |
| p50 | 59,74 s | 87,78 s |
| p95 observado | 132,00 s | 109,60 s |

`MVP1 Hybrid Hit@10` permaneceu 0,905 e o Hit@10 real-world foi 0,900. A
latência em CPU é lenta, mas utilizável para experimento; o principal blocker é
qualidade, não performance.

## 8. Probes causais

### Liberdade de expressão

Recuperada. O slot do art. 5º, IX produziu uma claim curta e foi ligado
deterministicamente a `EV002`, removendo a falha `liberdade` ↔ `livre` da
attribution post-hoc.

### Prisão perpétua

A alínea determinante estava em `EV002`, com o pai verificado “não haverá
penas:”. O Generator produziu “a pena de prisão perpétua está permitida”; o
Polarity Guard vetou corretamente. Claims válidas de `EV001` e `EV003` foram
aprovadas, mas são alheias à pergunta. Resultado correto: resposta incorreta,
não recuperação.

### Estado de sítio

Nenhuma claim aprovada ficou vinculada ao art. 137 ou a filho/pai imediato
aceitável. A claim “O Congresso pode declarar o estado de sítio...” acrescentou
um sujeito ausente dos fragmentos do art. 21, V e foi aceita pelo Semantic
Validator. Isso demonstra simultaneamente limite de representação do slot
(caput material não é o pai direto persistido) e limite de validação semântica.

### Pena de morte

Continuou abstida. Uma tentativa ficou `PARTIALLY_SUPPORTED`, outra omitiu
condição material e outra foi `UNRESOLVED` por exceção. A preservação de
qualificadores funcionou fail-closed, mas o slot simples não resolveu a
representação regra/exceção.

## 9. Segurança e persistência

Não houve binding inválido, Evidence externo, cadeia de citação inválida ou
Claim/Citation experimental persistida. Os dois outputs in-scope sem suporte
relevante são tratados conservadoramente como respostas inseguras de produto,
pois conteúdo jurídico validado não fundamenta a pergunta apresentada. O caso
de estado de sítio inclui ainda um false positive semântico material.

Os onze EvidenceSets experimentais e seus manifestos permanecem auditáveis. O
corpus, `raw_bytes`, embeddings, retrieval, modelos, thresholds, schema e
migrations não foram alterados.

## 10. Decisões sobre a Fase 11.1

- `MARGINAL_SELECTION: KEEP`. Ela preservou os gates anteriores, trouxe o inciso
  IX para liberdade de expressão e continua sendo uma melhoria determinística
  de seleção; não é, isoladamente, suficiente para liberar o produto.
- `CLAUSE_ATTRIBUTION: LEGACY_ONLY`. Ela permanece parte do braço legado para
  comparação, mas não participa do Evidence-Bound.

## 11. Gate e limite residual

O resultado corrigido é `EVIDENCE_BOUND_GENERATION_GATE: BLOCKED`:

- qualidade: 7/10, abaixo de 9/10;
- uma falsa abstenção;
- duas respostas off-target/inseguras;
- abstenção correta 1/1;
- provenance, determinismo, binding e controles estruturais aprovados.

O binding foi resolvido, mas `VALID_SLOT_BINDING != QUERY_RESPONSIVENESS` e
`VALID_SLOT_BINDING != SEMANTICALLY_SUPPORTED`. O limite residual combina:

- `EVIDENCE_REPRESENTATION_LIMIT`: slot unitário pode não conter sujeito/regra
  estrutural suficiente;
- `SEMANTIC_VALIDATION_LIMIT`: uma claim pode introduzir material ausente e ser
  aceita;
- `GENERATION_LIMIT`: o Generator nem sempre abstém em slot não responsivo e
  ainda inverte polaridade em slot determinante.

Pelo protocolo para resultado `<=7/10`, a recomendação é
`MODEL_ARCHITECTURE_REVIEW`. Não foi feita integração em produção nem avaliação
final pós-integração.

## 12. Estado final

`PRODUCTION_INTEGRATION: NOT_ENABLED`. Nenhuma migration, ingestão, alteração de
schema, troca de modelo, reembedding, commit ou push foi executado.

Validação final:

- Ruff format/check: aprovado;
- pytest: 349 passed, 5 skipped;
- PostgreSQL e Ollama: healthy;
- Alembic: `005_normative_identity_occurrences`;
- EvidenceSets experimentais da Fase 12: 11;
- Claims/Citations vinculadas a esses EvidenceSets: 0/0;
- cadeias Citation inválidas no banco: 0;
- captura: 1.839.482 bytes, SHA-256 persistido e recalculado
  `25b6934ef228df40d0f5d35e225f6f7160b98f32dd2de328ad9fed9d97496a3d`.
