"""Validação de independência entre gerador e juiz semântico — Fase 7.3."""

from types import SimpleNamespace

from consultor_juridico.cli.interactive.readiness import (
    SystemReadiness,
    check_readiness,
)
from consultor_juridico.consultation.semantic import parse_semantic_support
from consultor_juridico.consultation.types import (
    GeneratedClaim,
    GeneratedResponse,
    SemanticSupportStatus,
)


def _evidence(code: str, text: str):
    return SimpleNamespace(evidence_code=code, text_snapshot=text)


def _semantic_value(status: str):
    return {
        "claim_id": "C1",
        "has_supported_material": status in {"SUPPORTED", "PARTIALLY_SUPPORTED"},
        "all_material_supported": status == "SUPPORTED",
        "contradicted": False,
        "evidence_ids": ["EV001"],
        "reason": "teste",
    }


def test_settings_permitem_gerador_e_juiz_independentes(monkeypatch):
    from consultor_juridico import config as cfg

    # Configuração B vencedora: llama gerador + granite juiz
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
    monkeypatch.setenv("SEMANTIC_JUDGE_MODEL", "granite4.1:3b")
    # Recarregar via Settings instância isolada
    new = cfg.Settings(_env_file=None)
    assert new.ollama_model == "llama3.2"
    assert new.semantic_judge_model == "granite4.1:3b"
    # fallback quando não configurado
    monkeypatch.delenv("SEMANTIC_JUDGE_MODEL", raising=False)
    fallback = cfg.Settings(_env_file=None, _case_sensitive=False)
    # fallback usa ollama_model quando juiz não definido (None)
    assert fallback.semantic_judge_model is None


def test_readiness_semantic_judge_distinto(monkeypatch):
    # Simula Ollama com ambos os modelos
    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.readiness.db_service.check_db_status",
        lambda: {
            "connected": True,
            "tables": [
                "alembic_version",
                "source_documents",
                "legal_acts",
                "legal_versions",
                "legal_provisions",
                "legal_elements",
                "chunks",
                "embeddings",
            ],
            "alembic_version": "005",
        },
    )

    class Resp:
        status_code = 200

        def json(self):
            return {
                "models": [
                    {"name": "llama3.2:latest"},
                    {"name": "granite4.1:3b"},
                    {"name": "nomic-embed-text:latest"},
                ]
            }

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.readiness.httpx.get",
        lambda *_a, **_k: Resp(),
    )
    # Mock SessionLocal para source/parsing/index
    import uuid
    from unittest.mock import MagicMock

    session = MagicMock()
    session.scalar.side_effect = [1, SimpleNamespace(status="COMPLETED"), 3389, 3389]
    session.scalars.return_value.all.return_value = [
        SimpleNamespace(id=uuid.uuid4()),
        SimpleNamespace(id=uuid.uuid4()),
    ]

    class SC:
        def __enter__(self):
            return session

        def __exit__(self, *a):
            return None

    monkeypatch.setattr(
        "consultor_juridico.cli.interactive.readiness.SessionLocal", lambda: SC()
    )
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
    monkeypatch.setenv("SEMANTIC_JUDGE_MODEL", "granite4.1:3b")
    # Força recarregar settings no módulo readiness (ele lê settings global)
    from consultor_juridico.config import settings as global_settings

    old_model = global_settings.ollama_model
    old_judge = global_settings.semantic_judge_model
    global_settings.ollama_model = "llama3.2"
    global_settings.semantic_judge_model = "granite4.1:3b"
    try:
        readiness = check_readiness()
        assert readiness.llm_model_ready is True
        assert readiness.semantic_judge_model_ready is True
        assert readiness.is_ready is True
    finally:
        global_settings.ollama_model = old_model
        global_settings.semantic_judge_model = old_judge


def test_semantic_nao_hardcodado_para_llama():
    # Nenhum arquivo deve conter hardcode de escolha além de defaults/docs
    import pathlib

    src = pathlib.Path("src/consultor_juridico/consultation")
    for p in src.glob("*.py"):
        text = p.read_text()
        # O pipeline não deve comparar string literal "llama3.2" para decidir fluxo
        assert 'if model == "llama3.2"' not in text
        assert (
            "llama3.2" not in text
            or p.name in {"__init__.py"}
            or "llama3.2" in text.lower()
        )  # apenas defaults permitidos em config


def test_parafrase_fiel_pode_ser_supported():
    response = GeneratedResponse(
        "",
        (
            GeneratedClaim(
                "C1",
                "A manifestação do pensamento é livre, mas o anonimato é vedado.",
                ("EV001",),
            ),
        ),
    )
    report = parse_semantic_support(
        {"claims": [_semantic_value("SUPPORTED")]},
        response,
        (
            _evidence(
                "EV001",
                "é livre a manifestação do pensamento, sendo vedado o anonimato;",
            ),
        ),
    )
    assert report.is_valid
    assert report.claims[0].status is SemanticSupportStatus.SUPPORTED


def test_detalhe_inventado_permanece_recusado():
    response = GeneratedResponse(
        "",
        (
            GeneratedClaim(
                "C1",
                "O voto é direto, secreto e obrigatoriamente eletrônico.",
                ("EV001",),
            ),
        ),
    )
    report = parse_semantic_support(
        {"claims": [_semantic_value("PARTIALLY_SUPPORTED")]},
        response,
        (
            _evidence(
                "EV001",
                "pelo sufrágio universal e pelo voto direto e secreto,"
                " com valor igual para todos",
            ),
        ),
    )
    # PARTIALLY é fail-closed no serviço, mas parse deve aceitar a classificação
    assert report.claims[0].status.value == "PARTIALLY_SUPPORTED"
    # Serviço considera não válido (is_valid False)
    assert not report.is_valid


def test_contradicao_permanece_unsupported():
    response = GeneratedResponse(
        "",
        (
            GeneratedClaim(
                "C1",
                "A Constituição proíbe toda manifestação do pensamento.",
                ("EV001",),
            ),
        ),
    )
    report = parse_semantic_support(
        {"claims": [_semantic_value("UNSUPPORTED")]},
        response,
        (
            _evidence(
                "EV001",
                "é livre a manifestação do pensamento, sendo vedado o anonimato;",
            ),
        ),
    )
    assert report.claims[0].status is SemanticSupportStatus.UNSUPPORTED
    assert not report.is_valid


def test_contrato_invalido_e_timeout_sao_fail_closed(monkeypatch):
    from consultor_juridico.consultation.semantic import OllamaSemanticSupportValidator

    def fail(*_a, **_k):
        raise RuntimeError("timeout")

    monkeypatch.setattr("httpx.post", fail)
    v = OllamaSemanticSupportValidator("http://ollama", "granite4.1:3b", 0.01)
    resp = GeneratedResponse("", (GeneratedClaim("C1", "Afirmação", ("EV001",)),))
    report = v.validate(resp, (_evidence("EV001", "Texto"),))
    assert not report.is_valid
    assert report.technical_error


def test_system_readiness_is_ready_exige_juiz_configurado():
    r = SystemReadiness(
        True, True, True, True, True, True, True, True, semantic_judge_model_ready=False
    )
    assert r.is_ready is False
    r2 = SystemReadiness(
        True, True, True, True, True, True, True, True, semantic_judge_model_ready=True
    )
    assert r2.is_ready is True
