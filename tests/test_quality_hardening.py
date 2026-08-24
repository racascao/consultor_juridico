"""Regressões do hardening fail-closed da Fase 7.1."""

import uuid
from dataclasses import replace
from types import SimpleNamespace

from consultor_juridico.consultation.selection import select_evidence_candidates
from consultor_juridico.consultation.semantic import (
    OllamaSemanticSupportValidator,
    build_semantic_support_prompt,
    parse_semantic_support,
)
from consultor_juridico.consultation.sufficiency import assess_evidence_sufficiency
from consultor_juridico.consultation.types import (
    GeneratedClaim,
    GeneratedResponse,
    SemanticSupportStatus,
    SufficiencyDecision,
)
from consultor_juridico.retrieval import RetrievalCandidate


def _candidate(
    label: str,
    *,
    provision: uuid.UUID | None = None,
    lexical: float = 0.4,
    vector: float = 0.72,
) -> RetrievalCandidate:
    identifier = uuid.uuid5(uuid.NAMESPACE_URL, label)
    return RetrievalCandidate(
        chunk_id=identifier,
        legal_element_id=uuid.uuid4(),
        legal_provision_id=provision or uuid.uuid4(),
        legal_act="CF/88",
        element_type="CAPUT",
        number_label=label,
        identity_key=f"CF88/@root/ARTICLE:{label}/CAPUT:@caput",
        chunk_text=f"Texto constitucional {label}",
        lexical_rank=1,
        lexical_score=lexical,
        vector_rank=1,
        vector_score=vector,
        rrf_score=0.03,
    )


def _evidence(code: str, text: str, *, parent_context: str | None = None):
    return SimpleNamespace(
        evidence_code=code,
        text_snapshot=text,
        validation_metadata={"parent_context": parent_context},
    )


def _semantic_value(status: str, evidence_code: str = "EV001"):
    supported = status in {"SUPPORTED", "PARTIALLY_SUPPORTED"}
    return {
        "claim_id": "C1",
        "has_supported_material": supported,
        "all_material_supported": status == "SUPPORTED",
        "contradicted": False,
        "evidence_ids": [evidence_code],
        "reason": "Classificação de teste.",
    }


def test_evidence_selection_deduplicates_provision_and_preserves_best_occurrence():
    provision = uuid.uuid4()
    first = _candidate("5", provision=provision)
    duplicate = _candidate("5-duplicate", provision=provision)
    other = _candidate("6")
    selected = select_evidence_candidates((first, duplicate, other), limit=2)
    assert selected == (first, other)
    assert selected[0].chunk_id == first.chunk_id


def test_evidence_selection_is_deterministic_and_bounded():
    candidates = tuple(_candidate(str(index)) for index in range(8))
    assert select_evidence_candidates(candidates, limit=3) == candidates[:3]


def test_evidence_selection_filters_lexical_noise_but_keeps_top_candidate():
    relevant = _candidate("2")
    relevant = replace(
        relevant, chunk_text="Poderes da União independentes e harmônicos"
    )
    noise = _candidate("37")
    selected = select_evidence_candidates(
        (relevant, noise),
        question="Quais são os Poderes da União independentes e harmônicos?",
    )
    assert selected == (relevant,)


def test_evidence_selection_uses_parent_context_without_changing_snapshot():
    relevant = replace(
        _candidate("relevant"),
        chunk_text="de caráter perpétuo",
        parent_context="não haverá penas",
    )
    noise = replace(_candidate("noise"), chunk_text="prisão preventiva")
    selected = select_evidence_candidates(
        (noise, relevant), question="prisão perpétua", limit=1
    )
    assert relevant in selected
    assert relevant.chunk_text == "de caráter perpétuo"


def test_evidence_selection_keeps_ranked_candidate_without_contextual_overlap():
    first = replace(_candidate("first"), chunk_text="texto tematicamente próximo")
    selected = select_evidence_candidates((first,), question="consulta abstrata")
    assert selected == (first,)


def test_sufficiency_accepts_strong_constitutional_evidence():
    report = assess_evidence_sufficiency(
        "Quais são os Poderes da União?", (_candidate("2"),)
    )
    assert report.decision is SufficiencyDecision.SUFFICIENT


def test_sufficiency_rejects_weak_evidence_before_llm():
    report = assess_evidence_sufficiency(
        "Pergunta sem relação", (_candidate("x", lexical=0.1, vector=0.5),)
    )
    assert report.decision is SufficiencyDecision.INSUFFICIENT


def test_sufficiency_rejects_three_known_out_of_corpus_domains():
    candidate = _candidate("5")
    for question in (
        "Como preparar um bolo de chocolate?",
        "Quem venceu a última Copa do Mundo?",
        "Como ordenar uma lista em Python?",
    ):
        assert not assess_evidence_sufficiency(question, (candidate,)).is_sufficient


