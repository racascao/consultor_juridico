"""Fronteiras determinísticas da Fase 11.1."""

import uuid
from dataclasses import replace
from types import SimpleNamespace

from consultor_juridico.consultation.attribution import (
    deterministically_attribute,
    split_claim_clauses,
)
from consultor_juridico.consultation.selection import (
    select_evidence_candidates,
    select_evidence_candidates_with_diagnostics,
)
from consultor_juridico.consultation.types import (
    AttributionMode,
    AttributionStatus,
    GeneratedClaim,
    GeneratedResponse,
)
from consultor_juridico.retrieval import RetrievalCandidate


def candidate(label: str, text: str, *, provision=None, parent=None):
    return RetrievalCandidate(
        chunk_id=uuid.uuid5(uuid.NAMESPACE_URL, label),
        legal_element_id=uuid.uuid5(uuid.NAMESPACE_OID, label),
        legal_provision_id=provision or uuid.uuid5(uuid.NAMESPACE_DNS, label),
        legal_act="CF/88",
        element_type="CAPUT",
        number_label=label,
        identity_key=f"CF88/@root/ARTICLE:{label}/CAPUT:@caput",
        chunk_text=text,
        lexical_rank=1,
        lexical_score=0.4,
        vector_rank=1,
        vector_score=0.7,
        rrf_score=0.03,
        parent_context=parent,
    )


def evidence(code: str, text: str, *, parent=None):
    return SimpleNamespace(
        evidence_code=code,
        text_snapshot=text,
        validation_metadata={"parent_context": parent},
    )


def response(text: str, codes=("EV001",)):
    return GeneratedResponse("resposta", (GeneratedClaim("C1", text, codes),))


def test_marginal_selection_preserves_high_rank_determinant():
    determinant = candidate("a", "liberdade de expressão")
    related = candidate("b", "liberdade religiosa")
    selected = select_evidence_candidates(
        (determinant, related), question="liberdade de expressão", limit=1
    )
    assert selected == (determinant,)


def test_marginal_selection_prefers_complement_over_redundancy():
    first = candidate("a", "liberdade e expressão")
    redundant = candidate("b", "liberdade e expressão da manifestação")
    complement = candidate("c", "liberdade religiosa protegida")
    selected = select_evidence_candidates(
        (first, redundant, complement),
        question="liberdade expressão religiosa",
        limit=2,
    )
    assert selected == (first, complement)


def test_marginal_selection_promotes_intermediate_rank_with_new_coverage():
    first = candidate("a", "direito e liberdade")
    redundant = candidate("b", "direito à liberdade")
    complement = candidate("c", "manifestação e expressão")
    selected = select_evidence_candidates(
        (first, redundant, complement),
        question="direito liberdade expressão",
        limit=2,
    )
    assert complement in selected


def test_marginal_selection_does_not_promote_irrelevant_novel_tokens():
    relevant = candidate("a", "direito à liberdade")
    irrelevant = candidate("b", "tributação orçamento previdência")
    selected = select_evidence_candidates(
        (relevant, irrelevant), question="direito liberdade", limit=2
    )
    assert selected == (relevant,)


def test_parent_context_scores_without_changing_snapshot():
    noise = candidate("a", "prisão preventiva")
    relevant = candidate("b", "de caráter perpétuo", parent="não haverá penas")
    selected = select_evidence_candidates(
        (noise, relevant), question="prisão perpétua", limit=1
    )
    assert selected == (relevant,)
    assert relevant.chunk_text == "de caráter perpétuo"


def test_marginal_selection_preserves_dedup_and_limit():
    provision = uuid.uuid4()
    first = candidate("a", "direito liberdade", provision=provision)
    duplicate = candidate("b", "direito liberdade", provision=provision)
    other = candidate("c", "expressão protegida")
    extra = candidate("d", "manifestação protegida")
    selected = select_evidence_candidates(
        (first, duplicate, other, extra),
        question="direito liberdade expressão manifestação",
        limit=3,
    )
    assert first in selected
    assert duplicate not in selected
    assert len(selected) <= 3


def test_marginal_selection_handles_short_and_long_queries():
    items = (
        candidate("a", "voto obrigatório"),
        candidate("b", "alistamento eleitoral para maiores de dezoito anos"),
    )
    assert select_evidence_candidates(items, question="voto obrigatório")
    assert select_evidence_candidates(
        items,
        question="como funciona o alistamento eleitoral para maiores de dezoito anos",
    )


def test_marginal_selection_is_deterministic_and_auditable():
    items = (
        candidate("a", "liberdade expressão"),
        candidate("b", "manifestação expressão"),
    )
    first = select_evidence_candidates_with_diagnostics(
        items, question="liberdade expressão manifestação", limit=2
    )
    second = select_evidence_candidates_with_diagnostics(
        items, question="liberdade expressão manifestação", limit=2
    )
    assert first == second
    assert all(item.decision_reason for item in first.diagnostics)


