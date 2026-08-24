# Fase 9.10 — Polarity & Contradiction Guard determinístico

## Problema e escopo

Os benchmarks 9.7–9.9 mostraram que uma atribuição correta não impede uma
claim de inverter a polaridade normativa da evidência (por exemplo, transformar
uma proibição em permissão). Esta fase adiciona uma barreira determinística e
fail-closed. Ela não substitui o Semantic Validator e não afirma que uma claim
é juridicamente verdadeira.

## Algoritmo

`consultation/polarity.py` recebe a claim e somente os `EvidenceItems` citados
no mesmo `EvidenceSet`. O texto do snapshot e, quando presente, o
`parent_context` são normalizados apenas para análise (Unicode, caixa e flexões
por prefixo curto). Pequenos reconhecedores identificam sinais explícitos de:

- proibição/negação;
- obrigação;
- facultatividade;
- permissão;
- exceção.

Uma inversão só é marcada quando há sinais opostos e sobreposição textual de
alvo entre claim e evidência. Ausência de sinal, falta de alvo comum e omissão
de exceção não são convertidas em proibição inferida: retornam `UNRESOLVED`.

Os resultados são `CONSISTENT`, `CONTRADICTED` ou `UNRESOLVED`, com códigos de
evidência e diagnóstico preservados. `CONSISTENT` significa somente que não foi
detectada inversão explícita; a validação semântica continua obrigatória.

## Gate isolado

Foram adicionados fixtures para proibição, permissão, obrigação,
facultatividade, exceção, paráfrase, contexto pai e ambiguidade. As inversões
explícitas foram reexecutadas cinco vezes e produziram sempre
`CONTRADICTED`; as paráfrases fiéis foram aceitas; o caso ambíguo permaneceu
`UNRESOLVED`. Nenhum caso adversarial foi aceito.

## Integração

Após a validação estrutural de citações e antes do Semantic Validator, cada
resposta não abstida passa pelo guard. Uma claim `CONTRADICTED` ou
`UNRESOLVED` faz a tentativa falhar e mantém a política de abstention do
serviço. O guard não persiste claims rejeitadas e não cria IDs, consulta corpus,
usa LLM ou altera retrieval, attribution, thresholds, embeddings ou schema.

## Limitações e segurança

O componente reconhece apenas contradições linguísticas explícitas e pode não
resolver escopo, exceções implícitas, dupla negação ou relações jurídicas que
exijam interpretação. Isso é intencional: falsos positivos são evitados pela
saída `UNRESOLVED`, que é tratada de forma fechada. A ausência de contradição
não autoriza resposta sem o Citation Validator e o Semantic Validator.

## Resultado

`POLARITY_GUARD_GATE: APPROVED` para o gate isolado e integração habilitada.
Os benchmarks de modelos e o Real-World Release Gate não foram reexecutados
nesta fase; portanto o gate de release permanece `NOT_REEVALUATED`.
