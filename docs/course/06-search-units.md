# 06. SearchUnits

## Objetivo

Projetar provisions textuais em unidades recuperáveis e materializar uma
ActVersion completa transacionalmente.

## Onde estamos e incremento

```text
ParsedDocument → ProvisionTextProjection → ProjectedSearchUnit[]
               → SqlAlchemyCorpusMaterializer → ActVersion persistida
```

## Arquivos desta etapa

- `application/corpus/projection.py`, `services.py` e `ports.py`;
- `infrastructure/corpus/materializer.py`;
- testes unitários e `tests/integration/test_v02_corpus_postgresql.py`.

## Por que projetar

Provisions representam a hierarquia e podem ser containers sem texto.
SearchUnits representam o que o FTS pesquisa. Essa separação permite mudar uma
projeção em versão futura sem perder o snapshot ou a árvore original.

## Contratos e projeção

```python
@dataclass(frozen=True, slots=True)
class ProjectedSearchUnit:
    unit_key: str
    search_text: str
    provision_stable_keys: tuple[str, ...]

    @property
    def content_hash(self) -> str:
        return sha256(self.search_text.encode()).hexdigest()
```

O arquivo real `application/corpus/projection.py` é deliberadamente pequeno:

```python
class ProvisionTextProjection:
    def project(self, parsed: ParsedDocument) -> tuple[ProjectedSearchUnit, ...]:
        return tuple(
            ProjectedSearchUnit(
                unit_key=p.stable_key,
                search_text=p.citation_text,
                provision_stable_keys=(p.stable_key,),
            )
            for p in parsed.provisions
            if p.citation_text and p.citation_text.strip()
        )
```

Nome e versão congelados: `provision-text/1`. Containers sem texto não viram
SearchUnit; cada unidade aponta para sua provision sustentadora.

## Materialização

`MaterializeFromSnapshot.execute` obtém bytes pelo SHA, chama parser e projeção
e entrega tudo ao `CorpusMaterializer`. O adapter SQLAlchemy:

1. cria/reutiliza `LegalAct`;
2. calcula `version_hash` com identidades de snapshot/parser/projeção;
3. retorna a versão existente se a identidade natural já existe;
4. cria ActVersion, provisions em ordem, resolve `parent_id` por stable key;
5. cria SearchUnits e associações;
6. valida contagens e encerra a transação.

Nunca faça commit parcial entre esses passos. Uma falha deve deixar zero nova
ActVersion.

## Testes

```python
def test_projection_ignores_containers_without_text(parsed_document):
    units = ProvisionTextProjection().project(parsed_document)
    assert all(unit.search_text.strip() for unit in units)
    assert all(len(unit.provision_stable_keys) == 1 for unit in units)
```

Na integração, execute duas materializações e compare IDs/contagens; injete
falha antes do commit e confirme rollback. Verifique que links unem apenas
objetos da mesma ActVersion.

```bash
V02_TEST_DATABASE_URL=postgresql+psycopg://... uv run pytest \
  tests/integration/test_v02_corpus_postgresql.py -q
```

No corpus congelado, o resultado esperado é 322 provisions, 242 SearchUnits,
parser `planalto-lei-structural/1` e projeção `provision-text/1`.

## Checkpoint

Uma ActVersion completa, segunda execução idempotente, contagens esperadas e
nenhum commit parcial. Agora existe texto pesquisável, mas ainda não há busca.

**Anterior:** [parser](05-structural-parser.md).  
**Próximo:** [PostgreSQL FTS](07-postgresql-fts.md).
