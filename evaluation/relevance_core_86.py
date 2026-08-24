"""Experimento offline da boundary Query -> Claim da Fase 12.

Este módulo consome somente artefatos JSON congelados. Ele não integra a
consulta de produção, não chama LLM e não conhece cases, artigos ou provisions
esperados durante a classificação.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class RelevanceStatus(StrEnum):
    RELEVANT = "RELEVANT"
    IRRELEVANT = "IRRELEVANT"
    UNRESOLVED = "UNRESOLVED"


class AnswerRole(StrEnum):
    CENTRAL = "CENTRAL"
    AUXILIARY = "AUXILIARY"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class RelevanceDecision:
    status: RelevanceStatus
    role: AnswerRole
    query_terms: tuple[str, ...]
    covered_terms: tuple[str, ...]
    reason: str


_WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
_DEONTIC_SUBJECT_RE = re.compile(
    r"(?:^|\s)(?:o|a|os|as)\s+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][\wÀ-ÿ-]{3,})\s+"
    r"(?:pode|podem|deve|devem)\b",
    re.IGNORECASE,
)
_STRUCTURAL_TERMS = frozenset(
    {"artigo", "capitulo", "secao", "subsecao", "titulo", "inciso", "alinea"}
)
_FUNCTION_WORDS = frozenset(
    {
        "com",
        "como",
        "constitucional",
        "constituicao",
        "das",
        "dos",
        "esse",
        "esta",
        "este",
        "isso",
        "nos",
        "para",
        "pela",
        "pelo",
        "por",
        "qual",
        "que",
        "sobre",
        "uma",
        "uns",
    }
)
_SUBORDINATE_PREFIXES = frozenset(
    {"apos", "quando", "se", "desde", "salvo", "exceto", "ressalvado"}
)


def evaluate_claim_relevance(
    query: str, claim: str, fragments: tuple[str, ...]
) -> RelevanceDecision:
    """Classifica apenas vetos auditáveis; ambiguidade permanece fail-closed.

    A cobertura é calculada contra claim + fragments autorizados porque uma
    paráfrase pode deixar um termo explícito no fragmento, embora não na claim.
    Não há sinônimos, artigos, cases ou consulta ao corpus.
    """
    query_terms = _material_terms(query)
    if not query_terms:
        return RelevanceDecision(
            RelevanceStatus.UNRESOLVED,
            AnswerRole.UNRESOLVED,
            (),
            (),
            "A pergunta não contém termos materiais suficientes.",
        )

    source_text = " ".join(fragments)
    claim_terms = {_inflection_key(term) for term in _material_terms(claim)}
    source_terms = {_inflection_key(term) for term in _material_terms(source_text)}
    covered = tuple(
        term
        for term in query_terms
        if _inflection_key(term) in claim_terms | source_terms
    )
    if len(covered) != len(query_terms):
        return RelevanceDecision(
            RelevanceStatus.IRRELEVANT,
            AnswerRole.AUXILIARY,
            query_terms,
            covered,
            (
                "A claim e seus fragmentos autorizados não cobrem todos os termos "
                "materiais da pergunta."
            ),
        )

    ungrounded = _ungrounded_deontic_subjects(claim, source_text)
    if ungrounded:
        return RelevanceDecision(
            RelevanceStatus.UNRESOLVED,
            AnswerRole.UNRESOLVED,
            query_terms,
            covered,
            "A claim introduz termo institucional capitalizado ausente dos fragmentos: "
            + ", ".join(ungrounded)
            + ".",
        )

    if _is_structural_only(claim):
        return RelevanceDecision(
            RelevanceStatus.RELEVANT,
            AnswerRole.AUXILIARY,
            query_terms,
            covered,
            (
                "A claim descreve apenas localização ou organização documental, "
                "não uma proposição central."
            ),
        )

    if _focus_is_only_in_subordinate_prefix(claim, query_terms):
        return RelevanceDecision(
            RelevanceStatus.RELEVANT,
            AnswerRole.AUXILIARY,
            query_terms,
            covered,
            (
                "Os termos da pergunta aparecem somente em oração subordinada "
                "ou temporal da claim."
            ),
        )

    return RelevanceDecision(
        RelevanceStatus.RELEVANT,
        AnswerRole.CENTRAL,
        query_terms,
        covered,
        (
            "A claim e os fragmentos autorizados cobrem a proposição material "
            "da pergunta sem veto forte."
        ),
    )


def run_experiment(
    ab_rows: list[dict[str, Any]], frozen_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compara o rendering legado A com a policy B sobre outputs já congelados."""
    frozen_by_case = {row["case_id"]: row for row in frozen_rows}
    rows: list[dict[str, Any]] = []
    historical_regressions = 0
    unsafe_after = 0

    for row in ab_rows:
        bound = row["evidence_bound"]
        frozen = frozen_by_case[row["case_id"]]
        fragments_by_code = _fragments_by_code(frozen.get("support_slot_manifest", {}))
        decisions = []
        for claim in bound["claims"]:
            fragments = tuple(
                fragment
                for code in claim["evidence_codes"]
                for fragment in fragments_by_code.get(code, ())
            )
            decision = evaluate_claim_relevance(
                row["question"], claim["text"], fragments
            )
            decisions.append({"claim": claim, "decision": asdict(decision)})

        central_claims = [
            item
            for item in decisions
            if item["decision"]["status"] == RelevanceStatus.RELEVANT
            and item["decision"]["role"] == AnswerRole.CENTRAL
        ]
        after_outcome = "ANSWERED" if central_claims else "ABSTAINED"
        previous_correct = row["evidence_bound_assessment"]["correct"]
        after_correct = (
            after_outcome == "ANSWERED"
            if row["expect_answer"]
            else after_outcome == "ABSTAINED"
        )
        if previous_correct and not after_correct:
            historical_regressions += 1

        # Sem provision esperada no runtime: para o experimento, uma resposta
        # previamente julgada off-target só deixa de ser insegura se B abstiver.
        was_off_target = (
            row["expect_answer"]
            and bound["outcome"] == "ANSWERED"
            and not previous_correct
        )
        is_unsafe_after = was_off_target and after_outcome == "ANSWERED"
        unsafe_after += int(is_unsafe_after)
        rows.append(
            {
                "case_id": row["case_id"],
                "question": row["question"],
                "expect_answer": row["expect_answer"],
                "before_outcome": bound["outcome"],
                "after_outcome": after_outcome,
                "previously_correct": previous_correct,
                "after_correct": after_correct,
                "was_off_target": was_off_target,
                "unsafe_after": is_unsafe_after,
                "decisions": decisions,
            }
        )

    controls = _run_controls()
    relevant_cases = {row["case_id"]: row for row in rows}
    prison_cleared = (
        relevant_cases["rw-prisao-perpetua"]["after_outcome"] == "ABSTAINED"
    )
    state_cleared = relevant_cases["rw-estado-sitio"]["after_outcome"] == "ABSTAINED"
    controls_pass = all(control["passed"] for control in controls)
    passed = (
        prison_cleared
        and state_cleared
        and unsafe_after == 0
        and historical_regressions == 0
        and controls_pass
    )
    return {
        "phase": "answer_relevance_core_offline",
        "source_artifacts": {
            "ab": "evaluation/results/evidence_bound_12_ab.json",
            "frozen_evidence_sets": (
                "evaluation/results/evidence_bound_12_frozen_evidence_sets.json"
            ),
        },
        "generator_calls": 0,
        "retrieval_calls": 0,
        "production_integration": "NOT_ENABLED",
        "rows": rows,
        "controls": controls,
        "summary": {
            "result": "PASS" if passed else "FAIL",
            "unsafe_product_answers_before": 2,
            "unsafe_product_answers_after": unsafe_after,
            "historical_correct_regressions": historical_regressions,
            "prison_off_target_cleared": prison_cleared,
            "state_off_target_cleared": state_cleared,
            "controls_pass": controls_pass,
        },
    }


