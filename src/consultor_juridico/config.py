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

    # Ollama LLM Runtime
    ollama_base_url: str = Field(default="http://ollama:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.2", alias="OLLAMA_MODEL")


settings = Settings()
