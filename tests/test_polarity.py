from types import SimpleNamespace

import pytest

from consultor_juridico.consultation.polarity import (
    PolarityReason,
    PolarityStatus,
    can_route_to_semantic,
    validate_polarity,
)
from consultor_juridico.consultation.types import GeneratedClaim


def evidence(text: str, *, parent: str | None = None, code: str = "EV001"):
    return SimpleNamespace(
        evidence_code=code,
        text_snapshot=text,
        validation_metadata={"parent_context": parent},
    )


def check(claim: str, source: str, expected: PolarityStatus, *, parent=None):
    result = validate_polarity(
        GeneratedClaim("C1", claim, ("EV001",)),
        (evidence(source, parent=parent),),
    )
    assert result.status is expected, result
    return result


def test_explicit_prohibition_and_faithful_paraphrase_are_consistent():
    check(
        "É proibida a pena de caráter perpétuo.",
        "Não haverá penas de caráter perpétuo.",
        PolarityStatus.CONSISTENT,
    )


def test_permission_against_prohibition_is_contradicted():
    check(
        "A pena de caráter perpétuo é permitida.",
        "Não haverá penas de caráter perpétuo.",
        PolarityStatus.CONTRADICTED,
    )


def test_obligation_and_facultativity_are_opposites():
    check(
        "A medida é obrigatória.",
        "A medida é obrigatória.",
        PolarityStatus.CONSISTENT,
    )
    check(
        "A medida é facultativa.",
        "A medida é obrigatória.",
        PolarityStatus.CONTRADICTED,
    )


def test_permission_and_prohibition_are_opposites_in_both_directions():
    check(
        "A medida é proibida.",
        "A medida é permitida.",
        PolarityStatus.CONTRADICTED,
    )
    check(
        "A medida é permitida.",
        "A medida é proibida.",
        PolarityStatus.CONTRADICTED,
    )


def test_exception_is_consistent_only_when_preserved():
    source = "A medida é permitida, salvo em caso de emergência."
    check(
        "A medida é permitida, salvo em caso de emergência.",
        source,
        PolarityStatus.CONSISTENT,
    )
    check("A medida é permitida.", source, PolarityStatus.UNRESOLVED)


def test_ambiguous_language_fails_closed():
    check(
        "A medida pode ser analisada.",
        "A medida será analisada conforme o procedimento.",
        PolarityStatus.UNRESOLVED,
    )


def test_parent_context_is_authorized_for_the_comparison():
    result = check(
        "A providência é facultativa.",
        "A providência será aplicada.",
        PolarityStatus.CONTRADICTED,
        parent="A providência é obrigatória para todos.",
    )
    assert "obrigação" in result.reason


def test_affirmative_normative_claims_are_not_rejected_as_unresolved():
    check(
        "A liberdade religiosa é garantida e protege o livre exercício dos cultos.",
        (
            "É inviolável a liberdade de consciência e de crença, sendo assegurado "
            "o livre exercício dos cultos."
        ),
        PolarityStatus.CONSISTENT,
    )
    check(
        "O direito à vida é garantido pela Constituição.",
        "É inviolável o direito à vida.",
        PolarityStatus.CONSISTENT,
    )
    check(
        "A Constituição estabelece a possibilidade de declaração do estado de sítio.",
        (
            "A Constituição estabelece a declaração do estado de sítio nos termos "
            "constitucionais."
        ),
        PolarityStatus.CONSISTENT,
    )


def test_non_polarity_sem_does_not_become_prohibition():
    check(
        "O direito à vida é garantido.",
        (
            "Todos são iguais perante a lei, sem distinção de qualquer natureza, "
            "garantindo-se a inviolabilidade do direito à vida."
        ),
        PolarityStatus.CONSISTENT,
    )


def test_non_exceptive_a_salvo_does_not_trigger_exception():
    result = check(
        "O Estado deve proteger crianças de negligência e violência.",
        "É dever do Estado colocá-las a salvo de negligência e violência.",
        PolarityStatus.CONSISTENT,
    )
    assert result.reason_code is None


def test_regressions_prison_vote_and_death_exception():
    check(
        "A prisão perpétua é permitida.",
        "Não haverá penas de caráter perpétuo.",
        PolarityStatus.CONTRADICTED,
    )
    check(
        "O alistamento eleitoral é facultativo.",
        "O alistamento eleitoral e o voto são obrigatórios.",
        PolarityStatus.CONTRADICTED,
    )
    check(
        "A pena de morte é vedada, salvo em caso de guerra declarada.",
        "Não haverá pena de morte, salvo em caso de guerra declarada.",
        PolarityStatus.CONSISTENT,
    )


@pytest.mark.parametrize(
    ("claim", "source", "expected"),
    [
        (
            "A pena perpétua é permitida.",
            "Não haverá penas de caráter perpétuo.",
            PolarityStatus.CONTRADICTED,
        ),
        (
            "A providência é facultativa.",
            "A providência é obrigatória.",
            PolarityStatus.CONTRADICTED,
        ),
        ("A medida é proibida.", "A medida é permitida.", PolarityStatus.CONTRADICTED),
    ],
)
def test_adversarial_inversions_are_always_vetoed(claim, source, expected):
    statuses = {
        validate_polarity(
            GeneratedClaim("C1", claim, ("EV001",)),
            (evidence(source),),
        ).status
        for _ in range(5)
    }
    assert statuses == {expected}


def test_unresolved_reason_codes_are_deterministic():
    no_relation = validate_polarity(
        GeneratedClaim("C1", "A medida pode ser analisada.", ("EV001",)),
        (evidence("A providência será analisada conforme o procedimento."),),
    )
    assert no_relation.reason_code is PolarityReason.NO_POLARITY_RELATION

    exception = validate_polarity(
        GeneratedClaim("C1", "A medida é permitida.", ("EV001",)),
        (evidence("A medida é permitida, salvo em caso de emergência."),),
    )
    assert exception.reason_code is PolarityReason.EXCEPTION_SCOPE_AMBIGUITY
    assert not can_route_to_semantic(exception)
    assert can_route_to_semantic(no_relation)
