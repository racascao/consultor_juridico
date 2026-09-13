# Integração RAG end-to-end do MVP2

## Estado

O fluxo foi implementado sem inferência real e sem abrir o HOLDOUT:

```text
question
→ PostgreSQL FTS RELAXED_OR_WEIGHTED_COVERAGE
→ SearchUnit + Provision.stable_key
→ GoldEvidenceItem
→ gold-evidence-answering/2
→ gemma4:12b congelado
→ contrato JSON estrito
→ Citation Validation
→ RagResult rastreável
```

O assembly mantém a ordem do retrieval, elimina somente chaves repetidas e
materializa texto, locator, hash do snapshot e URL oficial. Nenhuma chave é
inventada. Uma citação ausente do namespace da `ActVersion` é
`INVALID_CITATION`; uma chave existente no corpus, mas ausente da evidência
fornecida, é `OUT_OF_EVIDENCE`. Ambas interrompem a execução.

O adapter valida o artifact local do freeze, a tag e o digest expostos pelo
Ollama antes da geração. O request usa `format=json`, `think=false`,
`stream=false`, timeout de 180 segundos e as opções congeladas. Não há reparo,
remoção de fences ou retry de formato.

### Runtime NVIDIA do Ollama

O host atual possui uma NVIDIA GeForce RTX 5070 Laptop GPU, driver 580.159.03
e CUDA 13.0 reportada. O NVIDIA Container Toolkit 1.20.0 está funcional. O
Compose expõe a GPU ao serviço `ollama` com `gpus: all`, preservando profile,
porta e volume de modelos. Após a recriação exclusiva desse serviço,
`DeviceRequests` confirmou a concessão da GPU, `nvidia-smi` funcionou no
container e os logs do Ollama identificaram o backend CUDA.

Essa aceleração é configuração operacional: `gemma4:12b`, digest, prompt,
`format=json`, opções de geração e timeout de 180 segundos permanecem
inalterados. Nenhuma geração foi executada nesta validação e nenhum retry foi
adicionado. O timeout observado no novo smoke 4 continua inconclusivo até o
reteste manual com o runtime GPU confirmado.

## Hardening após os primeiros smokes

Os primeiros testes manuais mostraram duas causas anteriores ao answerer. A
cobertura lexical simples atribuía o mesmo peso a lexemas comuns e raros: a
SearchUnit da avocação ficava no rank 11, e o núcleo do recurso intempestivo
ficava fora do top-10. Além disso, recuperar um CAPUT regente não incluía seus
incisos, pois projeção e assembly eram estritamente 1:1.

O runtime passou a ponderar cobertura pela frequência documental dos lexemas na
própria `ActVersion`, preservando PostgreSQL FTS, geração OR e desempates. No DEV
lexical conhecido, sem LLM, o resultado passou de `Hit@10=0,875` e `MRR=0,661`
para `Hit@10=0,900` e `MRR=0,740625`. O assembly passou a incluir filhos textuais
diretos da provision recuperada, em ordem documental, com limite de oito filhos
por pai e 24 EvidenceItems no total. Não há regra por artigo, pergunta ou caso.

Após a correção, a pergunta composta recupera `ARTICLE:15/CAPUT` no rank 2 e
monta `ARTICLE:13/CAPUT` com seus três incisos. A pergunta sobre recurso fora do
prazo recupera `ARTICLE:63/CAPUT` no rank 7 e monta seus quatro incisos. Esses
resultados são read-only; o answerer não foi executado.

A primeira falha `SELECTED_ANSWERER_REQUEST_FAILED`, seguida de sucesso na mesma
consulta, permanece transitória sem causa retrospectiva observável. Não foi
criado retry. Falhas futuras distinguem timeout, conectividade, status HTTP e
resposta inválida sem expor payloads.

### Packaging Docker do freeze

O freeze e todos os 13 artifacts referenciados por ele são runtime-critical.
O Dockerfile os copia individualmente para seus caminhos originais sob
`/app/evaluation/{model_selection,datasets,runs,results}`. Não existe cópia
ampla de `evaluation/`, e nenhum HOLDOUT é empacotado. O build e a validação no
container confirmaram `SELECTION_EVIDENCE_MATCH=YES` e `STATUS=VALID`.

