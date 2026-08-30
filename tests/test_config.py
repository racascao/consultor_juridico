"""Testes para o módulo de configurações."""

from consultor_juridico.config import Settings


def test_default_settings():
    """Testa se as configurações padrão são carregadas corretamente."""
    settings = Settings(_env_file=None)
    assert settings.env in ("development", "test", "production")
    assert settings.postgres_port == 5432
    assert "postgresql+psycopg" in settings.database_url
    assert settings.ollama_base_url.startswith("http")
    assert settings.ollama_consultation_model == "ministral-3:3b"
    assert settings.ollama_embedding_model == "nomic-embed-text"
    assert settings.embedding_dimensions == 768
    assert settings.retrieval_limit == 10
    assert settings.planalto_user_agent == (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/151 Safari/537.36"
    )


def test_planalto_user_agent_can_be_overridden(monkeypatch):
    monkeypatch.setenv("PLANALTO_USER_AGENT", "custom-agent")
    assert Settings().planalto_user_agent == "custom-agent"


def test_embedding_settings_can_be_overridden(monkeypatch):
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "custom-embedding")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "45")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "384")
    configured = Settings()
    assert configured.ollama_embedding_model == "custom-embedding"
    assert configured.ollama_timeout == 45
    assert configured.embedding_dimensions == 384


def test_consultation_and_embedding_models_can_be_configured(monkeypatch):
    monkeypatch.setenv("OLLAMA_CONSULTATION_MODEL", "consultation-model")
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "embedding-model")

    configured = Settings()

    assert configured.ollama_consultation_model == "consultation-model"
    assert configured.ollama_embedding_model == "embedding-model"
