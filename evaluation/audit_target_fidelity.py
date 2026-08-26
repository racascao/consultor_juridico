"""Reavalia um artefato E2E já congelado sem I/O de corpus ou LLM."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from consultor_juridico.evaluation.dataset import load_dataset
from consultor_juridico.evaluation.target_fidelity import assess_target_fidelity

DEFAULT_DATASET = Path("evaluation/datasets/real_world_short_v1.json")
_IDENTITY = re.compile(r"\(identidade:\s*(?P<identity>[^)]+)\)")


def audit_artifact(
    artifact: dict[str, Any], cases_by_id: dict[str, Any]
) -> dict[str, Any]:
    """Produz classificação estrita com dados serializados no artefato."""
    records = []
    for record in artifact["results"]:
        case = cases_by_id[record["case_id"]]
        result = record["result"]
        outcome = result["outcome"]
        identities = _identities_from_citations(record)
        fidelity = assess_target_fidelity(case, identities)
        if case.expect_answer and outcome == "ANSWERED":
            strict = "CORRECT_ANSWER" if fidelity.passed else "WRONG_TARGET"
            failure_stage = None if fidelity.passed else "TARGET_FIDELITY"
        elif case.expect_answer and outcome == "ABSTAINED":
            strict = "FALSE_ABSTENTION"
            failure_stage = result.get("failure_stage")
        elif not case.expect_answer and outcome == "ABSTAINED":
            strict = "CORRECT_ABSTENTION"
            failure_stage = None
        elif not case.expect_answer and outcome == "ANSWERED":
            strict = "UNSAFE_ANSWER"
            failure_stage = result.get("failure_stage")
        else:
            strict = "TECHNICAL_FAILURE"
            failure_stage = result.get("failure_stage")
        records.append(
            {
                "case_id": case.id,
                "legacy_classification": result.get("classification"),
                "strict_classification": strict,
                "allowed_targets": list(fidelity.allowed_targets),
                "used_evidence_identity_keys": list(
                    fidelity.used_evidence_identity_keys
                ),
                "target_fidelity_pass": fidelity.passed,
                "reason": fidelity.reason,
                "failure_stage": failure_stage,
            }
        )
    return {
        "raw_artifact_unchanged": "YES",
        "cases": len(records),
        "correct_answers": sum(
            item["strict_classification"] == "CORRECT_ANSWER" for item in records
        ),
        "correct_abstentions": sum(
            item["strict_classification"] == "CORRECT_ABSTENTION" for item in records
        ),
        "false_abstentions": sum(
            item["strict_classification"] == "FALSE_ABSTENTION" for item in records
        ),
        "wrong_targets": sum(
            item["strict_classification"] == "WRONG_TARGET" for item in records
        ),
        "unsafe_answers": sum(
            item["strict_classification"] == "UNSAFE_ANSWER" for item in records
        ),
        "answered_cases": sum(
            item["strict_classification"] in {"CORRECT_ANSWER", "WRONG_TARGET"}
            for item in records
        ),
        "target_fidelity_passes": sum(
            item["target_fidelity_pass"] is True for item in records
        ),
        "target_fidelity_failures": sum(
            item["target_fidelity_pass"] is False for item in records
        ),
        "results": records,
    }


def _identities_from_citations(record: dict[str, Any]) -> tuple[str, ...]:
    """Extrai a identidade já serializada no label de citação histórico.

    O artefato da Fase 95 não guardava uma coluna de identidade por EvidenceItem;
    este é o único dado estrutural disponível nele. Execuções futuras usam a
    cadeia EvidenceItem real no runtime, sem esta leitura de compatibilidade.
    """
    by_code = {}
    for citation in record.get("generation", {}).get("citations", []):
        match = _IDENTITY.search(str(citation.get("label", "")))
        if match:
            by_code[citation.get("code")] = match.group("identity")
    codes = [
        code
        for claim in record.get("generation", {}).get("claims", [])
        for code in claim.get("ev", [])
    ]
    return tuple(by_code[code] for code in codes if code in by_code)


def main(artifact_path: Path, output: Path | None = None) -> Path:
    artifact_bytes = artifact_path.read_bytes()
    artifact = json.loads(artifact_bytes)
    _version, cases = load_dataset(DEFAULT_DATASET)
    payload = {
        "artifact": str(artifact_path),
        "raw_artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "dataset": str(DEFAULT_DATASET),
        **audit_artifact(artifact, {case.id: case for case in cases}),
    }
    target = output or artifact_path.with_name("target_fidelity_audit.json")
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    main(arguments.artifact, arguments.output)
