# Fase 98 — Auditoria de contrato EBCG-v2

## Método e imutabilidade

A auditoria leu somente o artefato E2E, o dataset e, opcionalmente, a árvore
normativa por consultas SQLAlchemy de leitura. Não executou Ollama, embeddings,
retrieval, geração ou validators.

| Entrada | SHA-256 |
| --- | --- |
| Artefato E2E | `0e27a539ce623ac38221fb55fd5f830666682c1227269ee0b67358311bfca268` |
| Dataset v1 | `c6b496d20dd9b7b5952f7abecca92e64c0179ce134794f5e3b39e579025f441f` |

Os hashes foram idênticos antes e depois. A taxonomia do auditor separa
`PASS`, `EXPECTED_ABSTENTION`, `RETRIEVAL_MISS`,
`STRUCTURAL_CONTEXT_REQUIRED_FOR_VALIDATION`, `DATASET_TARGET_ERROR`,
`QUERY_AMBIGUITY`, `ACCEPTABLE_TARGETS_INCOMPLETE` e demais categorias
congeladas da Fase 98. `WRONG_TARGET` histórico não foi redefinido.

## Casos

| Caso | Histórico | Atribuição | Evidência |
| --- | --- | --- | --- |
| pena de morte | CORRECT_ANSWER | PASS | Locator aceitou a remissão interna corretamente. |
| prisão perpétua | FALSE_ABSTENTION | STRUCTURAL_CONTEXT_REQUIRED_FOR_VALIDATION | EV002 era o target; a negação está no pai. |
| liberdade religiosa | CORRECT_ANSWER | PASS | Target válido. |
| racismo | WRONG_TARGET | QUERY_AMBIGUITY | Art. 4º VIII e Art. 5º XLII têm cobertura integral. |
| extradição | CORRECT_ANSWER | PASS | Target válido. |
| direito à vida | CORRECT_ANSWER | PASS | Target válido. |
| liberdade de expressão | CORRECT_ANSWER | PASS | Target aceitável citado. |
| idade para ser presidente | CORRECT_ANSWER | PASS | Target válido. |
| voto obrigatório | WRONG_TARGET | DATASET_TARGET_ERROR | A alínea esperada não existe; o inciso contém o texto. |
| estado de sítio | WRONG_TARGET | RETRIEVAL_MISS | Art. 137 não ocorreu no retrieval medido. |
| aborto | CORRECT_ABSTENTION | EXPECTED_ABSTENTION | Controle negativo preservado. |

## Diagnóstico

`prisão perpétua` tem Core Evidence correta e claim atribuída, mas foi
bloqueada em Polarity por não haver no snapshot a negação estrutural do pai.
O estágio registrado como `GENERATOR_ABSTENTION` é taxonomicamente incorreto;
a recomendação futura é `POLARITY_VALIDATION`, sem alterar o artefato atual.

`racismo` exige revisão humana do contrato: a pergunta curta não desambigua
entre repúdio como princípio internacional e a regra penal constitucional. A
proposta é explicitar a intenção ou acrescentar target aceitável em dataset v2.

`voto obrigatório` possui erro estrutural objetivo: o target
`.../INCISO:I/ALINEA:A` está ausente na árvore, mas o `INCISO:I` existe e
contém “obrigatórios para os maiores de dezoito anos”.

`estado de sítio` continua `RETRIEVAL_MISS` genuíno: Art. 137 é válido e não
foi recuperado; Art. 21 V é relacionado, mas não satisfaz o contrato atual.

## Resultado

Core Evidence atingiu target em `7/10` respondíveis: seis respostas estritas e
prisão perpétua, bloqueada após construção. Há dois problemas de contrato
(racismo e voto), um miss de retrieval e uma limitação de contexto estrutural.
As duas propostas estão em
`evaluation/results/model_benchmark_98/benchmark_contract_proposals.json` e
não foram aplicadas. O cenário projetado se aceitas é `8/10`; o oficial segue
`6/10`, com `1/1` abstenção correta e `unsafe=0`.

`BENCHMARK_V2_NEEDED=YES`: qualquer mudança requer fase própria, novo SHA e
changelog. EBCG-v2, Retrieval, Selection, Sufficiency, Attribution, Locator,
Citation, Polarity e Semantic Judge não foram alterados. O gate de retrieval
permanece `0,900 < 0,905` e qualifier preservation segue não medido.