Retrieval vazio resulta em `ABSTAIN` determinístico, sem chamada ao modelo.
`ANSWER` exige ao menos uma citação; `ABSTAIN` exige lista vazia; `CLARIFY`
preserva a decisão produzida. O resultado contém hits, scores, evidence set,
decisão, citações, validação e identidades do modelo, freeze e prompt.

## Readiness real

O artifact local versionado da Lei nº 9.784/1999 foi usado sem acesso à rede:

```text
source_kind=LOCAL_VERSIONED
source_sha256=b4abab2e47732f76a16a99e8b00311dcb420b378f89e99c096b609ae84529261
version_hash=bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6
parser=planalto-lei-structural/1
projection=provision-text/1
act_versions=1
provisions=322
search_units=242
RAG_READINESS=READY
```

A segunda execução reutilizou o snapshot e a versão e não duplicou dados. Isso
estabelece um corpus atual utilizável, mas não reconstrói nem declara identidade
com o snapshot histórico perdido `face6f55...`; `LIVE_CORPUS_STATUS` permanece
`UNRESOLVED` para essa comparação histórica. O MVP2 usa `SearchUnit` diretamente
e não possui chunks ou embeddings; vector e RRF seguem `NOT_JUSTIFIED`.

Diagnóstico:

```bash
consultor-juridico rag status
```

Consulta, depois da preparação explícita do corpus:

```bash
consultor-juridico ask "<pergunta>" \
  --mode legal-rule \
  --version-hash bfa031c3e55bb8ff5e9349a9b8b278dcc5f84e64dcb918488ea9bf8316778cc6 \
  [--trace]
```

Dentro do Compose, o endpoint é `http://ollama:11434`. No host, o mesmo
container é acessado por `http://localhost:11435`; a porta nativa 11434 não é
suportada pelo projeto.

## Próximo gate

Os smokes foram concluídos o suficiente para iniciar DEV. A primeira campanha
Integrated DEV executou 32 casos pelo retrieval e evidence assembly reais, com
`24/32` automatic pass, dois `RETRIEVAL_MISS`, seis falhas de decisão nos seis
casos ambíguos e nenhuma falha de Citation Validation. Resultados, hashes e
limitações estão em
[`integrated-dev-mvp2.md`](evaluation/integrated-dev-mvp2.md).

A revisão material humana concluiu `24/32` all pass. A análise causal separou um
mismatch lexical, uma diluição multipart e a ausência de representação
estruturada de fatos necessários. Uma fusão lexical geral regrediu o DEV e foi
rejeitada; nenhum gate factual determinístico mostrou-se seguro com o input
atual. Não houve tuning nem alteração do runtime. A evidência completa está em
[`integrated-dev-general-failure-analysis-v1.md`](evaluation/integrated-dev-general-failure-analysis-v1.md).
O runtime ainda não foi congelado e o HOLDOUT permanece fechado.

## Decisão de factual sufficiency

A revisão arquitetural posterior selecionou um contrato explícito de dois modos.
`LEGAL_RULE` preservará o pipeline atual; `CASE_APPLICATION` deverá retornar
`CLARIFY` deterministicamente e sem LLM enquanto o projeto não possuir contrato
verificável de fatos necessários. A decisão evita inferência por pronomes,
segundo judge e alteração do prompt congelado. Ela está documentada em
[`factual-sufficiency-architecture-reconsideration-v1.md`](evaluation/factual-sufficiency-architecture-reconsideration-v1.md)
e foi implementada sem alterar retrieval, prompt, answerer ou freeze. O modo é
obrigatório na CLI e na API de aplicação; não existe inferência pelo texto.
`CASE_APPLICATION` retorna `CLARIFY` antes de abrir banco ou cliente HTTP, com
citações vazias e trace `retrieval=NOT_EXECUTED`/`answerer=NOT_EXECUTED`.
Os dois modos passaram no smoke manual. O evaluator
`integrated-dev-v2-two-mode` está preparado com mapping externo imutável; a
campanha de 26 inferências normativas foi executada manualmente, revisada e
congelada como `integrated-runtime-mvp2/1`. O resultado humano foi `30/32` all
pass; `GOLD-003` e `GOLD-016` permanecem riscos residuais aceitos de retrieval.
O HOLDOUT continua fechado.
