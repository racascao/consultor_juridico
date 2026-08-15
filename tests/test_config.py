"""Testes para o módulo de configurações."""

from consultor_juridico.config import Settings


def test_default_settings():
    """Testa se as configurações padrão são carregadas corretamente."""
    settings = Settings()
    assert settings.env in ("development", "test", "production")
    assert settings.postgres_port == 5432
    assert "postgresql+psycopg" in settings.database_url
    assert settings.ollama_base_url.startswith("http")
