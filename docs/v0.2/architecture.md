# Arquitetura do MVP2

## Ciclo de vida do índice vetorial

A construção do índice usa um advisory lock transacional PostgreSQL dedicado.
O processo que adquire o lock consulta novamente os embeddings válidos e gera
somente os documentos ausentes ou com `content_hash` obsoleto. A geração ocorre
em lotes pequenos, persistidos independentemente, permitindo retomada depois de
timeout sem repetir lotes concluídos. O adapter Ollama faz retry limitado apenas
para timeout e falhas de rede; contrato, HTTP e dimensão inválidos falham sem
retry.

No Compose, o serviço nominal `app` apenas confirma que a imagem CLI foi criada
e termina. O bootstrap automático é responsabilidade do container efêmero aberto
explicitamente pelo usuário, evitando duas indexações concorrentes no fluxo
oficial.

## Camadas

- **Domain:** valores e decisões imutáveis, sem frameworks.
- **Application:** casos de uso, ports, retrieval e workflow.
- **Infrastructure:** PostgreSQL, pgvector, Ollama e fonte Planalto.
- **CLI:** composition root e apresentação, sem regra de negócio.

### Boundary de fonte

Aquisição e materialização do corpus são casos distintos. O fetcher Planalto
produz uma `SourceCapture`; o materializador interpreta qualquer captura válida
recebida por seu port. Para reprojeção controlada, um reader SQLAlchemy
reconstrói a captura a partir do `SourceSnapshot` imutável e valida seu SHA-256
antes de chamar o mesmo materializador. Esse caminho não possui fetcher HTTP e
não faz fallback remoto.

```text
PlanaltoHttpSourceFetcher -> SourceCapture -> MaterializeCorpusUseCase
SourceSnapshotReader -----^                  (parser + corpus transacional)
```

O repositório reutiliza a transação e o advisory lock da materialização normal.
Assim, reprojeções concorrentes são serializadas, versões anteriores são
preservadas e uma versão parcial nunca se torna ativa.

## Pipeline

```text
Source -> SourceSnapshot -> LegalAct -> ActVersion -> Provision -> SearchUnit
SearchUnit -> FTS + pgvector -> RRF -> EvidenceCandidate
EvidenceCandidate -> Consultation Model
  ANSWER -> Citation Validator -> Answer
  CLARIFY -> interrupt -> clarification -> retrieval -> Consultation Model
  ABSTAIN -> abstention
```

FTS usa configuração portuguesa e `websearch_to_tsquery`. Vetores de 768
dimensões são persistidos por SearchUnit/modelo e consultados por cosine exato.
RRF usa `k=60`, sem pesos, boosts ou regras por dataset.

As modalidades recuperam pools internos de até três vezes o limite final
(`30` para o top-10 de produção). O RRF funde esses pools antes do corte. Uma
passagem determinística seleciona primeiro a SearchUnit mais bem ranqueada de
cada família de artigo; se ainda houver vagas, outra passagem reinsere as
demais na ordem híbrida. Metadata documental forma sua própria família. Essa
montagem não troca uma unidade contextual específica por uma unidade `ARTICLE`
e não altera scores, `k` ou o limite final.

LangGraph coordena apenas transições e o limite de duas clarificações; adapters
concretos são ligados somente no composition root. O runtime CPU-first usa uma
única inferência de consulta fundamentada por pergunta direta, com contrato
discriminado `ANSWER | CLARIFY | ABSTAIN`. Não existem retries semânticos,
rewrite ou retrieve-again automáticos.

Essa decisão decorre de medições reais: somente a classificação de relevância
levou cerca de 155 segundos no modelo 8B e 71 segundos no 3B, e ambos recusaram
o caso militar embora o target estivesse em rank 1. O pipeline de três papéis
LLM foi rejeitado como inadequado ao MVP local em CPU. O modelo de consulta
padrão é `ministral-3:3b`.

## Rastreabilidade

SearchUnits normativas carregam uma ou mais `CitationItem`s, cada uma com
`stable_key`, label, `citation_text` e localizador. O Candidate também carrega
ato, referência estável, snapshot e URL oficial. Metadata documental não exige
Provision, mas preserva a cadeia `SearchUnit -> ActVersion -> SourceSnapshot ->
Source`.

O Citation Validator apenas verifica deterministicamente essa integridade
estrutural. O modelo seleciona evidências exclusivamente do enum request-scoped.

## Projeção contextual v2

A auditoria causal do corpus real separou problemas de representação, FTS e
avaliação. A projeção adotada modifica apenas os casos sustentados por evidência
estrutural:

- descendentes de ARTICLE recebem o CAPUT irmão regente no `search_text`;
- metadata recebe um rótulo factual derivado de seu `kind`;
- a unidade contextual do CAPUT é omitida somente quando seu `search_text` é
  exatamente igual ao da unidade ARTICLE.

ARTICLE continua contendo a subárvore completa. Compactá-lo antes de uma
ablação poderia degradar perguntas amplas e listas, portanto não foi adotado.
O texto citável, os locators e as relações com Provision não são modificados.

A projeção faz parte do contrato versionado do corpus
`constitutional-corpus-v3`. O bootstrap compara a versão ativa com a versão do
código. O bootstrap normal ainda preserva sua semântica de aquisição; uma
reprojeção causalmente isolada deve ser acionada explicitamente por
`corpus rematerializar --snapshot-sha <sha256>`. Ela cria novas ActVersions
sobre o snapshot escolhido e os embeddings podem ser reconstruídos depois;
snapshots e versões anteriores permanecem preservados. Não há migration nem
atualização destrutiva.

## Segurança e limites

Outputs LLM inválidos, falhas do provider e citações inválidas falham fechados,
sem segunda inferência. Há no máximo duas clarificações; cada resposta humana
provoca novo retrieval antes da consulta. Não se persistem consultas ou outputs
do modelo. O checkpointer interativo é em memória. Não há fine-tuning nem
fallback v0.1.
