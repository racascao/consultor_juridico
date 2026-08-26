# Fase 91.6 — Structural Retrieval Expansion Safety Gate

Foi criado um transformer offline e determinístico para promover apenas filhos
normativos diretos de `SECTION` ou `SUBSECTION` efetivamente recuperados. A
expansão exige mesma fonte e versão, `CURRENT` + `NORMATIVE`, não atravessa a
árvore recursivamente, limita oito filhos por container e usa score separado
(`parent_rrf * 0.85`). Ranks lexical/vector originais nunca são fabricados.

Os controles positivos e negativos do componente passaram. O caso congelado de
estado de sítio confirma o container estrutural e o replay contrafactual
registrado anteriormente recupera o alvo em rank 1. Contudo, o artefato E2E não
contém o corpus relacional completo (parent IDs e filhos), e o PostgreSQL local
não estava disponível para reexecutar o replay de dez casos, seleção e aborto.

Por isso a expansão permanece isolada e o gate é `INCONCLUSIVE`; não houve
integração no retrieval, nova embedding, E2E, LLM, ingestão ou persistência.
