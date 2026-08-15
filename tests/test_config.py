"""Testes para o módulo de configurações."""

from consultor_juridico.config import Settings


def test_default_settings():
    """Testa se as configurações padrão são carregadas corretamente."""
    settings = Settings()
    assert settings.env in ("development", "test", "production")
    assert settings.postgres_port == 5432
    assert "postgresql+psycopg" in settings.database_url
    assert settings.ollama_base_url.startswith("http")
    assert settings.planalto_user_agent == (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/151 Safari/537.36"
    )


def test_planalto_user_agent_can_be_overridden(monkeypatch):
    monkeypatch.setenv("PLANALTO_USER_AGENT", "custom-agent")
    assert Settings().planalto_user_agent == "custom-agent"
