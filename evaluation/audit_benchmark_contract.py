"""Audita contrato de benchmark EBCG sem executar pipeline, LLM ou retrieval."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import select

from consultor_juridico.db.session import SessionLocal
from consultor_juridico.evaluation.dataset import load_dataset
from consultor_juridico.models import LegalProvision

_IDENTITY = re.compile(r"\(identidade:\s*(?P<identity>[^)]+)\)")
DEFAULT_ARTIFACT = Path(
    "evaluation/results/model_benchmark_96_ebcg_v2_e2e_1/e2e_ebcg_v2_run_1.json"
)
DEFAULT_DATASET = Path("evaluation/datasets/real_world_short_v1.json")
DEFAULT_OUTPUT = Path(
    "evaluation/results/model_benchmark_98/benchmark_contract_audit.json"
)
DEFAULT_PROPOSALS = Path(
    "evaluation/results/model_benchmark_98/benchmark_contract_proposals.json"
)


def allowed_targets(case: Any) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys((*case.expected_provisions, *case.acceptable_provisions))
    )


def _citation_identities(record: dict[str, Any]) -> tuple[str, ...]:
    by_code = {}
    for citation in record.get("generation", {}).get("citations", []):
        match = _IDENTITY.search(str(citation.get("label", "")))
        if match:
            by_code[citation.get("code")] = match.group("identity")
    return tuple(
        by_code[code]
        for claim in record.get("generation", {}).get("claims", [])
        for code in claim.get("ev", [])
        if code in by_code
    )


def _core_from_attribution(record: dict[str, Any]) -> tuple[str | None, str | None]:
    attribution = record.get("generation", {}).get("attribution", [])
    if not attribution:
        return None, None
    codes = attribution[0].get("evidence_codes", [])
    if not codes:
        return None, None
    code = codes[0]
    selected = record.get("evidence_selection", {}).get("items", [])
    position = int(code.removeprefix("EV")) - 1 if code.startswith("EV") else -1
    identity = (
        selected[position].get("identity_key")
        if 0 <= position < len(selected)
        else None
    )
    return code, identity


def _structural_status(
    targets: tuple[str, ...], structural_index: dict[str, dict[str, Any]]
) -> dict[str, str]:
    if not structural_index:
        return {target: "INCONCLUSIVE" for target in targets}
    return {
        target: "VALID" if target in structural_index else "MISSING"
        for target in targets
    }


def _has_ambiguous_full_coverage(
    record: dict[str, Any], targets: tuple[str, ...]
) -> bool:
    diagnostics = record.get("evidence_selection", {}).get("diagnostics", [])
    selected = {
        item.get("identity_key")
        for item in record.get("evidence_selection", {}).get("items", [])
    }
    full = {
        item.get("identity_key")
        for item in diagnostics
        if item.get("query_coverage") == 1.0
    }
    return bool((set(targets) & selected & full) and (full - set(targets)))


def _classify(
    record: dict[str, Any], case: Any, structural_index: dict[str, dict[str, Any]]
) -> tuple[str, tuple[str, ...], str, str | None]:
    result = record["result"]
    classification = result.get("classification")
    targets = allowed_targets(case)
    selected = tuple(
        item.get("identity_key", "")
        for item in record.get("evidence_selection", {}).get("items", [])
    )
    core_code, core_identity = _core_from_attribution(record)
    status = _structural_status(targets, structural_index)
    missing_targets = tuple(key for key, value in status.items() if value == "MISSING")

    if classification == "CORRECT_ANSWER":
        return (
            "PASS",
            (),
            "Resposta e target fidelity passaram no artefato congelado.",
            None,
        )
    if classification == "CORRECT_ABSTENTION":
        return (
            "EXPECTED_ABSTENTION",
            (),
            "Caso não respondível absteve corretamente.",
            None,
        )
    if classification == "UNSAFE_ANSWER":
        return "UNSAFE_RESPONSE", (), "Caso não respondível recebeu resposta.", None
    expected_status = _structural_status(case.expected_provisions, structural_index)
    expected_valid = not structural_index or any(
        value == "VALID" for value in expected_status.values()
    )
    if not record.get("retrieval", {}).get("hit") and expected_valid:
        return (
            "RETRIEVAL_MISS",
            (),
            "Nenhum target permitido ocorreu no retrieval medido.",
            None,
        )
    if missing_targets and any(
        selected_key.startswith(target.rsplit("/", 1)[0])
        for target in missing_targets
        for selected_key in selected
    ):
        return (
            "DATASET_TARGET_ERROR",
            ("EVALUATION_TAXONOMY_ERROR",),
            "Target do dataset não existe; a ocorrência ancestral foi selecionada.",
            "TARGET_HIERARCHY_MISMATCH_SUSPECTED",
        )
    errors = record.get("generation", {}).get("validation_errors", [])
    if classification == "FALSE_ABSTENTION" and any(
        "UNRESOLVED" in str(x) for x in errors
    ):
        secondary = (
            ("EVALUATION_TAXONOMY_ERROR",)
            if result.get("failure_stage") == "GENERATOR_ABSTENTION"
            else ()
        )
        return (
            "STRUCTURAL_CONTEXT_REQUIRED_FOR_VALIDATION",
            secondary,
            "Claim atribuída ao target foi bloqueada em validação com snapshot "
            "isolado.",
            "POLARITY_VALIDATION",
        )
    if classification == "WRONG_TARGET" and _has_ambiguous_full_coverage(
        record, targets
    ):
        return (
            "QUERY_AMBIGUITY",
            ("ACCEPTABLE_TARGETS_INCOMPLETE",),
            "Target permitido e norma distinta selecionada têm cobertura integral "
            "da consulta curta.",
            None,
        )
    if classification == "WRONG_TARGET" and set(targets) & set(selected):
        return (
            "CORE_EVIDENCE_SELECTION_ERROR",
            (),
            "Target permitido foi selecionável, mas a Core Evidence citada não "
            "pertence ao contrato.",
            None,
        )
    if (
        classification == "WRONG_TARGET"
        and core_identity
        and core_identity not in targets
    ):
        return (
            "CORE_EVIDENCE_SELECTION_ERROR",
            (),
            "Core Evidence fora dos targets permitidos.",
            None,
        )
    return "INCONCLUSIVE", (), "Artefato não contém sinal estrutural suficiente.", None


def audit_artifact(
    artifact: dict[str, Any],
    cases_by_id: dict[str, Any],
    structural_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Classifica o artefato imutável; `structural_index` é opcional e read-only."""
    index = structural_index or {}
    records = []
    for raw in artifact["results"]:
        case = cases_by_id[raw["case_id"]]
        targets = allowed_targets(case)
        primary, secondary, reason, recommended_stage = _classify(raw, case, index)
        core_code, core_identity = _core_from_attribution(raw)
        cited = _citation_identities(raw)
        ranks = raw.get("retrieval", {}).get("ranks", {})
        structural = _structural_status(targets, index)
        records.append(
            {
                "case_id": case.id,
                "question": case.question,
                "expect_answer": case.expect_answer,
                "pipeline_classification": raw["result"].get("classification"),
                "failure_stage": raw["result"].get("failure_stage"),
                "expected_provisions": list(case.expected_provisions),
                "acceptable_provisions": list(case.acceptable_provisions),
                "retrieval_hit": raw.get("retrieval", {}).get("hit"),
                "allowed_target_ranks": {key: ranks.get(key) for key in targets},
                "selected_evidence": raw.get("evidence_selection", {}).get("items", []),
                "core_evidence": {
                    "code": core_code,
                    "identity_key": core_identity,
                    "cited_identity_keys": list(cited),
                },
                "target_fidelity_pass": raw.get("target_fidelity", {}).get("passed"),
                "structural_target_status": structural,
                "primary_attribution": primary,
                "secondary_attributions": list(secondary),
                "reason": reason,
                "recommended_failure_stage": recommended_stage,
                "dataset_change_recommended": primary
                in {
                    "DATASET_TARGET_ERROR",
                    "ACCEPTABLE_TARGETS_INCOMPLETE",
                    "QUERY_AMBIGUITY",
                },
                "production_change_recommended": primary
                in {
                    "RETRIEVAL_MISS",
                    "CORE_EVIDENCE_SELECTION_ERROR",
                    "STRUCTURAL_CONTEXT_REQUIRED_FOR_VALIDATION",
                },
            }
        )
    aggregates = Counter(item["primary_attribution"] for item in records)
    return {
        "cases": records,
        "aggregate": {
            key.lower(): aggregates.get(key, 0)
            for key in (
                "PASS",
                "EXPECTED_ABSTENTION",
                "RETRIEVAL_MISS",
                "CORE_EVIDENCE_SELECTION_ERROR",
                "VALIDATOR_FALSE_NEGATIVE",
                "STRUCTURAL_CONTEXT_REQUIRED_FOR_VALIDATION",
                "DATASET_TARGET_ERROR",
                "ACCEPTABLE_TARGETS_INCOMPLETE",
                "QUERY_AMBIGUITY",
                "EVALUATION_TAXONOMY_ERROR",
                "INCONCLUSIVE",
            )
        },
    }


