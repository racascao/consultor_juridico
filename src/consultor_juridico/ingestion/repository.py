"""Persistência transacional de fontes e capturas documentais."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from consultor_juridico.ingestion.types import DownloadedDocument
from consultor_juridico.models import Source, SourceDocument


@dataclass(frozen=True, slots=True)
class StoredDocument:
    """Documento resolvido junto com a indicação de criação."""

    document: SourceDocument
    created: bool


class SourceDocumentRepository:
    """Repository de Source e SourceDocument sem política HTTP."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_source(
        self, *, name: str, base_url: str, description: str
    ) -> Source:
        """Resolve a fonte por base_url, inclusive sob inserção concorrente."""
        existing = self.session.scalar(
            select(Source).where(Source.base_url == base_url)
        )
        if existing is not None:
            return existing

        source = Source(name=name, base_url=base_url, description=description)
        try:
            with self.session.begin_nested():
                self.session.add(source)
                self.session.flush()
            return source
        except IntegrityError:
            concurrent = self.session.scalar(
                select(Source).where(Source.base_url == base_url)
            )
            if concurrent is None:
                raise
            return concurrent

    def store_document(
        self,
        *,
        source: Source,
        sha256: str,
        download: DownloadedDocument,
        adapter_version: str,
    ) -> StoredDocument:
        """Persiste uma captura nova ou retorna a conhecida pela fonte e hash."""
        existing = self._find_document(source.id, sha256)
        if existing is not None:
            return StoredDocument(existing, created=False)

        document = SourceDocument(
            source_id=source.id,
            url_source=download.requested_url,
            raw_bytes=download.canonical_bytes,
            content_hash_sha256=sha256,
            fetched_at=datetime.now(UTC),
            http_headers=[list(item) for item in download.headers],
            metadata_json=download.metadata(adapter_version=adapter_version),
        )
        try:
            with self.session.begin_nested():
                self.session.add(document)
                self.session.flush()
            return StoredDocument(document, created=True)
        except IntegrityError:
            concurrent = self._find_document(source.id, sha256)
            if concurrent is None:
                raise
            return StoredDocument(concurrent, created=False)

    def list_documents(self) -> list[SourceDocument]:
        """Lista capturas da mais recente para a mais antiga."""
        statement = select(SourceDocument).order_by(SourceDocument.fetched_at.desc())
        return list(self.session.scalars(statement))

    def get_latest_document(
        self, *, source_id, url_source: str
    ) -> SourceDocument | None:
        """Recupera a captura mais recente de uma fonte e URL solicitada."""
        statement = (
            select(SourceDocument)
            .where(
                SourceDocument.source_id == source_id,
                SourceDocument.url_source == url_source,
            )
            .order_by(SourceDocument.fetched_at.desc(), SourceDocument.id.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def _find_document(self, source_id, sha256: str) -> SourceDocument | None:
        return self.session.scalar(
            select(SourceDocument).where(
                SourceDocument.source_id == source_id,
                SourceDocument.content_hash_sha256 == sha256,
            )
        )
