# MVP2 — Restart

```text
STATUS: REDESIGN_PENDING
ABANDONED_MVP2_ATTEMPT_HEAD: c434845ce56802d117cda20b182852d5df6643db
BASELINE: v0.1.0
```

A primeira tentativa do MVP2 foi abandonada porque a complexidade e os
experimentos realizados não produziram qualidade prática satisfatória. Nenhum
de seus componentes é considerado decisão arquitetural para o novo MVP2.

A restauração de `v0.1.0` fornece somente um checkpoint técnico conhecido. Ela
não adota automaticamente a arquitetura do MVP1 para o novo ciclo. O banco
persistido da tentativa abandonada também não é baseline válido: sua eventual
reutilização, migração ou substituição será decidida separadamente após o
redesign.

## Charter de produto

O novo MVP2 deverá futuramente buscar:

1. responder perguntas constitucionais naturais;
2. recuperar evidência juridicamente relevante de forma geral;
3. usar fontes oficiais e rastreáveis;
4. funcionar localmente;
5. ser viável em CPU;
6. evitar regras específicas por pergunta ou artigo;
7. generalizar para perguntas não vistas durante o desenvolvimento;
8. distinguir resposta correta, abstenção correta e falsa abstenção;
9. evitar resposta jurídica errada ou sem suporte;
10. permanecer arquiteturalmente simples.

Este documento não define workflow, retrieval, banco, schema, chunking,
embedding, modelo, prompt, validator, dataset, threshold nem fases. Essas
decisões pertencem à próxima etapa de redesign orientada pelos objetivos do
produto.
