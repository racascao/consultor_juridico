# Fase 96 — Medição estrita e Core Evidence Policy v2

## Resultado

A primeira execução EBCG-v1 foi preservada em
`evaluation/results/model_benchmark_95_ebcg_e2e_1/e2e_ebcg_run_1.json` e seu
SHA-256 continua `67d6faffa28a0171896e0e2c97bbc5718192652c7f966aa669380f7e6eeab9b3`.
Ela não foi reexecutada nem sobrescrita.

O antigo aggregate automático contava toda resposta validada como correta e
registrava 9/10. A auditoria offline introduz fidelidade ao target: uma resposta
respondida só é correta quando uma EvidenceItem realmente vinculada à claim
possui `identity_key` pertencente a `expected_provisions ∪
acceptable_provisions` do caso. No artefato histórico, o resultado estrito é
4 respostas corretas, 5 `WRONG_TARGET`, 1 false abstention e 1 abstention
correta. `WRONG_TARGET` possui o estágio `TARGET_FIDELITY`; não é resposta
insegura e tampouco resposta correta.

O auditor `evaluation.audit_target_fidelity` usa apenas o JSON existente e o
dataset local congelado. Como o artefato 95 ainda não serializava a identidade
por EvidenceItem, sua camada de compatibilidade lê a identidade já presente no
label de citação histórico. No caminho E2E futuro, a medição usa diretamente a
cadeia `Claim -> evidence_code -> EvidenceItem.validation_metadata.identity_key`.

## Política v2

O auditor `evaluation.audit_core_evidence_policy` registrou, para cada item
selecionado, cobertura da query, contribuição marginal, relevância base,
score final, posição e rótulo dourado exclusivamente para análise.

| Política | Hits de target nos 10 casos respondíveis |
| --- | ---: |
| v1: `EV001` | 5 |
| A: cobertura → relevância base → posição | 5 |
| B: cobertura → contribuição marginal → relevância base → posição → código | 7 |

Como B melhora v1 e A não, foi integrada como
`QUERY_COVERAGE_MARGINAL_COVERAGE_BASE_RELEVANCE_SELECTED_POSITION`.
Ela só ordena EvidenceItems já selecionadas usando diagnostics previamente
calculados; não recebe pergunta, dataset, `case_id`, targets ou labels dourados.
Se algum signal necessário não existir, EBCG abstém sem fallback. A Core Claim
continua sendo exatamente o `text_snapshot` de uma única Core Evidence, sem
`parent_context`, paráfrase ou composição multi-evidence.

## Locator Fidelity

O falso negativo de pena de morte foi confirmado: a referência interna
`art. 84, XIX` no snapshot literal do Art. 5º, XLVII, a era confundida com um
locator declarado pelo sistema. Para EBCG-v1/v2, quando a claim é exatamente o
snapshot da única EvidenceItem citada, a identidade autoritativa é a da própria
EvidenceItem. Remissões internas deixam de gerar `LOCATOR_MISMATCH`; citations
estruturadas, atribuição, polaridade e veto semântico permanecem obrigatórios.

## Gates e limites

- `CORE_EVIDENCE_V2_GATE: PASS` por 7 > 5 hits projetados.
- `RETRIEVAL_HIT_AT_10` do dataset real-world é 0,900; o threshold histórico
  0,905 pertence ao `mvp1-v1` com 21 casos (`19/21 = 0,904761...`). Portanto
  a proveniência está reconciliada, mas o gate histórico continua pendente para
  a medição aplicável, sem redução de threshold.
- `qualifier_preservation: NOT_YET_MEASURED`; esta fase não introduziu uma nova
  inferência para medi-lo.
- Não houve LLM, embeddings, retrieval real ou E2E. O próximo E2E manual deve
  usar `generation_mode=EBCG_V2` e destino
  `evaluation/results/model_benchmark_96_ebcg_v2_e2e_1/e2e_ebcg_v2_run_1.json`.
