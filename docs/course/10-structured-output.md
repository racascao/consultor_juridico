# 10. Structured Output

## Objetivo

Converter a resposta bruta do modelo em um `AnswerContract` tipado e rejeitar
qualquer envelope ambíguo.

## Onde estamos e incremento

```text
raw response → json.loads → Pydantic strict schema → AnswerContract
```

## Arquivos desta etapa

- `domain/rag.py`;
- `application/rag/services.py`;
- testes de contrato em `tests/test_v02_rag.py`.

## Contratos

```python
class RagDecision(StrEnum):
    ANSWER = "ANSWER"
    ABSTAIN = "ABSTAIN"
    CLARIFY = "CLARIFY"


@dataclass(frozen=True, slots=True)
class AnswerContract:
    decision: RagDecision
    answer: str
    citations: tuple[str, ...]
```

Pydantic valida o envelope externo:

```python
class _StructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: RagDecision
    answer: str
    citations: tuple[str, ...]
```

## Parser literal

```python
def parse_answer_contract(raw_response: str) -> AnswerContract:
    try:
        payload = json.loads(raw_response)
        parsed = _StructuredOutput.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as error:
        raise InvalidAnswerContractError("INVALID_ANSWER_CONTRACT") from error
    if not parsed.answer.strip():
        raise InvalidAnswerContractError("ANSWER_TEXT_REQUIRED")
    if parsed.decision is RagDecision.ABSTAIN and parsed.citations:
        raise InvalidAnswerContractError("ABSTAIN_CITATIONS_MUST_BE_EMPTY")
    if parsed.decision is RagDecision.ANSWER and not parsed.citations:
        raise InvalidAnswerContractError("ANSWER_CITATIONS_REQUIRED")
    if len(set(parsed.citations)) != len(parsed.citations):
        raise InvalidAnswerContractError("DUPLICATE_CITATIONS")
    return AnswerContract(parsed.decision, parsed.answer, parsed.citations)
```

Válido:

```json
{"decision":"ANSWER","answer":"A regra estabelece...","citations":["article:1/caput"]}
```

Inválidos: Markdown cercando JSON, campo extra, answer vazio, `ANSWER` sem
citação, `ABSTAIN` com citação e chaves duplicadas.

## Por que `format=json` não basta

Ollama ajuda o modelo a produzir JSON sintaticamente válido; Pydantic e as
invariantes verificam o contrato do produto. Nenhum stripping, renome de campo,
parser tolerante ou reparo silencioso é permitido.

Erro de interface significa que não foi possível interpretar o payload. Erro
material significa que um payload válido está juridicamente errado ou
incompleto. As duas dimensões devem ser medidas separadamente.

## Testes

Parametrize payloads válidos/inválidos e confira a exceção exata:

```python
@pytest.mark.parametrize("raw", ["not-json", "{}", '{"decision":"ANSWER"}'])
def test_invalid_envelopes_fail_closed(raw):
    with pytest.raises(InvalidAnswerContractError):
        parse_answer_contract(raw)
```

```bash
uv run pytest tests/test_v02_rag.py -q
```

## Checkpoint

Nenhuma string bruta atravessa o boundary sem schema e invariantes. O contrato
ainda não prova que as citações foram autorizadas; isso vem a seguir.

**Anterior:** [answerer](09-local-answerer.md).  
**Próximo:** [Citation Validation](11-citation-validation.md).
