# 14. Avaliação

## Objetivo

Construir uma infraestrutura mínima para medir retrieval, contrato e qualidade
material sem usar o HOLDOUT como desenvolvimento.

## Onde estamos e incremento

```text
runtime funcional → datasets DEV + runners + artifacts + human review
```

## Arquivos desta etapa

- `evaluation/dataset.py`, `metrics.py`, `report.py`;
- `evaluation/retrieval_baseline.py`, `gold_evidence.py`, `gold_stability.py`;
- `evaluation/integrated_rag.py`, `quality.py`, `runner.py`;
- `evaluation/datasets/`, `runs/` e `results/` para artifacts versionados;
- testes `test_v02_gold_evidence.py`, `test_v02_frozen_gold_bundle.py` e afins.

## Três níveis de medição

1. **Retrieval:** a provision esperada está em top-k? Calcule Hit@1/3/5/10,
   MRR e coverage.
2. **Gold Evidence:** forneça evidências congeladas ao modelo para medir sua
   capacidade sem confundir retrieval.
3. **Integrated DEV:** execute o pipeline real e atribua a falha ao estágio.

Um caso didático público pode ter pergunta, modo, version hash, expected
decision e stable keys aceitáveis. Não copie os casos privados do HOLDOUT.

```python
@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    question: str
    expected_decision: str
    required_stable_keys: tuple[str, ...]
```

## Métricas

Para retrieval, o reciprocal rank é `1/rank` da primeira provision aceitável,
ou zero. Para answerer, meça separadamente:

- JSON/schema/payload válido;
- decisão esperada e citações obrigatórias;
- correção jurídica humana;
- groundedness;
- completude;
- `human_all_pass` e interseção strict.

```python
def reciprocal_rank(ranked_keys, acceptable):
    for rank, keys in enumerate(ranked_keys, start=1):
        if set(keys) & acceptable:
            return 1 / rank
    return 0.0
```

Automatic pass não substitui revisão: envelope perfeito pode conter erro
jurídico, e resposta materialmente boa pode violar schema.

## Reprodutibilidade

Grave raw output antes de derivar summaries; inclua modelo, digest, prompt,
seed, parâmetros, dataset hash e timestamps. Recuse sobrescrever artifacts.
Em estabilidade, altere somente a seed e compare decisão/citações.

## Testes e execução

Teste parsing de dataset, hashes, duplicatas, métricas, bundles imutáveis e
separação entre resultados automáticos/humanos.

```bash
uv run pytest tests/test_v02_gold_evidence.py \
  tests/test_v02_frozen_gold_bundle.py \
  tests/test_v02_gold_ollama_runner.py -q
uv run consultor_juridico eval --help
```

Inferências longas devem ser manuais; testes automáticos usam respostas
congeladas ou fakes.

## Checkpoint

Você consegue avaliar retrieval isolado, modelo com evidence fixa e DEV
integrado, preservando raws e distinguindo falha formal de material. O HOLDOUT
ainda não foi lido.

**Anterior:** [CLI](13-cli-bootstrap-packaging.md).  
**Próximo:** [freeze e HOLDOUT](15-freeze-and-holdout.md).
