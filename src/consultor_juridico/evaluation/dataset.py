"""Carregamento estrito do dataset versionado de avaliação."""

import json
from pathlib import Path

from consultor_juridico.evaluation.types import EvaluationCase


class EvaluationDatasetError(ValueError):
    """Dataset ausente ou incompatível com o contrato."""


def load_dataset(path: str | Path) -> tuple[str, tuple[EvaluationCase, ...]]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationDatasetError(f"Não foi possível ler {source}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("version"), str):
        raise EvaluationDatasetError("Dataset deve possuir version textual.")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise EvaluationDatasetError("Dataset deve possuir cases não vazio.")
    cases = tuple(_parse_case(value) for value in raw_cases)
    identifiers = [case.id for case in cases]
    if len(set(identifiers)) != len(identifiers):
        raise EvaluationDatasetError("IDs de casos devem ser únicos.")
    return payload["version"], cases


def _parse_case(value: object) -> EvaluationCase:
    if not isinstance(value, dict):
        raise EvaluationDatasetError("Cada caso deve ser um objeto.")
    required_strings = ("id", "category", "question", "rationale")
    if any(
        not isinstance(value.get(key), str) or not value[key].strip()
        for key in required_strings
    ):
        raise EvaluationDatasetError("Caso possui campo textual obrigatório inválido.")
    expected_act = value.get("expected_act")
    if expected_act is not None and not isinstance(expected_act, str):
        raise EvaluationDatasetError(f"expected_act inválido em {value['id']}.")
    expect_answer = value.get("expect_answer")
    if not isinstance(expect_answer, bool):
        raise EvaluationDatasetError(f"expect_answer inválido em {value['id']}.")
    expected = _string_tuple(value.get("expected_provisions"), "expected_provisions")
    acceptable = _string_tuple(
        value.get("acceptable_provisions", []), "acceptable_provisions"
    )
    concepts = _string_tuple(value.get("required_concepts", []), "required_concepts")
    tags = _string_tuple(value.get("tags", []), "tags")
    if expect_answer and not expected:
        raise EvaluationDatasetError(
            f"Caso respondível {value['id']} sem provision esperada."
        )
    if not expect_answer and expected:
        raise EvaluationDatasetError(
            f"Caso de abstenção {value['id']} possui provision esperada."
        )
    return EvaluationCase(
        id=value["id"],
        category=value["category"],
        question=value["question"],
        expected_act=expected_act,
        expected_provisions=expected,
        acceptable_provisions=acceptable,
        expect_answer=expect_answer,
        required_concepts=concepts,
        rationale=value["rationale"],
        tags=tags,
    )


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise EvaluationDatasetError(f"{field} deve ser lista textual.")
    return tuple(value)
