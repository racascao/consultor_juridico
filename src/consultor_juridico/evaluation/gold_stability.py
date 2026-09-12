"""Preparação e sumarização determinística da estabilidade Gold Evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any

from consultor_juridico.evaluation.gold_evidence import (
    GoldCategory,
    GoldEvidenceCase,
    load_gold_dataset,
)

STABILITY_PROMPT_VERSION = "2"
STABILITY_CASES_PER_CATEGORY = 3
STABILITY_SEEDS = (42, 43, 44)
STABILITY_SUMMARY_NAME = "gold-evidence-stability"
STABILITY_SUMMARY_VERSION = "1"

_BUNDLE_REQUIRED_FIELDS = {
    "case_id",
    "system_prompt",
    "user_prompt",
    "dataset_sha256",
    "version_hash",
    "prompt_name",
    "prompt_version",
}


def load_gold_bundle_records(path: Path) -> list[dict[str, Any]]:
    """Carrega um bundle provider-neutral e valida seus campos invariantes."""
    records: list[dict[str, Any]] = []
    case_ids: set[str] = set()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Bundle JSONL inválido na linha {line_number}") from error
        if not isinstance(record, dict) or not _BUNDLE_REQUIRED_FIELDS.issubset(record):
            raise ValueError(f"Bundle incompleto na linha {line_number}")
        case_id = record["case_id"]
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"case_id inválido na linha {line_number}")
        if case_id in case_ids:
            raise ValueError(f"case_id duplicado no bundle: {case_id}")
        if not isinstance(record["system_prompt"], str) or not isinstance(
            record["user_prompt"], str
        ):
            raise ValueError(f"Prompts inválidos na linha {line_number}")
        case_ids.add(case_id)
        records.append(record)
    if not records:
        raise ValueError("Bundle Gold Evidence vazio")
    for field in (
        "dataset_sha256",
        "version_hash",
        "prompt_name",
        "prompt_version",
    ):
        if len({record[field] for record in records}) != 1:
            raise ValueError(f"Bundle inconsistente para {field}")
    return records


def _case_score(dataset_sha256: str, case_id: str) -> str:
    return sha256(f"{dataset_sha256}:{case_id}".encode()).hexdigest()


def select_stability_cases(
    cases: tuple[GoldEvidenceCase, ...],
    *,
    dataset_sha256: str,
    per_category: int = STABILITY_CASES_PER_CATEGORY,
) -> tuple[GoldEvidenceCase, ...]:
    """Seleciona por SHA do dataset e case_id, sem consultar resultados."""
    if per_category < 1:
        raise ValueError("per_category deve ser positivo")
    selected: list[GoldEvidenceCase] = []
    for category in GoldCategory:
        candidates = sorted(
            (case for case in cases if case.category is category),
            key=lambda case: (_case_score(dataset_sha256, case.case_id), case.case_id),
        )
        if len(candidates) < per_category:
            raise ValueError(f"Casos insuficientes para {category.value}")
        selected.extend(candidates[:per_category])
    return tuple(selected)


def export_stability_bundle(
    *,
    dataset_path: Path,
    input_bundle_path: Path,
    output_path: Path,
    prompt_version: str = STABILITY_PROMPT_VERSION,
) -> dict[str, Any]:
    """Recorta o subset congelado preservando literalmente os prompts do bundle."""
    if output_path.exists():
        raise FileExistsError(f"O artefato não pode ser sobrescrito: {output_path}")
    raw_dataset = dataset_path.read_bytes()
    dataset_sha256 = sha256(raw_dataset).hexdigest()
    dataset = load_gold_dataset(dataset_path)
    records = load_gold_bundle_records(input_bundle_path)
    if records[0]["dataset_sha256"] != dataset_sha256:
        raise ValueError("SHA do dataset diverge do bundle de entrada")
    if records[0]["prompt_version"] != prompt_version:
        raise ValueError("Versão de prompt do bundle diverge da versão de estabilidade")
    by_case_id = {record["case_id"]: record for record in records}
    dataset_ids = {case.case_id for case in dataset.cases}
    if set(by_case_id) != dataset_ids:
        raise ValueError("Bundle de entrada não representa integralmente o dataset")

    selected = select_stability_cases(
        dataset.cases,
        dataset_sha256=dataset_sha256,
    )
    safe_fields = (
        "case_id",
        "prompt_name",
        "prompt_version",
        "dataset_sha256",
        "version_hash",
        "system_prompt",
        "user_prompt",
    )
    selected_records = [
        {field: by_case_id[case.case_id][field] for field in safe_fields}
        for case in selected
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as output:
        for record in selected_records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {
        "dataset_id": dataset.dataset_id,
        "dataset_sha256": dataset_sha256,
        "prompt_name": records[0]["prompt_name"],
        "prompt_version": prompt_version,
        "case_count": len(selected_records),
        "selected_cases": {
            category.value: [
                case.case_id for case in selected if case.category is category
            ]
            for category in GoldCategory
        },
        "output": str(output_path),
    }


def stability_subset_contract(
    path: Path, *, dataset_path: Path
) -> tuple[frozenset[str], str]:
    """Retorna IDs e versão declarados por um input de estabilidade validado."""
    records = load_gold_bundle_records(path)
    raw_dataset = dataset_path.read_bytes()
    dataset_sha256 = sha256(raw_dataset).hexdigest()
    dataset = load_gold_dataset(dataset_path)
    selected_ids = frozenset(
        case.case_id
        for case in select_stability_cases(
            dataset.cases,
            dataset_sha256=dataset_sha256,
        )
    )
    actual_ids = frozenset(record["case_id"] for record in records)
    if actual_ids != selected_ids or len(records) != len(selected_ids):
        raise ValueError("Input não corresponde ao subset congelado")
    if records[0]["dataset_sha256"] != dataset_sha256:
        raise ValueError("SHA do dataset diverge do input de estabilidade")
    prompt_version = str(records[0]["prompt_version"])
    if prompt_version != STABILITY_PROMPT_VERSION:
        raise ValueError("Input de estabilidade não usa o prompt v2")
    return actual_ids, prompt_version


def _load_evaluation(
    path: Path,
    *,
    dataset_sha256: str,
    selected_ids: set[str],
) -> dict[str, Any]:
    evaluation = json.loads(path.read_text(encoding="utf-8"))
    metadata = evaluation.get("metadata", {})
    if metadata.get("dataset_sha256") != dataset_sha256:
        raise ValueError(f"SHA do dataset diverge na avaliação: {path}")
    if metadata.get("prompt_version") != STABILITY_PROMPT_VERSION:
        raise ValueError(f"Prompt diverge na avaliação de estabilidade: {path}")
    if metadata.get("prompt_name") != "gold-evidence-answering":
        raise ValueError(f"Nome de prompt diverge na avaliação: {path}")
    cases = evaluation.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"Avaliação sem casos: {path}")
    case_ids = {item.get("case_id") for item in cases}
    if case_ids != selected_ids or len(cases) != len(selected_ids):
        raise ValueError(f"Avaliação não corresponde ao subset congelado: {path}")
    return evaluation


def _coverage_for_answer(case: dict[str, Any]) -> bool | None:
    if case.get("model_decision") != "ANSWER" or not case.get("parsed_response"):
        return None
    return bool(case["automatic_checks"]["required_citations_covered"])


def _citation_set(case: dict[str, Any]) -> list[str] | None:
    parsed = case.get("parsed_response")
    if not parsed:
        return None
    return sorted(set(parsed.get("citations", [])))


def _coverage_stability(values: list[bool | None]) -> bool | str:
    evaluable = [value for value in values if value is not None]
    if not evaluable:
        return "not_applicable"
    return len(set(evaluable)) == 1


def summarize_gold_stability(
    *,
    dataset_path: Path,
    evaluations_by_seed: Mapping[int, Path],
    output_path: Path,
) -> dict[str, Any]:
    """Compara decisões, cobertura e citations nas três seeds congeladas."""
    if output_path.exists():
        raise FileExistsError(f"O artefato não pode ser sobrescrito: {output_path}")
    if set(evaluations_by_seed) != set(STABILITY_SEEDS):
        raise ValueError(f"Seeds obrigatórias: {STABILITY_SEEDS}")

    raw_dataset = dataset_path.read_bytes()
    dataset_sha256 = sha256(raw_dataset).hexdigest()
    dataset = load_gold_dataset(dataset_path)
    selected = select_stability_cases(
        dataset.cases,
        dataset_sha256=dataset_sha256,
    )
    selected_ids = {case.case_id for case in selected}
    evaluations = {
        seed: _load_evaluation(
            path,
            dataset_sha256=dataset_sha256,
            selected_ids=selected_ids,
        )
        for seed, path in evaluations_by_seed.items()
    }
    cases_by_seed = {
        seed: {case["case_id"]: case for case in evaluation["cases"]}
        for seed, evaluation in evaluations.items()
    }

    cases: list[dict[str, Any]] = []
    for selected_case in selected:
        runs = {
            seed: cases_by_seed[seed][selected_case.case_id] for seed in STABILITY_SEEDS
        }
        decisions = [runs[seed].get("model_decision") for seed in STABILITY_SEEDS]
        coverages = [_coverage_for_answer(runs[seed]) for seed in STABILITY_SEEDS]
        citation_sets = {
            str(seed): _citation_set(runs[seed]) for seed in STABILITY_SEEDS
        }
        cases.append(
            {
                "case_id": selected_case.case_id,
                "category": selected_case.category.value,
                **{
                    f"seed_{seed}_decision": runs[seed].get("model_decision")
                    for seed in STABILITY_SEEDS
                },
                "decision_stable": len(set(decisions)) == 1,
                **{
                    f"seed_{seed}_required_citations_covered": (
                        _coverage_for_answer(runs[seed])
                    )
                    for seed in STABILITY_SEEDS
                },
                "required_citation_coverage_stable": _coverage_stability(coverages),
                "citation_sets": citation_sets,
                "citation_set_varied": len(
                    {
                        None if value is None else tuple(value)
                        for value in citation_sets.values()
                    }
                )
                > 1,
                "automatic_pass_by_seed": {
                    str(seed): bool(runs[seed]["automatic_pass"])
                    for seed in STABILITY_SEEDS
                },
            }
        )

    decision_stable = sum(case["decision_stable"] for case in cases)
    metrics = {
        "total_cases": len(cases),
        "decision_stable_cases": decision_stable,
        "decision_unstable_cases": len(cases) - decision_stable,
        "decision_stability_rate": decision_stable / len(cases),
        "decision_stability_fraction": f"{decision_stable}/{len(cases)}",
        "decision_unstable_by_category": {
            category.value: sum(
                not case["decision_stable"]
                for case in cases
                if case["category"] == category.value
            )
            for category in GoldCategory
        },
        "required_citation_coverage_unstable_cases": sum(
            case["required_citation_coverage_stable"] is False for case in cases
        ),
        "citation_set_variation_cases": sum(
            case["citation_set_varied"] for case in cases
        ),
        "automatic_pass_by_seed": {
            str(seed): sum(case["automatic_pass_by_seed"][str(seed)] for case in cases)
            for seed in STABILITY_SEEDS
        },
    }
    check_metrics = {
        "false_abstention_by_seed": "false_abstention",
        "missed_clarification_by_seed": "missed_clarification",
        "unsafe_answer_on_insufficient_by_seed": ("unsafe_answer_on_insufficient"),
    }
    for metric_name, check_name in check_metrics.items():
        metrics[metric_name] = {
            str(seed): sum(
                bool(cases_by_seed[seed][case.case_id]["automatic_checks"][check_name])
                for case in selected
            )
            for seed in STABILITY_SEEDS
        }
    metrics["invalid_citation_cases_by_seed"] = {
        str(seed): sum(
            bool(cases_by_seed[seed][case.case_id]["invalid_citations"])
            for case in selected
        )
        for seed in STABILITY_SEEDS
    }
    metrics["out_of_evidence_citation_cases_by_seed"] = {
        str(seed): sum(
            bool(cases_by_seed[seed][case.case_id]["out_of_evidence_citations"])
            for case in selected
        )
        for seed in STABILITY_SEEDS
    }

    result = {
        "metadata": {
            "summary_name": STABILITY_SUMMARY_NAME,
            "summary_version": STABILITY_SUMMARY_VERSION,
            "dataset_id": dataset.dataset_id,
            "dataset_sha256": dataset_sha256,
            "prompt_name": "gold-evidence-answering",
            "prompt_version": STABILITY_PROMPT_VERSION,
            "seeds": list(STABILITY_SEEDS),
            "cases_per_category": STABILITY_CASES_PER_CATEGORY,
            "selection_method": "DATASET_SHA_CASE_ID_HASH",
            "source_evaluations": {
                str(seed): {
                    "path": str(evaluations_by_seed[seed]),
                    "sha256": sha256(
                        evaluations_by_seed[seed].read_bytes()
                    ).hexdigest(),
                }
                for seed in STABILITY_SEEDS
            },
        },
        "metrics": metrics,
        "cases": cases,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return result
