"""Configurações da aplicação utilizando Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações centralizadas do Consultor Jurídico."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    env: str = Field(default="development", alias="ENV")
    debug: bool = Field(default=True, alias="DEBUG")

    # PostgreSQL + pgvector
    postgres_user: str = Field(default="consultor", alias="POSTGRES_USER")
    postgres_password: str = Field(default="consultor_pass", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="consultor_juridico", alias="POSTGRES_DB")
    postgres_host: str = Field(default="db", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    database_url: str = Field(
        default="postgresql+psycopg://consultor:consultor_pass@db:5432/consultor_juridico",
        alias="DATABASE_URL",
    )

    # Ollama runtime. EBCG v2 does not use a free-form legal generator; these
    # settings configure the conservative semantic judge and its fallback.
    ollama_base_url: str = Field(default="http://ollama:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="ministral-3:8b", alias="OLLAMA_MODEL")
    semantic_judge_model: str | None = Field(default=None, alias="SEMANTIC_JUDGE_MODEL")
    embedding_model: str = Field(default="nomic-embed-text", alias="EMBEDDING_MODEL")
    embedding_timeout: float = Field(default=120.0, alias="EMBEDDING_TIMEOUT")
    embedding_batch_size: int = Field(default=32, alias="EMBEDDING_BATCH_SIZE")
    consultation_timeout: float = Field(default=180.0, alias="CONSULTATION_TIMEOUT")
    consultation_top_k: int = Field(default=10, alias="CONSULTATION_TOP_K")
    consultation_max_attempts: int = Field(default=2, alias="CONSULTATION_MAX_ATTEMPTS")
    consultation_evidence_limit: int = Field(
        default=3, alias="CONSULTATION_EVIDENCE_LIMIT"
    )

    # Aquisição documental HTTP
    ingestion_connect_timeout: float = Field(
        default=10.0, alias="INGESTION_CONNECT_TIMEOUT"
    )
    ingestion_read_timeout: float = Field(default=30.0, alias="INGESTION_READ_TIMEOUT")
    ingestion_write_timeout: float = Field(
        default=10.0, alias="INGESTION_WRITE_TIMEOUT"
    )
    ingestion_pool_timeout: float = Field(default=10.0, alias="INGESTION_POOL_TIMEOUT")
    ingestion_max_attempts: int = Field(default=3, alias="INGESTION_MAX_ATTEMPTS")
    ingestion_backoff_seconds: float = Field(
        default=0.5, alias="INGESTION_BACKOFF_SECONDS"
    )
    ingestion_retry_after_max_seconds: float = Field(
        default=5.0, alias="INGESTION_RETRY_AFTER_MAX_SECONDS"
    )
    ingestion_min_bytes: int = Field(default=1024, alias="INGESTION_MIN_BYTES")
    ingestion_max_bytes: int = Field(
        default=10 * 1024 * 1024, alias="INGESTION_MAX_BYTES"
    )
    planalto_user_agent: str = Field(
        default=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "Chrome/151 Safari/537.36"
        ),
        alias="PLANALTO_USER_AGENT",
    )


settings = Settings()
