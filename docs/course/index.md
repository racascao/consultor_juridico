# Curso — reconstruindo o MVP2

Este curso ensina a construir, a partir de um diretório vazio, um sistema
funcionalmente equivalente ao Consultor Jurídico MVP2 congelado na tag `0.2.0`.
O público-alvo conhece Python, terminal, Docker e SQL em nível básico; os
conceitos específicos de SQLAlchemy, Alembic, FTS, RAG, Typer e Ollama são
introduzidos quando passam a ser necessários.

## A arquitetura que será construída

Este não é apenas um exercício de conectar chunking, busca e LLM. O resultado
é um **RAG jurídico estruturado e auditável**: a fonte oficial é preservada e
versionada, a lei é materializada como hierarquia normativa, retrieval produz
candidatos e uma etapa separada os transforma em evidências autorizadas. O
answerer recebe esse conjunto explícito, responde sob contrato estruturado e
suas citações são verificadas antes da entrega.

```text
RAG tradicional
documento → chunks → retrieval → LLM → resposta

MVP2 deste curso
fonte oficial → versão → provisions hierárquicas → SearchUnits → retrieval
→ expansão estrutural → Evidence Assembly → EvidenceSet → answerer estruturado
→ Citation Validation → resultado auditável
```

Ao longo dos capítulos, essa separação permite observar onde termina a busca e
onde começa a evidência, preservar proveniência e testar contrato técnico
separadamente de qualidade jurídica. Ela reduz graus de liberdade do modelo,
mas não garante correção nem completude.

## O que você construirá

```text
Planalto → snapshot imutável → parser jurídico → provisions hierárquicas
         → SearchUnits → PostgreSQL FTS → expansão estrutural
         → Evidence Assembly → EvidenceSet/EvidenceItems
         → Gemma4:12b → JSON estrito
         → Citation Validation → CLI Rich
```

O corpus é a Lei Federal nº 9.784/1999. Consultas normativas seguem o pipeline
RAG; situações concretas recebem uma clarificação determinística sem chamar o
modelo.

## Como usar o curso

Comece no capítulo 1 e avance somente depois do checkpoint. Cada capítulo
declara o estado anterior, os arquivos criados ou alterados, contratos, código,
testes e comandos. Os paths correspondem ao projeto real.

Os snippets identificados como **recorte literal** foram extraídos da tag
`0.2.0`. Os identificados como **recorte didático** removem detalhes periféricos,
mas preservam o contrato. Arquivos pequenos apresentados como completos podem
ser usados diretamente; recortes devem ser integrados no módulo indicado.

## Sequência incremental

| Capítulo | Incremento verificável |
|---|---|
| 01 | pacote importável, CLI e testes |
| 02 | PostgreSQL, Ollama e imagem da aplicação |
| 03 | schema e migrations |
| 04 | snapshot oficial versionado |
| 05 | árvore de provisions auditável |
| 06 | SearchUnits persistidas |
| 07 | retrieval PostgreSQL FTS |
| 08 | evidências com filhos estruturais |
| 09 | chamada local ao answerer |
| 10 | contrato JSON tipado |
| 11 | citações determinísticas |
| 12 | modos de consulta seguros |
| 13 | bootstrap e produto CLI |
| 14 | avaliação reproduzível |
| 15 | freeze, HOLDOUT e release |

## Curso, Referência e Experimentos

- **Curso:** vamos criar e integrar cada componente.
- **[Referência](../reference/architecture.md):** fotografia compacta do
  sistema final.
- **[Experimentos](../experiments/index.md):** evidência histórica das escolhas.

O curso apresenta o caminho recomendado conhecido hoje, não a cronologia das
tentativas. Nenhum caso privado do Blind HOLDOUT é reproduzido.

## Ambiente esperado

Tenha Python 3.13, `uv`, Git, Docker e Docker Compose. Os comandos partem da
raiz criada assim:

```bash
mkdir consultor_juridico
cd consultor_juridico
```

Siga para [01. Bootstrap do projeto](01-project-bootstrap.md).
