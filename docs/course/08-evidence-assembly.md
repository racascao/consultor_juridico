# 08. Evidence Assembly

## Objetivo

Converter candidates em evidências completas, ordenadas e autorizadas para o
answerer, expandindo somente filhos estruturais diretos.

## Onde estamos e incremento

```text
RetrievalCandidate[] → EvidenceAssembler → tuple[GoldEvidenceItem, ...]
```

## Antes de começar

O retriever deve retornar stable keys da ActVersion. Provisions precisam ter
parent, ordem, texto, locator e snapshot preservados.

## Arquivos desta etapa

- `application/gold_evidence/types.py` e `ports.py`;
- `application/rag/ports.py` e `services.py`;
- `infrastructure/gold_evidence.py`;
- `tests/test_v02_gold_evidence.py`, `test_v02_rag.py` e integração PostgreSQL.

## Contrato de evidência

O nome `GoldEvidenceItem` nasceu no isolamento experimental, mas o mesmo tipo é
usado como unidade autorizada do runtime:

```python
@dataclass(frozen=True, slots=True)
class GoldEvidenceItem:
    stable_key: str
    provision_type: str
    citation_text: str
    source_locator: dict[str, Any]
    source_snapshot_sha256: str
    official_url: str
    document_order: int
```

Confira os campos literais na tag ao implementar; o ponto contratual é que
texto, identidade, ordem, locator, URL e hash viajam juntos.

`StructuralEvidenceRepository` estende a porta de materialização:

```python
class StructuralEvidenceRepository(GoldEvidenceRepository, Protocol):
    def direct_children(
        self,
        version_hash: str,
        parent_keys: tuple[str, ...],
        *,
        max_children_per_parent: int,
    ) -> Mapping[str, tuple[GoldEvidenceItem, ...]]: ...
```

## Repository SQLAlchemy

`SqlAlchemyGoldEvidenceRepository.materialize` busca stable keys somente na
versão solicitada, liga Source/ActVersion para proveniência e preserva a ordem
de entrada. `direct_children` resolve IDs dos pais em batch e carrega filhos por
`document_order`; não execute uma query por pai.

Version safety é obrigatória: a mesma stable key em outra versão não pode ser
materializada. Uma key ausente não deve virar item parcial.

## Assembler literal

```python
@dataclass(frozen=True, slots=True)
class EvidenceAssembler:
    repository: StructuralEvidenceRepository
    max_children_per_parent: int = 8
    max_evidence_items: int = 24

    def assemble(self, version_hash: str, candidates):
        ordered_keys = tuple(
            dict.fromkeys(
                key
                for candidate in candidates
                for key in candidate.provision_stable_keys
            )
        )
        materialized = self.repository.materialize(version_hash, ordered_keys)
        by_key = {item.stable_key: item for item in materialized}
        missing = tuple(key for key in ordered_keys if key not in by_key)
        if missing:
            raise RagError(f"RETRIEVED_EVIDENCE_NOT_MATERIALIZABLE: {missing}")
        children = self.repository.direct_children(
            version_hash, ordered_keys, max_children_per_parent=8
        )
        expanded, seen = [], set()
        for key in ordered_keys:
            for item in (by_key[key], *children.get(key, ())):
                if item.stable_key in seen:
                    continue
                expanded.append(item)
                seen.add(item.stable_key)
                if len(expanded) == 24:
                    return tuple(expanded)
        return tuple(expanded)
```

## Exemplo executado

```text
candidates: [ARTICLE:6, ARTICLE:7]
children:   ARTICLE:6 → [CAPUT:6, INCISO:6:I]
            ARTICLE:7 → [CAPUT:7]

evidence: [ARTICLE:6, CAPUT:6, INCISO:6:I, ARTICLE:7, CAPUT:7]
```

Se `CAPUT:6` também vier como candidate, `seen` impede duplicata. Netos não
são adicionados. O limite de oito é por pai; 24 é global.

## Testes

Crie fakes que registrem chamadas e teste:

- pais na ordem do retrieval;
- filhos em ordem documental;
- corte em oito filhos e 24 itens;
- dedupe quando filho também é candidate;
- ausência de netos;
- key ausente gera `RagError`;
- outra versão não é aceita.

```python
def test_missing_retrieved_key_fails_closed(fake_repository, candidate):
    fake_repository.materialized = ()
    with pytest.raises(RagError, match="NOT_MATERIALIZABLE"):
        EvidenceAssembler(fake_repository).assemble("a" * 64, (candidate,))
```

```bash
uv run pytest tests/test_v02_gold_evidence.py tests/test_v02_rag.py -q
```

## Checkpoint

Todos os testes acima passam e um candidate real produz evidência com hash,
locator e URL. Ainda não há chamada LLM: este boundary pode ser inspecionado
inteiramente offline.

**Anterior:** [FTS](07-postgresql-fts.md).  
**Próximo:** [answerer local](09-local-answerer.md).
