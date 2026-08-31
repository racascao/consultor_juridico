"""Testes para o módulo de configurações."""

from consultor_juridico.config import Settings


def test_default_settings():
    """Testa se as configurações padrão são carregadas corretamente."""
    settings = Settings(_env_file=None)
    assert settings.env in ("development", "test", "production")
    assert settings.postgres_port == 5432
    assert settings.postgres_db == "consultor_juridico_v02"
    assert "postgresql+psycopg" in settings.database_url
    assert settings.ingestion_read_timeout == 30
    assert settings.planalto_user_agent == (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/151 Safari/537.36"
    )


def test_planalto_user_agent_can_be_overridden(monkeypatch):
    monkeypatch.setenv("PLANALTO_USER_AGENT", "custom-agent")
    assert Settings().planalto_user_agent == "custom-agent"


def test_ingestion_settings_can_be_overridden(monkeypatch):
    monkeypatch.setenv("INGESTION_READ_TIMEOUT", "45")
    monkeypatch.setenv("INGESTION_MAX_BYTES", "2048")
    configured = Settings()
    assert configured.ingestion_read_timeout == 45
    assert configured.ingestion_max_bytes == 2048
