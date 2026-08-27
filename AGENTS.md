# AGENTS.md — Consultor Jurídico

## Objetivo

Implementar um mecanismo de consulta jurídica baseado em legislação oficial, versionada, rastreável e com respostas fundamentadas em fontes primárias.

O MVP 1 cobre exclusivamente a Constituição Federal de 1988 e o ADCT.

## Regras obrigatórias

1. O sistema é CLI-first.
2. Não implementar Frontend no MVP 1.
3. Não implementar API HTTP no MVP 1.
4. Todo o ambiente deve ser containerizado com Docker.
5. PostgreSQL + pgvector é o armazenamento principal.
6. Ollama é o runtime inicial do LLM local.
7. A CLI não contém regras de negócio.
8. A fonte jurídica primária é a autoridade documental.
9. O LLM nunca é fonte de verdade.
10. Respostas jurídicas devem possuir evidências rastreáveis.
11. O documento bruto nunca deve ser sobrescrito.
12. Parsing estrutural deve ser determinístico sempre que possível.
13. A ingestão deve ser idempotente.
14. Não adicionar infraestrutura sem necessidade.
15. Não adicionar dependências sem justificativa técnica.
16. Não implementar funcionalidades de MVPs posteriores sem autorização.
17. Alterações arquiteturais devem ser registradas em ADR.

## Princípios jurídicos

- Não inventar dispositivos.
- Não inventar citações.
- Preservar artigo, parágrafo, inciso e alínea quando identificáveis.
- Preservar URL e metadados da fonte.
- Diferenciar texto bruto, normalizado e usado em embeddings.
- Se não houver evidência suficiente, declarar insuficiência.

## Processo

Antes de implementar:

1. consultar `docs/`;
2. consultar `TASKS.md`;
3. consultar ADRs;
4. implementar a menor mudança necessária;
5. criar/atualizar testes;
6. executar lint e testes;
7. atualizar documentação quando o comportamento mudar.

## Não introduzir no MVP 1

React, Vue, Angular, FastAPI, Redis, Celery, Kafka, Elasticsearch/OpenSearch, Kubernetes, autenticação, multi-tenancy, cloud LLM, agentes autônomos, jurisprudência ou doutrina.

## Referência

A documentação do Dundie é referência estrutural para CLI, containers, banco, migrations e testes:

https://rochacbruno.github.io/dundie-api/06_estrutura.html

Ela deve ser adaptada, não copiada literalmente.


## Invariantes adicionais da revisão v2

- Evidence Builder, Evidence Validator e Citation Validator são componentes explícitos da arquitetura.
- Toda resposta deve possuir cadeia `claim → evidence → legal_element → legal_version → source_document → official_source`.
- Se a cadeia não puder ser validada, a resposta não é apresentada como fundamentada.
- Todas as dependências Python devem ser isoladas no ambiente virtual `.venv` do projeto. Nenhuma dependência Python deve ser instalada globalmente no sistema operacional do desenvolvedor.

## Invariantes permanentes da v0.2

- O desenvolvimento da v0.2 ocorre na branch `mvp-v0.2`; a tag v0.1.0 permanece
  congelada.
- A nova implementação segue Clean Architecture e SOLID, com domínio
  independente de frameworks e integrações externas.
- LangGraph coordena somente estado, rotas, retries e interrupções; regras de
  negócio pertencem aos componentes apropriados.
- Decisões de workflow são tipos explícitos, não coleções de flags booleanas.
- Não criar God Service, God Graph ou condicionais de negócio profundamente
  aninhadas.
- Dependências externas entram por ports e dependency injection; não usar
  estado global para adapters.
- Não criar regras específicas para perguntas, artigos ou casos de benchmark.
- Não realizar fine-tuning no MVP1 e não executar LLM real durante fases que o
  proíbam expressamente.
- Cada fase corresponde a um commit manual do usuário. O assistente não cria
  commits, e mensagens Git devem ser escritas em português.
- Atualizar o README após cada fase que altere arquitetura ou comportamento.
- Nunca executar `uv run ruff format .`; formatar somente arquivos tocados e
  sempre validar com `uv run ruff format --check .`.
