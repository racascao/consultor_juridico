"""Testes para o módulo de configurações."""

from consultor_juridico.config import Settings


def test_default_settings():
    """Testa se as configurações padrão são carregadas corretamente."""
    settings = Settings()
    assert settings.env in ("development", "test", "production")
    assert settings.postgres_port == 5432
    assert "postgresql+psycopg" in settings.database_url
    assert settings.ollama_base_url.startswith("http")
    assert settings.embedding_model == "nomic-embed-text"
    assert settings.embedding_batch_size == 32
    assert settings.planalto_user_agent == (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/151 Safari/537.36"
    )


def test_planalto_user_agent_can_be_overridden(monkeypatch):
    monkeypatch.setenv("PLANALTO_USER_AGENT", "custom-agent")
    assert Settings().planalto_user_agent == "custom-agent"


def test_embedding_settings_can_be_overridden(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "custom-embedding")
    monkeypatch.setenv("EMBEDDING_TIMEOUT", "45")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "8")
    configured = Settings()
    assert configured.embedding_model == "custom-embedding"
    assert configured.embedding_timeout == 45
    assert configured.embedding_batch_size == 8
