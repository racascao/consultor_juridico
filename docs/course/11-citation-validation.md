# 11. Citation Validation

## Objetivo

Aceitar somente citações que existam na versão e tenham sido apresentadas ao
modelo na consulta atual.

## Onde estamos e incremento

```text
AnswerContract + EvidenceItems + corpus namespace
             → CitationValidation → RagResult ou erro fail-closed
```

## Arquivos desta etapa

- `domain/rag.py` para status/resultados;
- `application/rag/services.py` para validação;
- `infrastructure/gold_evidence.py` para namespaces;
- `tests/test_v02_rag.py`.

## Contrato

```python
class CitationStatus(StrEnum):
    VALID = "VALID"
    INVALID_CITATION = "INVALID_CITATION"
    OUT_OF_EVIDENCE = "OUT_OF_EVIDENCE"


@dataclass(frozen=True, slots=True)
class CitationValidation:
    status: CitationStatus
    invalid_citations: tuple[str, ...] = ()
    out_of_evidence: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return self.status is CitationStatus.VALID
```

Existem dois conjuntos autorizadores. `corpus_keys` responde se a identidade
existe; `evidence_keys` responde se ela foi entregue ao answerer nessa pergunta.

## Implementação literal

```python
def validate_citations(citations, *, evidence_keys, corpus_keys):
    cited = frozenset(citations)
    invalid = tuple(sorted(cited - corpus_keys))
    if invalid:
        return CitationValidation(CitationStatus.INVALID_CITATION, invalid)
    outside = tuple(sorted(cited - evidence_keys))
    if outside:
        return CitationValidation(
            CitationStatus.OUT_OF_EVIDENCE, out_of_evidence=outside
        )
    return CitationValidation(CitationStatus.VALID)
```

`SqlAlchemyGoldEvidenceRepository.provision_keys(version_hash)` constrói o
namespace do corpus da versão. As evidence keys vêm diretamente do tuple
montado no capítulo 8. O modelo nunca decide validade formal.

## Integração

Depois de `parse_answer_contract`, `RunRagQuery` chama o validator. Resultado
não válido levanta `CitationValidationError`; não persista nem apresente uma
resposta parcialmente aceita.

```python
validation = validate_citations(
    output.citations,
    evidence_keys=frozenset(item.stable_key for item in evidence),
    corpus_keys=repository.provision_keys(request.version_hash),
)
if not validation.valid:
    raise CitationValidationError(validation)
```

## Testes

Cubra citação válida, inventada, existente mas fora do EvidenceSet, nenhuma
citação em abstenção e isolamento por versão.

```python
def test_existing_but_unseen_key_is_out_of_evidence():
    result = validate_citations(
        ("article:2",),
        evidence_keys=frozenset({"article:1"}),
        corpus_keys=frozenset({"article:1", "article:2"}),
    )
    assert result.status is CitationStatus.OUT_OF_EVIDENCE
```

```bash
uv run pytest tests/test_v02_rag.py -q
```

## Checkpoint

Toda resposta `ANSWER` aceita cita apenas stable keys do EvidenceSet atual. A
cadeia preserva locator, snapshot e fonte; nenhuma citação é inventada.

**Anterior:** [Structured Output](10-structured-output.md).  
**Próximo:** [Query Modes](12-query-modes.md).
