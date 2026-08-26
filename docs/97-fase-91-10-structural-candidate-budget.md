# Fase 91.10 — Structural Candidate Budget & Evidence Selection

Foi criado um transformador puro de reserve estrutural. Ele preserva o top-K
primário, adiciona somente candidatos com provenance `STRUCTURAL_EXPANSION`,
deduplica por identidade e ordena por score estrutural seguido de identidade.

As políticas suportadas para replay são baseline, reserve 1 e reserve 2. O
replay completo de dataset, aborto e controles adversariais não foi executado
nesta etapa; portanto não houve integração ao retrieval nem alteração da
Evidence Selection.
