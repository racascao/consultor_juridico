# Consultor Jurídico

O Consultor Jurídico é um RAG local e auditável para consulta normativa sobre
a Lei Federal nº 9.784/1999. O MVP2 combina PostgreSQL FTS, evidências com
proveniência, Gemma4:12b, validação de citações e uma CLI Rich com `QueryMode`
explícito.

!!! info "MVP2 — versão congelada"
    Esta documentação descreve a tag oficial `0.2.0`. Ela foi adicionada à
    `main` depois do freeze, sem alterar o produto congelado. Evoluções
    funcionais pertencem ao MVP3 ou a uma versão posterior.

## Quero aprender a construir

Siga o [curso](course/index.md) para reconstruir o MVP2 pelo caminho recomendado,
sem repetir a cronologia experimental.

## Quero entender como funciona

Consulte a [referência de arquitetura](reference/architecture.md), o
[runtime](reference/runtime.md), a [CLI](reference/cli.md) e o
[modelo de dados](reference/data-model.md).

## Quero entender as decisões

Leia os [experimentos](experiments/index.md) para conhecer hipóteses, resultados,
alternativas rejeitadas e condições para reconsiderá-las.

## Escopo em uma frase

```text
Lei 9.784/1999 versionada → PostgreSQL FTS → evidência estrutural
→ Gemma4:12b local → JSON estrito → citações validadas
```

O modelo de linguagem nunca é tratado como fonte jurídica. Consultas comuns
não acessam a web; apenas o bootstrap pode obter o snapshot oficial ausente.