def load_structural_index() -> dict[str, dict[str, Any]]:
    """Lê a identidade normativa materializada sem alterar o banco."""
    with SessionLocal() as session:
        rows = session.execute(
            select(
                LegalProvision.identity_key,
                LegalProvision.element_type,
                LegalProvision.parent_id,
            )
        ).all()
    return {
        identity: {
            "element_type": element_type,
            "parent_id": str(parent_id) if parent_id else None,
        }
        for identity, element_type, parent_id in rows
    }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(
    artifact_path: Path,
    dataset_path: Path,
    output: Path,
    proposals: Path,
    structural: bool,
) -> None:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    _version, cases = load_dataset(dataset_path)
    index = load_structural_index() if structural else {}
    report = audit_artifact(artifact, {case.id: case for case in cases}, index)
    payload = {
        "phase": "98",
        "source_artifact": str(artifact_path),
        "source_artifact_sha256": _sha(artifact_path),
        "dataset": str(dataset_path),
        "dataset_sha256": _sha(dataset_path),
        "raw_artifact_unchanged": True,
        "read_only_structural_audit": structural,
        **report,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    proposed = [
        {
            "case_id": item["case_id"],
            "current_contract": {
                "expected_provisions": item["expected_provisions"],
                "acceptable_provisions": item["acceptable_provisions"],
            },
            "proposed_change": item["primary_attribution"],
            "reason": item["reason"],
            "confidence": "HIGH"
            if item["primary_attribution"] == "DATASET_TARGET_ERROR"
            else "MEDIUM",
        }
        for item in report["cases"]
        if item["dataset_change_recommended"]
    ]
    proposals.write_text(
        json.dumps({"phase": "98", "proposals": proposed}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--proposals", type=Path, default=DEFAULT_PROPOSALS)
    parser.add_argument("--structural", action="store_true")
    arguments = parser.parse_args()
    main(
        arguments.artifact,
        arguments.dataset,
        arguments.output,
        arguments.proposals,
        arguments.structural,
    )
