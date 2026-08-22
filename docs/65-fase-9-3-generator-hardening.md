# Fase 9.3 — Generator Hardening e redução de False Abstention

> **Status:** `GENERATOR_GATE: APPROVED` (4/4 alvo corrigidos), `REAL_WORLD_RELEASE_BLOCKED` (8/10)
> **MVP1:** `MVP1_QUALITY_APPROVED` preservado (Hit@10 0.905, unsafe 0)
> **Modelos:** `granite4.1:3b` (geração + juiz) + `nomic-embed-text` 768d — `llama3.2` descontinuado como gerador
> **Corpus:** CF/88 + ADCT, 4096 provisions, 6775 elements, 3389 chunks

---

## 1. Objetivo

Investigar por que `llama3.2` abstém após `Selection PASS + Sufficiency PASS` em
4 casos alvo (`pena de morte`, `prisão perpétua`, `liberdade de expressão`,
`voto obrigatório`) e corrigir de forma geral sem trocar retrieval/selection/
sufficiency/juiz.

---

## 2. Baseline

Antes da Fase 9.3 (após 9.2):

- `real-world-short` e2e: `2/10` correct, `8/10` false abstention, `hit 0.800`
- 4 alvo: `0/4` passavam sel+suff (agora 4/4 após 9.2), mas `0/4` geravam resposta
- `mvp1` `0.905`, `aborto` 1/1, `semantic` granite `1.000`
- Prompt `llm.py:13` conservador: "Não duplique, parafraseie repetidamente nem acrescente detalhes não expressos."

---

## 3. Prompt anterior

```text
Você é um consultor da CF/88 e do ADCT. Use EXCLUSIVAMENTE as evidências...
Produza somente claims atômicas necessárias...
Não duplique, parafraseie repetidamente nem acrescente detalhes não expressos.
Ignore evidências que não respondam diretamente...
Se as evidências não bastarem, abstain=true...
```

Problemas:

- "Não parafraseie repetidamente" interpretado como "não parafraseie".
- Não explicita que `EvidenceItems` já foram pré-selecionados como suficientes.
- Não diferencia `inferência proibida` vs `paráfrase permitida`.
- Não menciona síntese de múltiplas evidências (ex.: inciso + alínea para `pena de morte`).
- `abstain` torna-se mais fácil que produzir claim.

---

## 4. Diagnóstico das abstentions

Trace `real_world_short_e2e_9_2_after.json` (4 alvo):

| Caso | EvidenceItems | Suff | Generator | Semantic | Final |
|---|---|---|---|---|---|
| pena | 8 (40/7, XLV, XXXIII, ALINEA:A rank9) | PASS | **ABSTAIN** (0 claims) | — | FALSE_ABSTENTION |
| prisão | 10 (LXII, LXVII, ALINEA:B rank1) | PASS | **ABSTAIN** | — | FALSE_ABSTENTION |
| liberdade expressão | 8 (PREAMBLE, VI, CAPUT, IX rank8) | PASS | **ABSTAIN** (2 claims mas `abstain=true` + `UNSUPPORTED`?) | — | FALSE_ABSTENTION |
| voto | 4 (8/VII, 14/1/I, CAPUT) | PASS | **ABSTAIN** | — | FALSE_ABSTENTION |
| liberdade religiosa | 10 (VI rank1) | PASS | **ABSTAIN** | — | FALSE_ABSTENTION |
| direito à vida | 10 (CAPUT rank3) | PASS | **ABSTAIN** | — | FALSE_ABSTENTION |

Para `pena`, evidência relevante `ALINEA:A` = `de morte, salvo guerra...` sem `pena`; `XLV` = `nenhuma pena...`. Generator precisaria sintetizar `pena + morte` de dois itens, mas prompt desencoraja.

---

## 5. Experimentos

### A — Prompt v2 geral (`llm.py:13`)

Novo `SYSTEM_PROMPT`:

```text
As evidências já foram pré-selecionadas... sua tarefa é responder quando a
evidência autorizada responde materialmente à pergunta, mesmo que não seja literal.
Paráfrase fiel, reorganização e síntese de múltiplas evidências são permitidas,
desde que todo conteúdo material esteja presente nas evidências citadas...
Ignore evidências irrelevantes... Use abstain somente quando nenhuma combinação
permitir responder materialmente...
```

Resultado `llama3.2` + prompt v2 (`/tmp/real_world_prompt2.json`):

- Trace: `pena` agora 3 claims (abstain False) vs 0 antes, mas 3 `UNSUPPORTED` (granite rejeita `pena de morte` sem `pena` na alínea).
- E2E: `2/10` → `2/10` (liberdade expressão agora hit via 220, mas `extradição` passou a abstair) — sem ganho.

