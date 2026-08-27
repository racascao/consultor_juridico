"""Regressões do orquestrador de consulta sem I/O de modelo local."""

import uuid
from types import SimpleNamespace

from consultor_juridico.consultation.errors import LLMResponseError
from consultor_juridico.consultation.service import ABSTENTION, run_consultation
from consultor_juridico.consultation.types import (
    GeneratedClaim,
    GeneratedResponse,
    SufficiencyDecision,
    SufficiencyReport,
    ValidationReport,
)


class _Session:
    def commit(self) -> None:
        pass

    def refresh(self, _value) -> None:
        pass


class _Generator:
    generation_mode = "EBCG_V2"

    def __init__(self, response: GeneratedResponse | None = None) -> None:
        self.response = response

    def generate(self, *_args, **_kwargs) -> GeneratedResponse:
        if self.response is None:
            raise LLMResponseError("contrato inválido")
        return self.response


def _sufficiency() -> SufficiencyReport:
    return SufficiencyReport(
        SufficiencyDecision.SUFFICIENT,
        (),
        lexical_score=1.0,
        vector_score=1.0,
        retriever_agreement=2,
    )


def _configure_sufficient_flow(monkeypatch) -> None:
    evidence_set = SimpleNamespace(
        id=uuid.uuid4(),
        items=[SimpleNamespace(evidence_code="EV001")],
        metadata_json={},
        validation_status=None,
    )
    monkeypatch.setattr(
        "consultor_juridico.consultation.service.select_evidence_candidates_with_diagnostics",
        lambda *_args, **_kwargs: SimpleNamespace(
            candidates=(object(),), diagnostics=()
        ),
    )
    monkeypatch.setattr(
        "consultor_juridico.consultation.service.assess_evidence_sufficiency",
        lambda *_args, **_kwargs: _sufficiency(),
    )
    monkeypatch.setattr(
        "consultor_juridico.consultation.service.build_evidence_set",
        lambda *_args, **_kwargs: evidence_set,
    )


def test_validation_abstention_preserves_structured_polarity_stage(monkeypatch) -> None:
    _configure_sufficient_flow(monkeypatch)
    response = GeneratedResponse(
        "claim",
        (GeneratedClaim("C1", "claim", ("EV001",)),),
    )
    monkeypatch.setattr(
        "consultor_juridico.consultation.service.deterministically_attribute",
        lambda *_args: SimpleNamespace(
            abstained=False, diagnostics=(), response=response
        ),
    )
    monkeypatch.setattr(
        "consultor_juridico.consultation.service.validate_response_locators",
        lambda *_args, **_kwargs: SimpleNamespace(valid=True, errors=()),
    )
    monkeypatch.setattr(
        "consultor_juridico.consultation.service.validate_citations",
        lambda *_args: ValidationReport(True, (), 1, 1),
    )
    monkeypatch.setattr(
        "consultor_juridico.consultation.service.validate_response_polarity",
        lambda *_args: SimpleNamespace(results=(object(),), errors=("polaridade",)),
    )
    monkeypatch.setattr(
        "consultor_juridico.consultation.service.can_route_to_semantic",
        lambda _result: False,
    )

    result = run_consultation(
        _Session(),
        "prisão perpétua",
        retriever=lambda _question: (),
        generator=_Generator(response),
        model_name="unused",
        semantic_validator=object(),
        max_generation_attempts=1,
    )

    assert result.outcome.value == "ABSTAINED"
    assert result.answer == ABSTENTION
    assert result.claims == ()
    assert result.citations == ()
    assert result.validation_errors == ("polaridade",)
    assert result.validation_stage == "POLARITY_VALIDATION"
    assert result.sufficiency == _sufficiency()


def test_validation_abstention_uses_fallback_when_stage_is_absent(monkeypatch) -> None:
    _configure_sufficient_flow(monkeypatch)

    result = run_consultation(
        _Session(),
        "pergunta",
        retriever=lambda _question: (),
        generator=_Generator(),
        model_name="unused",
        semantic_validator=object(),
        max_generation_attempts=1,
    )

    assert result.outcome.value == "ABSTAINED"
    assert result.answer == ABSTENTION
    assert result.validation_stage == "VALIDATION_ABSTENTION"
    assert result.validation_errors == ("contrato inválido",)
    assert result.sufficiency == _sufficiency()
