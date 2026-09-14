# 03. Modelo de dados

## Objetivo

Criar engine, sessões, modelos SQLAlchemy e as duas migrations do schema MVP2.

## Onde estamos e incremento

```text
PostgreSQL vazio → Alembic → snapshots + ato/versão + provisions + SearchUnits
```

## Arquivos desta etapa

Criados:

- `alembic.ini`;
- `src/consultor_juridico/db/base.py`, `session.py` e `migrations/`;
- `src/consultor_juridico/infrastructure/corpus/models.py`;
- migrations `001_v02_foundation_corpus.py` e `002_v02_postgresql_fts.py`;
- `tests/integration/test_v02_corpus_postgresql.py`.

## Base e sessão

SQLAlchemy mapeia objetos Python para tabelas. Alembic versiona alterações do
schema sem recriar o banco. Crie a base declarativa:

```python
# src/consultor_juridico/db/base.py
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

O recorte didático abaixo mostra a composição mínima. A tag também adapta
`db:5432` para `localhost:5434` quando executada fora do Compose e expõe
`get_db`/`set_verbose`:

```python
# src/consultor_juridico/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from consultor_juridico.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

## Entidades e contratos

```text
Source → SourceSnapshot → ActVersion ← LegalAct
                           ↓
                     Provision (self-parent)
                           ↑
             SearchUnitProvision ← SearchUnit
```

Use UUID nas PKs. O recorte literal abaixo mostra as identidades centrais:

```python
class ActVersionModel(Base):
    __tablename__ = "act_versions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    legal_act_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("legal_acts.id", ondelete="RESTRICT"), nullable=False
    )
    source_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    projection_name: Mapped[str] = mapped_column(String(100), nullable=False)
    projection_version: Mapped[str] = mapped_column(String(40), nullable=False)
    version_hash: Mapped[str] = mapped_column(String(64), nullable=False)
```

`ProvisionModel` acrescenta `stable_key`, `provision_type`, `number_label`,
`parent_id`, `document_order`, `citation_text`, `source_locator`, `content_hash`
e `legal_status`. `SearchUnitModel` guarda `unit_key`, `search_text` e hash; a
tabela associativa registra provisions e sua `position`.

## Migration 001

A migration deve garantir, no banco e não apenas em Python:

- unicidade de source URL, snapshot SHA e act code;
- SHA/hash hexadecimal de 64 caracteres;
- snapshot imutável por trigger contra UPDATE/DELETE;
- identidade natural da ActVersion;
- `document_order >= 1` e único na versão;
- FK composta `(parent_id, act_version_id)` para pai na mesma versão;
- JSON locator com `paragraph_start` e `paragraph_end`;
- SearchUnit e Provision sempre da mesma versão.

Um recorte representativo da integridade hierárquica:

```python
op.create_foreign_key(
    "fk_provisions_parent_same_version",
    "provisions",
    "provisions",
    ["parent_id", "act_version_id"],
    ["id", "act_version_id"],
    ondelete="CASCADE",
)
```

A migration 002 cria o índice que usaremos no capítulo 7:

```sql
CREATE INDEX ix_search_units_fts_portuguese
ON search_units
USING gin (to_tsvector('portuguese'::regconfig, search_text));
```

## Testes e execução

Use um banco descartável e teste upgrade, downgrade, constraints e triggers.
Nunca execute testes destrutivos no volume principal.

```bash
docker compose run --rm app alembic upgrade head
docker compose exec db psql -U consultor -d consultor_juridico_v02 -c '\dt'
V02_TEST_DATABASE_URL=postgresql+psycopg://... uv run pytest \
  tests/integration/test_v02_corpus_postgresql.py -q
```

Espere oito tabelas mais `alembic_version`; o head é
`002_v02_postgresql_fts`.

## Erros comuns e decisões

Não use `Base.metadata.create_all` como substituto de migrations. Não modele
Evidence/Claim persistidos: no MVP2 são contratos em memória. A imutabilidade
de snapshot e a segurança de versão pertencem ao banco.

## Checkpoint

Upgrade em banco descartável, `alembic current` no head, testes de FK/trigger
verdes e nenhuma linha de corpus ainda criada.

**Anterior:** [infraestrutura](02-infrastructure.md).  
**Próximo:** [corpus](04-corpus.md).