def test_sufficiency_rejects_underspecified_personal_case():
    report = assess_evidence_sufficiency(
        "Quais são todos os meus direitos neste caso?", (_candidate("5"),)
    )
    assert not report.is_sufficient


def test_semantic_prompt_contains_only_claim_and_its_evidence():
    response = GeneratedResponse(
        "",
        (GeneratedClaim("C1", "A manifestação é livre.", ("EV001",)),),
    )
    prompt = build_semantic_support_prompt(
        response, (_evidence("EV001", "é livre a manifestação do pensamento"),)
    )
    assert "CLAIM C1" in prompt
    assert "EV001" in prompt
    assert "PERGUNTA" not in prompt


def test_semantic_prompt_preserves_structural_parent_context():
    response = GeneratedResponse(
        "",
        (GeneratedClaim("C1", "Não haverá pena perpétua.", ("EV001",)),),
    )
    prompt = build_semantic_support_prompt(
        response,
        (
            _evidence(
                "EV001",
                "de caráter perpétuo;",
                parent_context="não haverá penas:",
            ),
        ),
    )
    assert "[EV001] de caráter perpétuo;" in prompt
    assert "Contexto estrutural: não haverá penas:" in prompt


def test_semantic_validator_accepts_supported_claim():
    response = GeneratedResponse("", (GeneratedClaim("C1", "Afirmação", ("EV001",)),))
    report = parse_semantic_support(
        {"claims": [_semantic_value("SUPPORTED")]},
        response,
        (_evidence("EV001", "Afirmação"),),
    )
    assert report.is_valid
    assert report.claims[0].status is SemanticSupportStatus.SUPPORTED


def test_semantic_validator_rejects_partial_contradicted_and_unrelated_claims():
    response = GeneratedResponse("", (GeneratedClaim("C1", "Afirmação", ("EV001",)),))
    for status in ("PARTIALLY_SUPPORTED", "UNSUPPORTED"):
        report = parse_semantic_support(
            {"claims": [_semantic_value(status)]},
            response,
            (_evidence("EV001", "Texto irrelevante ou contraditório"),),
        )
        assert not report.is_valid


def test_semantic_validator_rejects_invented_evidence_and_omitted_claim():
    response = GeneratedResponse("", (GeneratedClaim("C1", "Afirmação", ("EV001",)),))
    invented = parse_semantic_support(
        {"claims": [_semantic_value("SUPPORTED", "EV999")]},
        response,
        (_evidence("EV001", "Texto"),),
    )
    omitted = parse_semantic_support(
        {"claims": []}, response, (_evidence("EV001", "Texto"),)
    )
    assert not invented.is_valid
    assert not omitted.is_valid


def test_semantic_supported_without_material_lexical_anchor_is_vetoed():
    response = GeneratedResponse(
        "", (GeneratedClaim("C1", "Uma lista Python usa sorted", ("EV001",)),)
    )
    report = parse_semantic_support(
        {"claims": [_semantic_value("SUPPORTED")]},
        response,
        (_evidence("EV001", "Todos são iguais perante a lei"),),
    )
    assert not report.is_valid
    assert report.claims[0].status is SemanticSupportStatus.UNSUPPORTED


def test_semantic_contradiction_is_unsupported_even_with_supported_material():
    response = GeneratedResponse("", (GeneratedClaim("C1", "Afirmação", ("EV001",)),))
    value = _semantic_value("SUPPORTED")
    value["contradicted"] = True
    report = parse_semantic_support(
        {"claims": [value]}, response, (_evidence("EV001", "Afirmação"),)
    )
    assert not report.is_valid
    assert report.claims[0].status is SemanticSupportStatus.UNSUPPORTED


def test_semantic_invalid_boolean_decision_is_fail_closed():
    response = GeneratedResponse("", (GeneratedClaim("C1", "Afirmação", ("EV001",)),))
    value = _semantic_value("SUPPORTED")
    value["has_supported_material"] = False
    report = parse_semantic_support(
        {"claims": [value]}, response, (_evidence("EV001", "Afirmação"),)
    )
    assert not report.is_valid
    assert report.technical_error


def test_semantic_technical_failure_is_fail_closed(monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("indisponível")

    monkeypatch.setattr("httpx.post", fail)
    validator = OllamaSemanticSupportValidator("http://ollama", "model", 1)
    response = GeneratedResponse("", (GeneratedClaim("C1", "Afirmação", ("EV001",)),))
    report = validator.validate(response, (_evidence("EV001", "Texto"),))
    assert not report.is_valid
    assert report.technical_error
