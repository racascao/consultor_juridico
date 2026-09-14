# Experimentos de modelos

Gold Evidence isolou o answerer do retrieval: todos os candidatos receberam as
mesmas evidências. Foram avaliados correção jurídica, groundedness, completude,
contrato, citações, prudência e estabilidade.

- Qwen3 4B e Qwen3.5 9B aplicaram fatos prematuramente;
- Phi-4 Mini apresentou inversão de polaridade e baixa completude;
- Gemma3 4B combinou envelope frágil e risco decisório;
- Gemma4 12B foi materialmente superior, mas falhou inicialmente no envelope.

O experimento `format=json` mudou uma única variável e eliminou o bloqueio
operacional do Gemma4 sem regressão material observada. Veja a
[tabela e o freeze](../reference/model-selection.md).

Falha de schema não é equivalente a resposta juridicamente errada, mas ambas
impedem aceitação automática. Essa separação evitou escolher o modelo apenas por
um score agregado.
