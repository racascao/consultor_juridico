# Fase 99 — Benchmark v2 Freeze

`real_world_short_v1` permanece congelado (`c6b496d…f441f`). O v2
(`a6ef0c…10a89`) altera exclusivamente `rw-racismo` e
`rw-voto-obrigatorio`: Art. 4º VIII tornou-se aceitável para a consulta curta
de racismo e a alínea inexistente foi substituída pelo `INCISO:I` materializado.

O diff offline confirmou 11 casos, mesma ordem e nenhuma mudança inesperada.
O reassessment do artefato EBCG-v2 já existente, que não é novo E2E, resulta
em `8/10`, uma abstenção correta, uma falsa abstenção, um wrong target e zero
unsafe. Hit@10 projetado permanece `0,900 < 0,905`.

Para novos runs, o serviço transporta `validation_stage` estruturado: falha de
Polarity passa a `POLARITY_VALIDATION`, não `GENERATOR_ABSTENTION`. Artefatos
históricos não foram reescritos. Prisão perpétua continua limitação real de
contexto estrutural; estado de sítio continua retrieval miss. Não houve LLM ou
E2E nesta fase.
