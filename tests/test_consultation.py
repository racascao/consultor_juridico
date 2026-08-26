"""Testes unitários de validação da consulta jurídica."""

import uuid
from types import SimpleNamespace

import pytest

from consultor_juridico.consultation.types import GeneratedClaim, GeneratedResponse
from consultor_juridico.consultation.validator import validate_citations


def test_validator_accepts_clean_abstention_without_database_access():
    evidence_set = SimpleNamespace(id=uuid.uuid4(), items=[])
    response = GeneratedResponse("Não há evidência suficiente.", (), abstain=True)
    report = validate_citations(SimpleNamespace(), evidence_set, response)
    assert report.is_valid


def test_validator_rejects_claim_without_citation():
    evidence_set = SimpleNamespace(id=uuid.uuid4(), items=[])
    response = GeneratedResponse(
        "Resposta",
        (GeneratedClaim("C1", "Afirmação", ()),),
    )
    report = validate_citations(SimpleNamespace(), evidence_set, response)
    assert not report.is_valid
    assert "sem citação" in report.errors[0]


def test_validator_rejects_evidence_from_another_set():
    set_id = uuid.uuid4()
    item = SimpleNamespace(
        evidence_code="EV001",
        evidence_set_id=uuid.uuid4(),
        is_validated=True,
    )
    evidence_set = SimpleNamespace(id=set_id, items=[item])
    response = GeneratedResponse("", (GeneratedClaim("C1", "Afirmação", ("EV001",)),))
    report = validate_citations(SimpleNamespace(), evidence_set, response)
    assert not report.is_valid
    assert "não pertence" in report.errors[0]


def test_validator_rejects_unvalidated_evidence():
    set_id = uuid.uuid4()
    item = SimpleNamespace(
        evidence_code="EV001", evidence_set_id=set_id, is_validated=False
    )
    evidence_set = SimpleNamespace(id=set_id, items=[item])
    response = GeneratedResponse("", (GeneratedClaim("C1", "Afirmação", ("EV001",)),))
    report = validate_citations(SimpleNamespace(), evidence_set, response)
    assert not report.is_valid


@pytest.mark.parametrize(
    ("row", "expected_error"),
    [
        (None, "Cadeia documental inválida"),
        (
            SimpleNamespace(chunk_text="alterado", url_source="https://fonte"),
            "Snapshot divergente",
        ),
        (
            SimpleNamespace(chunk_text="snapshot", url_source="https://outra"),
            "URL oficial divergente",
        ),
    ],
)
def test_validator_rejects_broken_physical_chain(row, expected_error):
    set_id = uuid.uuid4()
    item = SimpleNamespace(
        evidence_code="EV001",
        evidence_set_id=set_id,
        is_validated=True,
        chunk_id=uuid.uuid4(),
        legal_element_id=uuid.uuid4(),
        text_snapshot="snapshot",
        source_url="https://fonte",
    )

    class Result:
        def one_or_none(self):
            return row

    session = SimpleNamespace(execute=lambda _statement: Result())
    evidence_set = SimpleNamespace(id=set_id, items=[item])
    response = GeneratedResponse("", (GeneratedClaim("C1", "Afirmação", ("EV001",)),))
    report = validate_citations(session, evidence_set, response)
    assert not report.is_valid
    assert any(expected_error in error for error in report.errors)
