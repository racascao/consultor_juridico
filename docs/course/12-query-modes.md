# 12. Query Modes

## Objetivo

Implementar um boundary explícito entre explicação de regra e aplicação a
fatos concretos.

## Onde estamos e incremento

```text
RagQueryRequest.mode
├─ LEGAL_RULE       → pipeline RAG completo
└─ CASE_APPLICATION → CLARIFY determinístico
```

## Arquivos desta etapa

- `domain/rag.py`;
- `application/rag/services.py`;
- `application/rag/types.py`;
- testes em `tests/test_v02_rag.py`.

## Contrato

```python
class QueryMode(StrEnum):
    LEGAL_RULE = "legal-rule"
    CASE_APPLICATION = "case-application"


@dataclass(frozen=True, slots=True)
class RagQueryRequest:
    question: str
    version_hash: str
    mode: QueryMode
    limit: int = 10
```

Valide pergunta, hash e limite. O caller escolhe o modo; não inspecione palavras
da pergunta para inferi-lo.

## Contenção determinística

```python
def case_application_result(request: RagQueryRequest) -> RagResult:
    if request.mode is not QueryMode.CASE_APPLICATION:
        raise ValueError("CASE_APPLICATION_MODE_REQUIRED")
    return RagResult(
        question=request.question,
        retrieved=(),
        evidence=(),
        output=AnswerContract(
            RagDecision.CLARIFY,
            "Para aplicar uma regra jurídica a um caso concreto, são necessários fatos estruturados e verificáveis.",
            (),
        ),
        citation_validation=CitationValidation(CitationStatus.VALID),
        identity=None,
        query_mode=request.mode,
        retrieval_executed=False,
        answerer_executed=False,
    )
```

O recorte reduz a mensagem, mas preserva a estrutura real.

## Orquestrador completo

`RunRagQuery.execute` verifica o modo antes de criar `RetrievalRequest`. Para
`LEGAL_RULE`: valida contextos, busca, monta evidence, abstém se vazio, gera,
parseia, valida citações e retorna `RagResult` com identidade do freeze.

```python
def execute(self, request: RagQueryRequest) -> RagResult:
    if request.mode is QueryMode.CASE_APPLICATION:
        return case_application_result(request)
    candidates = self._retriever.search(...)
    evidence = EvidenceAssembler(self._evidence_repository).assemble(...)
    # empty evidence -> ABSTAIN; otherwise generate, parse and validate
```

## Testes de não execução

Use doubles que falham se chamados:

```python
class MustNotRun:
    def __getattr__(self, name):
        raise AssertionError(f"{name} não deveria ser chamado")


def test_case_application_bypasses_retrieval_and_answerer():
    service = RunRagQuery(MustNotRun(), MustNotRun(), MustNotRun())
    result = service.execute(case_request)
    assert result.output.decision is RagDecision.CLARIFY
    assert not result.retrieval_executed
    assert not result.answerer_executed
    assert result.output.citations == ()
```

Teste também o caminho `LEGAL_RULE`, abstenção por evidence vazia, identidade
do runtime e propagation de erros fail-closed.

```bash
uv run pytest tests/test_v02_rag.py -q
```

## Decisão arquitetural

Classifier, heurística ou LLM router não fornecem os fatos ausentes e tornam o
boundary probabilístico. Veja [experimentos de modos](../experiments/query-modes.md).

## Checkpoint

`CASE_APPLICATION` passa com zero chamada externa; `LEGAL_RULE` percorre todos
os componentes e devolve flags verdadeiras. O pipeline de domínio está completo.

**Anterior:** [Citation Validation](11-citation-validation.md).  
**Próximo:** [CLI e bootstrap](13-cli-bootstrap-packaging.md).
