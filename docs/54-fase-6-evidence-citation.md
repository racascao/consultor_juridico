# Fase 6 — Evidence, geração local e validação de citações

## Resultado

A consulta final transforma o retrieval híbrido em uma resposta fundamentada e
auditável. Cada execução persiste um `EvidenceSet`; seus `EvidenceItem`s são
snapshots imutáveis dos chunks efetivamente enviados ao modelo local. Claims só
são persistidas depois da validação determinística de todas as citações.

```text
pergunta → retrieval híbrido → EvidenceSet/EvidenceItem snapshot
         → prompt restrito às evidências → Ollama/llama3.2
         → claims estruturadas → Citation Validator
         → Claims/Citations válidas ou abstenção
```

## Evidence Builder e Validator

O builder aceita somente chunks ligados primariamente a ocorrências
`CURRENT + NORMATIVE` de versões ativas. Antes de congelar um item, confirma
Chunk, LegalElement, LegalProvision, LegalVersion e SourceDocument, além da
igualdade entre o texto recuperado e o snapshot. Metadados preservam ranks,
scores, `identity_key`, IDs jurídicos e status.

O Citation Validator rejeita claims sem citação, códigos inexistentes, itens de
outro conjunto, evidências não validadas, snapshots divergentes e URLs que não
correspondam à captura oficial. A FK composta existente continua sendo a
garantia física contra cruzamento de EvidenceSets.

Validação semântica automática de entailment não é declarada como resolvida:
o MVP valida a cadeia, completude estrutural e imutabilidade. Fidelidade
semântica ampla pertence à avaliação da Fase 7.

## Prompt e Ollama

O prompt contém apenas pergunta, identificadores, rótulos, URL oficial e
`text_snapshot` dos itens selecionados. O endpoint `/api/chat` usa o modelo
local configurável, temperatura zero e JSON Schema. O contrato exige `answer`,
`abstain` e claims com `evidence_ids`.

Uma saída inválida recebe uma única tentativa corretiva por padrão. Persistindo
a falha, o sistema se abstém e não grava Claim/Citation. A resposta apresentada
é reconstruída deterministicamente a partir das claims validadas, acompanhadas
dos códigos de evidência; o texto livre original do LLM fica apenas nos
metadados de auditoria.

## Estados e atomicidade

- `INSUFFICIENT_EVIDENCE`: nenhum item tecnicamente válido; o LLM não é chamado;
- `ABSTAINED`: o modelo declarou insuficiência;
- `VALIDATION_FAILED`: saídas recusadas após as tentativas permitidas;
- `VALIDATED`: Claims e Citations foram materializadas com sucesso.

O EvidenceSet e seu snapshot são confirmados antes da geração para registrar a
consulta. Claims e Citations são gravadas juntas somente após validação. Uma
saída inválida nunca se torna uma afirmação persistida.

## Configuração e CLI

Variáveis: `OLLAMA_MODEL`, `CONSULTATION_TIMEOUT`, `CONSULTATION_MAX_TOKENS`,
`CONSULTATION_TOP_K` e `CONSULTATION_MAX_ATTEMPTS`.

```bash
consultor-juridico consult \
  "O que a Constituição diz sobre a manifestação do pensamento?"
consultor-juridico consult "Como funciona o voto?" --act CF/88 --limit 8
```

A saída inclui outcome, EvidenceSet, resposta, claims, códigos, rótulos e URL
oficial. O campo livre `answer` do JSON não é fonte da resposta exibida: ela é
montada a partir das claims que passaram pela validação, inclusive quando o
modelo deixa esse campo redundante vazio.

## Testes e integração

Testes unitários cobrem contrato JSON, prompt fechado, configuração do Ollama,
abstenção e rejeição de claim sem citação. A integração local é opt-in, não usa
internet e percorre retrieval, embeddings, Ollama, persistência e cadeia final:

```bash
RUN_CONSULTATION_INTEGRATION=1 uv run pytest \
  -m consultation_integration -vv -s
```

## Limitações

- o corpus continua restrito a CF/88 e ADCT;
- não há reranker adicional nem HNSW;
- a suficiência temática final combina retrieval e abstenção do modelo;
- avaliação extensiva de fidelidade, hallucination e thresholds fica na Fase 7;
- não há API HTTP ou frontend.