def test_absent_marginal_contribution_does_not_force_redundancy():
    first = candidate("a", "liberdade expressão protegida")
    duplicate = replace(
        candidate("b", "liberdade expressão protegida"), parent_context=None
    )
    selected = select_evidence_candidates(
        (first, duplicate), question="liberdade expressão", limit=2
    )
    assert selected == (first,)


def test_simple_claim_preserves_simple_attribution():
    decision = deterministically_attribute(
        response("O voto é obrigatório."),
        (evidence("EV001", "O voto é obrigatório."),),
    )
    assert not decision.abstained
    assert decision.diagnostics[0].mode is AttributionMode.SIMPLE
    assert decision.response.claims[0].evidence_codes == ("EV001",)


def test_two_clauses_can_share_one_evidence():
    decision = deterministically_attribute(
        response("A regra é válida e a medida é aplicável."),
        (evidence("EV001", "A regra é válida e a medida é aplicável."),),
    )
    assert decision.diagnostics[0].mode is AttributionMode.CLAUSE
    assert decision.response.claims[0].evidence_codes == ("EV001",)
    assert len(decision.diagnostics[0].clauses) == 2


def test_clauses_can_use_different_authorized_evidence():
    decision = deterministically_attribute(
        response(
            "A autoridade pode decretar a medida e o Congresso pode autorizar a medida."
        ),
        (
            evidence("EV001", "A autoridade pode decretar a medida."),
            evidence("EV002", "O Congresso pode autorizar a medida."),
        ),
    )
    assert not decision.abstained
    assert decision.response.claims[0].evidence_codes == ("EV001", "EV002")


def test_three_clauses_are_attributed_individually():
    decision = deterministically_attribute(
        response("A regra é válida; a medida é aplicável; o ato é obrigatório."),
        (
            evidence("EV001", "A regra é válida."),
            evidence("EV002", "A medida é aplicável."),
            evidence("EV003", "O ato é obrigatório."),
        ),
    )
    assert not decision.abstained
    assert len(decision.diagnostics[0].clauses) == 3


def test_unsupported_clause_rejects_entire_claim():
    decision = deterministically_attribute(
        response(
            "A autoridade pode decretar a medida e o Congresso pode autorizar a medida."
        ),
        (evidence("EV001", "A autoridade pode decretar a medida."),),
    )
    assert decision.abstained
    assert decision.diagnostics[0].status is AttributionStatus.UNRESOLVED


def test_thematic_evidence_does_not_support_clause():
    decision = deterministically_attribute(
        response("A autoridade pode autorizar a medida."),
        (evidence("EV001", "A autoridade integra a administração pública."),),
    )
    assert decision.abstained


def test_attribution_never_emits_external_evidence_code():
    decision = deterministically_attribute(
        response("A regra é válida.", ("EV999",)),
        (evidence("EV001", "A regra é válida."),),
    )
    assert decision.response.claims[0].evidence_codes == ("EV001",)


def test_negation_exception_condition_and_nominal_list_are_not_split():
    texts = (
        "Não haverá penas de caráter perpétuo.",
        "Não haverá pena de morte, salvo em caso de guerra declarada.",
        "A medida é válida quando a condição estiver presente.",
        "Vida, liberdade e propriedade são direitos.",
        "Direito e liberdade.",
    )
    assert all(len(split_claim_clauses(text)) == 1 for text in texts)


def test_real_coordination_is_split_with_stable_spans():
    text = "A autoridade pode decretar a medida e o Congresso pode autorizar a medida."
    clauses = split_claim_clauses(text)
    assert tuple(item.text for item in clauses) == (
        "A autoridade pode decretar a medida",
        "o Congresso pode autorizar a medida.",
    )
    assert all(text[item.start : item.end] == item.text for item in clauses)
    assert clauses == split_claim_clauses(text)


def test_union_preserves_original_evidence_order():
    decision = deterministically_attribute(
        response("A segunda regra é válida e a primeira medida é aplicável."),
        (
            evidence("EV001", "A primeira medida é aplicável."),
            evidence("EV002", "A segunda regra é válida."),
        ),
    )
    assert decision.response.claims[0].evidence_codes == ("EV001", "EV002")


def test_partially_supported_composite_claim_fails_closed_deterministically():
    claim = response(
        "A autoridade pode decretar a medida e o Congresso pode autorizar a medida."
    )
    items = (evidence("EV001", "A autoridade pode decretar a medida."),)
    first = deterministically_attribute(claim, items)
    second = deterministically_attribute(claim, items)
    assert first == second
    assert first.abstained