def _fragments_by_code(manifest: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    return {
        slot["evidence_codes"][0]: tuple(
            fragment["text"] for fragment in slot["fragments"]
        )
        for slot in manifest.get("slots", ())
    }


def _run_controls() -> list[dict[str, object]]:
    controls = (
        (
            "TRUE_BUT_IRRELEVANT",
            "pena perpétua",
            "A comunicação da prisão deve ser imediata.",
            ("A comunicação da prisão deve ser imediata.",),
            RelevanceStatus.IRRELEVANT,
            AnswerRole.AUXILIARY,
        ),
        (
            "SUPPORTED_BUT_OFF_TARGET",
            "estado de sítio",
            "Após o término do estado de sítio, haverá relatório.",
            ("Após o término do estado de sítio, haverá relatório.",),
            RelevanceStatus.RELEVANT,
            AnswerRole.AUXILIARY,
        ),
        (
            "WRONG_LEGAL_ACTOR",
            "estado de sítio",
            "O Congresso pode decretar o estado de sítio.",
            ("decretar o estado de sítio.",),
            RelevanceStatus.UNRESOLVED,
            AnswerRole.UNRESOLVED,
        ),
        (
            "RELATED_PROVISION_WRONG_ANSWER",
            "prisão perpétua",
            "A prisão deve ser comunicada ao juiz.",
            ("A prisão deve ser comunicada ao juiz.",),
            RelevanceStatus.IRRELEVANT,
            AnswerRole.AUXILIARY,
        ),
        (
            "PARTIAL_TRUE_ANSWER_TO_BINARY_QUERY",
            "voto obrigatório",
            "O voto é exercido nas eleições.",
            ("O voto é exercido nas eleições.",),
            RelevanceStatus.IRRELEVANT,
            AnswerRole.AUXILIARY,
        ),
        (
            "AUXILIARY_FACT_WITHOUT_CORE_ANSWER",
            "estado de sítio",
            "O estado de sítio integra capítulo específico de título constitucional.",
            (
                "O estado de sítio integra capítulo específico de título "
                "constitucional.",
            ),
            RelevanceStatus.RELEVANT,
            AnswerRole.AUXILIARY,
        ),
        (
            "CENTRAL_CLAIM_REJECTED_AUXILIARY_SURVIVES",
            "pena de morte",
            "Após a pena de morte, haverá registro administrativo.",
            ("Após a pena de morte, haverá registro administrativo.",),
            RelevanceStatus.RELEVANT,
            AnswerRole.AUXILIARY,
        ),
        (
            "VALID_ALTERNATIVE_PROVISION",
            "voto obrigatório",
            "O voto é obrigatório para maiores de dezoito anos.",
            ("O voto é obrigatório para maiores de dezoito anos.",),
            RelevanceStatus.RELEVANT,
            AnswerRole.CENTRAL,
        ),
        (
            "RELEVANT_BUT_UNSUPPORTED",
            "pena de morte",
            "A pena de morte é sempre permitida.",
            ("A pena de morte é proibida.",),
            RelevanceStatus.RELEVANT,
            AnswerRole.CENTRAL,
        ),
        (
            "SUPPORTED_AND_RELEVANT",
            "pena de morte",
            "A pena de morte é proibida, salvo exceção expressa.",
            ("A pena de morte é proibida, salvo exceção expressa.",),
            RelevanceStatus.RELEVANT,
            AnswerRole.CENTRAL,
        ),
    )
    results = []
    for name, query, claim, fragments, expected_status, expected_role in controls:
        decision = evaluate_claim_relevance(query, claim, fragments)
        results.append(
            {
                "name": name,
                "expected_status": expected_status.value,
                "expected_role": expected_role.value,
                "actual": asdict(decision),
                "passed": (
                    decision.status == expected_status
                    and decision.role == expected_role
                ),
            }
        )
    return results


def _material_terms(value: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in _WORD_RE.findall(_normalize(value))
        if token not in _FUNCTION_WORDS
    )


def _inflection_key(token: str) -> str:
    """Remove apenas flexões terminais regulares; não introduz sinônimos."""
    value = token
    for suffix in ("os", "as", "es", "o", "a", "s"):
        if len(value) - len(suffix) >= 4 and value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    return value


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _ungrounded_deontic_subjects(claim: str, source_text: str) -> tuple[str, ...]:
    """Veta apenas ator capitalizado em construção deôntica explícita.

    Isso não tenta resolver entidades jurídicas em geral: é um sinal forte de
    que a claim atribuiu poder ou dever a um sujeito ausente da fonte.
    """
    source_token_keys = {
        _inflection_key(token) for token in _material_terms(source_text)
    }
    return tuple(
        _normalize(match.group(1))
        for match in _DEONTIC_SUBJECT_RE.finditer(claim)
        if _inflection_key(_normalize(match.group(1))) not in source_token_keys
    )


def _is_structural_only(claim: str) -> bool:
    terms = set(_material_terms(claim))
    structural_count = len(terms & _STRUCTURAL_TERMS)
    return structural_count >= 2 and not bool(
        terms
        & {
            "obrigatorio",
            "permitido",
            "proibido",
            "vedado",
            "garantido",
            "inviolavel",
        }
    )


def _focus_is_only_in_subordinate_prefix(
    claim: str, query_terms: tuple[str, ...]
) -> bool:
    normalized = _normalize(claim)
    prefix, separator, _main = normalized.partition(",")
    return bool(
        separator
        and prefix.split(maxsplit=1)[0] in _SUBORDINATE_PREFIXES
        and set(query_terms).issubset(set(_material_terms(prefix)))
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ab", type=Path, required=True)
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_experiment(
        json.loads(args.ab.read_text(encoding="utf-8")),
        json.loads(args.frozen.read_text(encoding="utf-8")),
    )
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
