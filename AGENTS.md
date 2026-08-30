# AGENTS.md — Consultor Jurídico

## Objetivo

Construir um mecanismo de consulta jurídica baseado em fontes oficiais,
versionadas e rastreáveis, sem tratar modelos de linguagem como fonte jurídica.
O novo MVP2 está em redesign e ainda não possui arquitetura ou fases definidas.

## Invariantes gerais

- A tag `v0.1.0` é imutável.
- Dependências Python devem permanecer na `.venv` local e ser gerenciadas com
  `uv`; nada deve ser instalado globalmente.
- O assistente não cria commits. Cada fase futura corresponde a um commit manual
  do usuário, quando as fases forem novamente definidas.
- Mensagens Git sugeridas devem ser escritas em português.
- Nunca executar `uv run ruff format .`; formatar somente arquivos tocados e
  validar sempre com `uv run ruff format --check .`.
- Aplicar Clean Code, SOLID e dependency inversion; evitar God Services, estado
  global e condicionais de negócio profundamente aninhadas.
- Não criar regras runtime específicas para pergunta, artigo, dispositivo,
  dataset ou caso de benchmark.
- Adicionar complexidade apenas diante de falha concreta e reproduzível, com a
  camada responsável identificada e regressão que cubra a falha.
- Inferências LLM reais e benchmarks longos são executados manualmente pelo
  usuário.
- Durante uma medição, não alterar silenciosamente dataset, modelo, prompt,
  threshold ou variável experimental.
- Atualizar o README em toda implementação futura que altere arquitetura ou
  comportamento.
- Preservar fontes oficiais, proveniência e conteúdo bruto; se a evidência for
  insuficiente, declarar insuficiência em vez de inventar resposta ou citação.

## Processo

Antes de implementar:

1. consultar `README.md`, `TASKS.md`, `docs/` e ADRs aplicáveis;
2. confirmar escopo, critérios de aceite e estado do working tree;
3. implementar a menor mudança necessária;
4. criar ou atualizar regressões;
5. executar lint e testes proporcionais ao risco;
6. atualizar a documentação quando o comportamento mudar.

Nenhum componente do MVP1 ou da primeira tentativa do MVP2 é automaticamente
uma decisão arquitetural do novo MVP2.
