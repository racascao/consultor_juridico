# Consultor Jurídico

Aplicação CLI-first de consulta à Constituição Federal de 1988 e ao ADCT,
baseada em fonte oficial, execução local e rastreabilidade. A branch
`mvp-v0.2` contém o MVP2 em `0.2.0.dev0`; a versão 0.1.0 permanece preservada
em sua tag histórica.

> O LLM não é fonte jurídica. Se a evidência oficial não for suficiente, o
> sistema se abstém.

## Estado do MVP2

- **MVP2-F1 — Fundação Arquitetural:** completa.
- **MVP2-F2 — Core Funcional:** implementação completa, aguardando aceitação
  manual com os modelos locais. O primeiro reteste do retrieval não produziu
  ganho material; a projeção contextual v2 foi implementada a partir da
  auditoria causal. A rematerialização explícita a partir da captura persistida
  está pronta, mas o rebuild/reteste real permanece manual. Retrieval e
  latência ainda não atendem ao release.
- **MVP2-F3 — Validação e Release:** futura.

O MVP2 não utiliza `EBCG_V2`, guards ou fallback de consulta da v0.1. Seu core
é uma implementação menor, orientada primeiro à localização e relevância da
evidência.

## Arquitetura

```text
Fonte oficial
  -> SourceSnapshot imutável
  -> LegalAct / ActVersion
  -> Provision
  -> SearchUnit contextual
  -> PostgreSQL FTS + pgvector (exact cosine)
  -> RRF
  -> Consultation Model
       ANSWER -> Citation Validator determinístico
       CLARIFY -> clarificação -> novo retrieval
       ABSTAIN -> abstenção
  -> resposta fundamentada ou abstenção
```

As `SearchUnit`s são `DOCUMENT_METADATA`, `ARTICLE` ou
`CONTEXTUAL_PROVISION`. A projeção contextual v2 inclui o CAPUT regente nos
descendentes, rotula fatos documentais de modo determinístico e não indexa um
CAPUT separado quando sua projeção é exatamente igual à do ARTICLE. O ARTICLE
continua completo para preservar perguntas amplas e listas normativas.
`search_text` reúne somente contexto oficial derivado deterministicamente;
`citation_text` preserva sem alteração o texto citável do dispositivo.
As embeddings persistentes usam `nomic-embed-text`, 768 dimensões e prefixos de
documento/query centralizados no adapter. A busca híbrida combina FTS em
português (`websearch_to_tsquery`) e cosine exato com RRF (`k=60`), sem boosts
por pergunta ou artigo. Cada modalidade busca um pool interno de 30 unidades;
depois da fusão, uma passagem determinística preserva primeiro a unidade mais
bem ranqueada de cada família de artigo e só então preenche o top-10 restante.

### LangGraph e inferência única para CPU

LangGraph coordena estado, rotas, limites e `interrupt/resume`. Ele não contém
SQL, retrieval, HTTP, regras jurídicas ou acesso direto ao Ollama.

O `Consultation Model` recebe pergunta e candidatas e retorna uma das variantes
tipadas `ANSWER`, `CLARIFY` ou `ABSTAIN`. Em `ANSWER`, a cadeia de citação é
validada deterministicamente; não há segundo Judge, rewrite ou retry automático.

Uma pergunta como “Alistamento é obrigatório?” pode gerar clarificação entre
alistamento eleitoral e serviço militar. A resposta do usuário é incorporada à
pergunta resolvida e o retrieval é obrigatoriamente executado novamente.

Uma pergunta direta usa no máximo uma inferência de chat. O modelo padrão é
`ministral-3:3b`, com temperatura zero, schema discriminado e falha fechada.
Uma nova inferência só ocorre após entrada humana em uma clarificação. Não há
fine-tuning.

### Rastreabilidade

Para conteúdo normativo:

```text
Answer -> Evidence ID -> SearchUnit -> Provision
       -> ActVersion -> SourceSnapshot -> Source
```

Para metadata documental, a cadeia omite `Provision`. IDs como `E1` são locais
à requisição; referências como `CF88/ARTICLE:14` são estáveis. O
`CitationValidator` confirma deterministamente que a evidência foi selecionada
e possui referência, snapshot e fonte oficial rastreáveis.

### Aquisição e rematerialização da fonte

`SourceSnapshot` é a captura física imutável da fonte oficial: seus bytes e
SHA-256 são preservados no PostgreSQL. Aquisição e materialização são operações
distintas. A aquisição HTTP cria uma nova captura; a rematerialização lê uma
captura já persistida, valida novamente seu SHA-256 e aplica o parser/projeção
atual sem acessar o Planalto. Isso permite comparar projeções diferentes sobre
exatamente a mesma fonte documental.

## Stack e escopo

- Python 3.13, uv, Typer, Rich, Pydantic e LangGraph;
- PostgreSQL 16 + pgvector, SQLAlchemy e Alembic;
- Beautiful Soup e parser determinístico para CF/88 + ADCT;
- Ollama local com `nomic-embed-text` e `ministral-3:3b` para consulta;
- Docker Compose.