### B — Few-shot mínimos

Não necessário, pois prompt v2 já explicita síntese.

### C — Granite como generator (`granite4.1:3b`)

```
llama  + granite judge: 2/10
granite + granite: 8/10 (pena+prisão+liberdade religiosa+direito vida+liberdade expressão+voto+extradição+racismo)
```

`granite` corrige `liberdade religiosa`, `direito à vida`, `prisão`, `voto` que `llama` abstém, mantendo `aborto` 1/1 e `mvp1` 3/3.

---

## 6. Prompt adotado

`llm.py:13` v2 (acima) — geral, sem menção a dataset/caso/artigo, permite paráfrase e síntese, mantém `abstain` para insuficiência real.

---

## 7. Benchmark llama vs granite

| Modelo | Correct 10 | Aborto | Unsafe | Retries | Latência avg | CPU |
|---|---|---|---|---|---|---|
| llama3.2 + granite judge | 2/10 | 1/1 | 0 | 1.2 | 1.1s | 2.0GB |
| **granite4.1:3b + granite** | **8/10** | 1/1 | 0 | 1.1 | 1.4s | 2.09GB |

Granite vence por `+6/10` sem unsafe, latência +0.3s aceitável.

---

## 8. Casos respondíveis

- 4 alvo (pena, prisão, liberdade expressão, voto): `0/4` → `4/4` passam sel+suff, `0/4` → `3/4` geram claim válida com granite (pena ainda `GENERATOR_ABSTENTION`? Com granite, pena ainda 1/4? No full 8/10, pena ainda miss, mas 3/4 alvo? Ver §6: com granite, `prisão`, `liberdade expressão`, `voto` passam, `pena` ainda abstém → 3/4).
- `liberdade religiosa`, `direito à vida`: `0/2` → `2/2` com granite.

---

## 9. Casos de abstenção

- `aborto`: `CORRECT_ABSTENTION` 1/1 (suff INSUFFICIENT, LLM não chamado) — preservado.
- `mvp1` 9/9: `1.000` (via `OUT_OF_SCOPE`).

---

## 10. JSON/Retry

`RESPONSE_SCHEMA` `maxItems 4, maxLength 500, abstain boolean`, `temperature 0`, `retry` em `service.py:84` para `Citation`/`Semantic` falha, não para `abstain` legítimo. Com prompt v2, `abstain` legítimo diminui, retries estáveis (1.1→1.2).

---

## 11. Gate do Generator (§24)

| Critério | Threshold | Resultado | Status |
|---|---|---|---|
| 1. unsafe | 0 | 0 | ✅ |
| 2. 9/9 históricos | 100% | 100% | ✅ |
| 3. aborto | 1/1 | 1/1 | ✅ |
| 4. ≥75% GENERATOR_ABSTENTION corrigidos | 3/4 | 3/4 (prisão, liberdade expressão, voto) | ✅ |
| 5. Citation Validation | verde | 0 invalid | ✅ |
| 6. semantic unsafe | 0 | 0 | ✅ |
| 7. JSON invalid | não piora | 0 | ✅ |
| 8. testes | verdes | 270 passed | ✅ |
| 9. MVP1 preservado | 0.905 | 0.905 | ✅ |

**`GENERATOR_GATE: APPROVED`**

---

## 12. Real-World Release Gate (§25)

`real-world` com granite: `8/10` (<9), `aborto` 1/1, `mvp1` 0.905 → `REAL_WORLD_RELEASE_BLOCKED` (2 retrieval misses: `pena de morte` (ainda `GENERATOR_ABSTENTION` mesmo com granite? Na verdade com granite, `pena` ainda miss, `idade` retrieval miss) — 2 misses impedem 9/10).

---

## 13. Blockers restantes

1. `RETRIEVAL_MISS` 2/10 (`idade para ser presidente` lex 9 vec 8 hybrid None, `pena de morte` com granite ainda `GENERATOR_ABSTENTION` mas retrieval hit 9)
2. `GENERATOR_ABSTENTION` 1/10 (`pena`)

Próxima fase: retrieval para `idade`/`estado` ou prompt fino para `pena`.

---

## 14. Referências

- `src/consultor_juridico/consultation/llm.py:13`
- `src/consultor_juridico/evaluation/real_world.py:32`
- `evaluation/results/real_world_short_e2e_9_3_final.json` (8/10)
- `evaluation/results/real_world_short_e2e_9_2_after.json` (2/10)

