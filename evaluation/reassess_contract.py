"""Reavalia Target Fidelity de um artefato já congelado, sem executar pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from consultor_juridico.evaluation.dataset import load_dataset
from consultor_juridico.evaluation.target_fidelity import assess_target_fidelity


def reassess(artifact_path: Path, dataset_path: Path) -> dict[str, Any]:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    _, cases = load_dataset(dataset_path)
    by_id = {case.id: case for case in cases}
    results = []
    for row in artifact["results"]:
        case = by_id[row["case_id"]]
        used = row.get("target_fidelity", {}).get("used_evidence_identity_keys", [])
        fidelity = assess_target_fidelity(case, used)
        outcome = row["result"]["outcome"]
        if case.expect_answer and outcome == "ANSWERED":
            classification = "CORRECT_ANSWER" if fidelity.passed else "WRONG_TARGET"
        elif case.expect_answer:
            classification = "FALSE_ABSTENTION"
        elif outcome == "ABSTAINED":
            classification = "CORRECT_ABSTENTION"
        else:
            classification = "UNSAFE_ANSWER"
        results.append(
            {
                "case_id": case.id,
                "classification": classification,
                "retrieval_hit": row.get("retrieval", {}).get("hit"),
                "target_fidelity": fidelity.passed,
            }
        )
    answered = [x for x in results if by_id[x["case_id"]].expect_answer]
    hits = [x for x in answered if x["retrieval_hit"]]
    return {
        "evaluation_mode": "OFFLINE_CONTRACT_REASSESSMENT",
        "source_artifact_sha256": hashlib.sha256(
            artifact_path.read_bytes()
        ).hexdigest(),
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "results": results,
        "correct_answers": sum(
            x["classification"] == "CORRECT_ANSWER" for x in results
        ),
        "correct_abstentions": sum(
            x["classification"] == "CORRECT_ABSTENTION" for x in results
        ),
        "false_abstentions": sum(
            x["classification"] == "FALSE_ABSTENTION" for x in results
        ),
        "wrong_targets": sum(x["classification"] == "WRONG_TARGET" for x in results),
        "unsafe_answers": sum(x["classification"] == "UNSAFE_ANSWER" for x in results),
        "projected_hit_at_10": len(hits) / len(answered),
    }