Não fazem parte deste MVP: API HTTP, frontend, jurisprudência, doutrina,
legislação infraconstitucional, fine-tuning ou persistência de consultas.
Clarificações usam `InMemorySaver` e são perdidas ao encerrar o processo.

## Início rápido

```bash
git clone <repo>
cd consultor_juridico
cp .env.example .env
docker compose up -d --build
docker compose run --rm app bash
```

Dentro do container:

```bash
consultor-juridico
```

O bootstrap aplica migrations e prepara corpus e embeddings de modo
idempotente, usando o PostgreSQL como fonte de estado. O primeiro acesso exige
internet e pode demorar por causa da captura oficial e dos modelos; os acessos
seguintes atualizam somente o que estiver ausente ou obsoleto.

Builds concorrentes ou interrompidos podem ser repetidos sem limpar o banco:
Source, snapshot e identidades jurídicas compatíveis são reutilizados por suas
chaves naturais, enquanto conflitos reais interrompem o processo com diagnóstico.
A MVP2-F2 continua em aceitação manual; a MVP2-F3 ainda não foi iniciada.

O `docker compose up -d --build` prepara DB, Ollama e a imagem da aplicação,
mas não inicia uma segunda indexação em background. O bootstrap pertence ao
container efêmero aberto por `docker compose run --rm app bash`. Na primeira
indexação em CPU, o progresso é exibido periodicamente; embeddings são salvas
em lotes e uma nova execução retoma somente itens ausentes ou obsoletos.

Configuração principal:

```dotenv
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_CONSULTATION_MODEL=ministral-3:3b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_TIMEOUT=180
EMBEDDING_DIMENSIONS=768
RETRIEVAL_LIMIT=10
```

## Operações avançadas

```bash
consultor-juridico db status
consultor-juridico corpus status
consultor-juridico corpus construir
consultor-juridico corpus rematerializar --snapshot-sha <sha256>
consultor-juridico indice construir
consultor-juridico retrieval rastrear "O voto é facultativo?"
consultor-juridico eval retrieval \
  --dataset evaluation/datasets/basic_direct_v1.json \
  --output evaluation/results/mvp2_retrieval_baseline.json
```

`corpus rematerializar` é uma operação avançada e explícita: ela nunca faz
fallback para HTTP nem altera o `SourceSnapshot`. Snapshot ausente ou payload
incompatível com o hash encerram a operação antes do parser.

O dataset funcional `basic_direct_v1` possui 18 perguntas. Seus targets devem
ser alterados somente em uma nova versão. A medição real inicial obteve
Hit@1 `0,333`, Hit@3 `0,444`, Hit@10 `0,500` e MRR `0,391`; o baseline de
retrieval está reprovado. A geração de candidatas foi corrigida para evitar
truncamento antes do RRF e desperdício do top-10 por famílias repetidas, mas o
reteste não mostrou ganho material. O rebuild e o benchmark da projeção
contextual v2 permanecem pendentes do usuário. Quatro consultas iniciais
resultaram em abstenção e
levaram aproximadamente 2–3 minutos cada em CPU, latência ainda inaceitável
para release.

Para diagnosticar uma consulta sem expor prompts nem raciocínio oculto:

```bash
consultor-juridico consultar "Alistamento militar é obrigatório?" --verbose
```

O modo verbose mostra rota do LangGraph, tempos e contagens por nó, decisões
estruturadas, IDs selecionados, tamanhos aproximados das entradas, chamadas ao
Ollama e a causa técnica de eventual abstenção. Ele não altera a decisão nem o
comportamento público seguro do pipeline.

Os diagnósticos mostraram que o workflow anterior consumia cerca de 155 s no
Relevance Judge 8B e 71 s no 3B, além de recusar uma evidência correta em rank
1. Esse pipeline multi-LLM foi removido. O contrato atual usa variantes
discriminadas e IDs request-scoped para `ANSWER`, `CLARIFY` e `ABSTAIN`; o modo
verbose mostra modelo, métricas nativas, total de chamadas e falhas sanitizadas
do provider sem expor prompts. O workflow simplificado e o retrieval revisado
aguardam reteste manual da MVP2-F2; a consulta direta continua usando uma única
inferência LLM.

## Banco local anterior

A baseline `001_v02_initial_schema` é deliberadamente incompatível com bancos
v0.1. A migration recusa a revision antiga sem apagar dados. Somente o usuário,
se quiser descartar seus volumes locais, deve executar:

```bash
docker compose down -v
```

Esse comando é destrutivo e nunca é executado automaticamente.

## Desenvolvimento

```bash
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
git diff --check
docker compose config
```

Testes de adapters usam HTTP mockado. A avaliação real de embeddings e as
cinco consultas manuais obrigatórias ficam a cargo do usuário; a implementação
não anuncia qualidade ainda não medida.

Documentação ativa: [arquitetura](docs/v0.2/architecture.md),
[plano](docs/v0.2/implementation-plan.md),
[fonte e rastreabilidade](docs/v0.2/source-and-traceability.md) e
[avaliação](docs/v0.2/evaluation.md).
