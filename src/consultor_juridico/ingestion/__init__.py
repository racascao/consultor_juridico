"""Aquisição e armazenamento imutável de documentos oficiais."""

from consultor_juridico.ingestion.service import (
    IngestionService,
    get_ingestion_status,
    run_planalto_ingestion,
)

__all__ = ["IngestionService", "get_ingestion_status", "run_planalto_ingestion"]
