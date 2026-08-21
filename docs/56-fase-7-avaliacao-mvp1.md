# Fase 7 — avaliação sistemática e fechamento técnico do MVP1

## 1. Objetivo e gate

Esta fase mediu retrieval, decisão de resposta/abstenção, integridade de
citações e operação do `llama3.2` sem redesenhar o domínio.

**Gate final: `MVP1_QUALITY_BLOCKED`.**

Blockers comprovados:

1. Hybrid Hit@10 = 0,714, abaixo do threshold pré-definido de 0,90.
2. Uma de três perguntas claramente fora do corpus recebeu resposta
   (`unsafe answer decision`).

## 2. Baseline

- branch `main`, commit inicial `d9dc5e5`;
- Ruff passou;
- 193 testes passaram e 4 integrações estavam desabilitadas por padrão;
- PostgreSQL/pgvector e Ollama saudáveis;
- Alembic `005_normative_identity_occurrences`;
- corpus: 1 Source, 1 SourceDocument, 2 LegalVersions, 4.096
  LegalProvisions, 6.775 LegalElements, 3.389 chunks e 3.389 embeddings.

## 3. Dataset

`evaluation/datasets/mvp1_v1.json` contém 30 casos auditáveis. São 21 casos
respondíveis e 9 de abstenção, distribuídos entre perguntas diretas,
paráfrases, lexicalmente fortes, múltiplas provisions, ADCT, fora do corpus,
jurídicas fora do escopo, ambíguas, adversariais e premissa falsa.

As provisions esperadas são `identity_key`s existentes no corpus materializado.
Não se exige igualdade textual da resposta generativa.

## 4. Metodologia e thresholds definidos antes da execução

- Hybrid Hit@10 >= 0,90;
- expected provision recall >= 0,90;
- citações inválidas aceitas = 0;
- claims validadas sem citation = 0;
- respostas fora das evidências nos casos adversariais = 0;
- nenhuma resposta após falha do Citation Validator.

Retrieval foi medido independentemente do LLM por identidade normativa, com
Hit@1/3/5/10, MRR e Recall@10. A avaliação generativa foi limitada a amostra
controlada porque cada execução persiste a cadeia auditável e o banco atual não
é descartável.

## 5. Retrieval — baseline

| modo | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR | Recall@10 |
|---|---:|---:|---:|---:|---:|---:|
| lexical | 0,190 | 0,190 | 0,190 | 0,190 | 0,190 | 0,190 |
| vector | 0,476 | 0,571 | 0,619 | 0,667 | 0,544 | 0,643 |
| hybrid | 0,476 | 0,571 | 0,619 | 0,667 | 0,544 | 0,643 |

Tempos totais para 21 casos: lexical 0,08 s, vector 2,19 s e hybrid 1,72 s.

## 6. Falha, hipótese, correção e comparação

Falha: FTS retornava poucos resultados porque a pergunta natural inteira era
convertida em conjunção pelo `websearch_to_tsquery`.

Hipótese: uma disjunção segura dos tokens lexicais aumentaria recall sem mudar
índice, chunking ou embeddings.

Alteração: `lexical_query_text` extrai tokens Unicode e usa OR. Foi adicionada
regressão unitária; o dataset completo foi reexecutado.

| modo | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR | Recall@10 |
|---|---:|---:|---:|---:|---:|---:|
| lexical | 0,476 | 0,571 | 0,667 | 0,667 | 0,548 | 0,667 |
| vector | 0,476 | 0,571 | 0,619 | 0,667 | 0,544 | 0,643 |
| hybrid | 0,524 | 0,667 | 0,714 | 0,714 | 0,591 | 0,690 |

Tempos após a correção: lexical 0,20 s, vector 1,65 s e hybrid 1,94 s.
A melhora foi mantida, mas não atingiu o threshold.

## 7. Evidence selection

O Evidence Builder usa top-8 híbrido e mantém apenas cadeia
`CURRENT + NORMATIVE` válida. Como proxy reproduzível, 71,4% dos casos tinham
alguma provision esperada até a posição 8; o recall médio das provisions
esperadas no top-10 foi 0,690. A precisão é baixa por construção: até oito
EvidenceItems são enviados mesmo quando apenas um é esperado, ampliando ruído.

## 8. Respostas, abstenção e grounding

A amostra estratificada fora do corpus produziu:

| caso | esperado | resultado | latência |
|---|---|---|---:|
| receita | abster | ABSTAINED | 46,34 s |
| futebol | abster | ABSTAINED | 54,41 s |
| Python | abster | ANSWERED | 101,19 s |

Matriz da amostra:

| esperado | respondeu | absteve |
|---|---:|---:|
| responder | 0 | 0 |
| abster | 1 | 2 |

Taxa correta de abstenção: 0,667. Taxa de resposta indevida: 0,333.
O caso Python gerou uma Claim com oito Citations estruturalmente válidas, mas
semanticamente irrelevantes. Isso comprova que integridade física não equivale
a entailment e que o prompt/LLM não bastam como gate semântico.

Uma amostra respondível foi interrompida após exceder seis minutos; ficou um
EvidenceSet em `EVIDENCE_VALIDATED`, sem Claim parcial. O tempo observado é um
warning de operação local e não foi transformado em benchmark CPU-only, pois o
ambiente não comprova isolamento de CPU/GPU.

Latências da amostra fora do corpus: média 67,31 s, p50 54,41 s e p95 observado
101,19 s (amostra pequena; percentil apenas diagnóstico).

## 9. Claims, Citations e testes adversariais

Testes unitários rejeitam claim sem citation, código inventado, EvidenceItem de
outro conjunto e item não validado. A auditoria SQL encontrou:

- citações inválidas aceitas: 0;
- cadeias físicas inválidas: 0;
- SourceDocuments com SHA divergente: 0.

O problema encontrado é semântico: uma cadeia fisicamente válida pode sustentar
uma Claim fora do tema. Nenhum segundo LLM foi adotado como autoridade.

## 10. Modelo e reprodutibilidade

- provider: Ollama local;
- modelo generativo: `llama3.2`;
- embeddings: `nomic-embed-text:latest`, 768 dimensões;
- temperatura: 0;
- retrieval: RRF k=60, top-10 no benchmark, top-8 em consultation;
- retry: máximo 2 tentativas;
- dataset: `mvp1-v1`.

Não havia outro modelo pequeno previamente disponível; comparação multi-modelo
foi adiada. Nenhum modelo adicional foi baixado.

## 11. Artefatos

- `evaluation/results/mvp1_v1_retrieval.json`: baseline;
- `evaluation/results/mvp1_v1_retrieval_after.json`: após correção;
- `evaluation/results/mvp1_v1_consult_outside.json`: amostra generativa.

Resultados pequenos e determinísticos entram no Git. Logs SQL e artefatos
volumosos permanecem fora.

## 12. Limitações e recomendações pós-MVP1

- retrieval ainda abaixo do gate;
- ausência de gate semântico determinístico antes de persistir Claims;
- abstenção insegura em 1/3 da amostra fora do corpus;
- latência alta e variável do `llama3.2` local;
- amostra generativa pequena devido ao banco não descartável;
- nenhuma medição CPU-only confiável;
- dataset inicial com 30 casos requer revisão jurídica humana futura.

Próxima revisão deve investigar evidence precision, detecção de escopo e suporte
semântico por critérios humanos/determinísticos, sem promover outro LLM a fonte
de verdade. O MVP1 não deve ser declarado aprovado antes de nova medição atingir
os thresholds e eliminar respostas indevidas fora do corpus.
