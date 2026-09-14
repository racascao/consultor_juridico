# 04. Corpus jurídico

## Objetivo

Adquirir a Lei nº 9.784/1999, verificar seus bytes e persistir snapshots
imutáveis de forma idempotente.

## Onde estamos e incremento

```text
schema vazio → Planalto → SourceSnapshot(bytes + SHA-256 + metadata)
```

## Antes de começar

O banco deve estar no head. Adicione ao `Settings` timeouts HTTP, tentativas,
backoff, limites de tamanho e `PLANALTO_USER_AGENT`, como em `.env.example`.

## Arquivos desta etapa

- `application/corpus/catalog.py`, `ports.py`, `services.py`;
- `infrastructure/corpus/http.py`, `repositories.py`;
- `domain/corpus.py`;
- testes em `tests/test_v02_foundation_corpus.py` e integração PostgreSQL.

## Contratos

`SourceSpec` descreve autoridade, URL, encoding e limites. `SourceAcquirer`
retorna status, bytes e headers. `SnapshotRepository` consulta a última captura,
grava uma nova e localiza bytes por SHA. `AcquireOfficialSource` coordena sem
conhecer HTTP ou SQLAlchemy.

```python
@dataclass(frozen=True, slots=True)
class SourceSpec:
    authority_code: str
    official_url: str
    name: str
    encoding: str


class SourceAcquirer(Protocol):
    def acquire(
        self, url: str, *, etag: str | None, last_modified: str | None
    ) -> AcquisitionResponse: ...
```

O catálogo fixa o ato `BR-FED-LEI-9784-1999`; a URL é proveniência, não uma
dependência em tempo de consulta.

## Aquisição e idempotência

O adapter `HttpxSourceAcquirer.acquire` faz GET com timeout fornecido pelo
`httpx.Client`, envia `Accept-Encoding: identity` e headers condicionais,
exige sucesso e `text/html`, e retorna bytes sem normalização. O repository
calcula SHA-256 sobre os bytes e grava `byte_length`.

```python
class AcquireOfficialSource:
    def execute(self, source: SourceSpec) -> AcquisitionResult:
        previous = self._snapshots.latest_for_source(source)
        response = self._acquirer.acquire(
            source.official_url,
            etag=previous.etag if previous else None,
            last_modified=previous.last_modified if previous else None,
        )
        if response.status_code == 304:
            if previous is None:
                raise RuntimeError("Servidor retornou 304 sem snapshot anterior")
            return AcquisitionResult(previous, 304, created=False, reused=True)
        snapshot, created = self._snapshots.store(source, response)
        return AcquisitionResult(
            snapshot, response.status_code, created=created, reused=not created
        )
```

Este é um recorte didático: a tag também trata headers e erros de contrato.
Idempotência vem de `source + sha256`, não de um arquivo sentinel.

## Integridade e versionamento

O snapshot congelado em `docs/corpus/artifacts/` possui SHA-256
`b4abab2e47732f76a16a99e8b00311dcb420b378f89e99c096b609ae84529261`.
`decode_strict(raw_bytes, "windows-1252")` rejeita bytes indecodificáveis;
nunca use `errors="ignore"`.

`BOOTSTRAP_WEB_FETCH=ENABLED`: o bootstrap pode adquirir quando ausente.
`QUERY_TIME_WEB_FETCH=DISABLED`: o pipeline de consulta não possui acquirer.

## Testes

Use um fake acquirer para testar criação, 304/reuso, SHA, limites e erro HTTP:

```python
def test_second_equal_acquisition_reuses_snapshot(service, repository):
    first = service.execute(LEI_9784_SOURCE)
    second = service.execute(LEI_9784_SOURCE)
    assert first.snapshot.sha256 == second.snapshot.sha256
    assert second.created is False
    assert repository.count() == 1
```

No teste PostgreSQL, tente UPDATE no snapshot e espere rejeição pela trigger.

## Executando

Quando adicionar o grupo CLI `corpus` (forma final no capítulo 13):

```bash
uv run consultor_juridico corpus adquirir
uv run consultor_juridico corpus adquirir
```

Ambas devem imprimir o mesmo SHA; a segunda indica `REUSED`. Durante o curso,
também é aceitável instanciar o caso de uso em um pequeno teste de integração.

## Checkpoint

Uma `Source`, um snapshot imutável, SHA conferido e segunda execução sem
duplicata. Ainda não existem provisions ou SearchUnits.

**Anterior:** [modelo de dados](03-data-model.md).  
**Próximo:** [parser estrutural](05-structural-parser.md).
