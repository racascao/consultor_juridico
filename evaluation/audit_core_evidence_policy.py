"""Compara políticas determinísticas de Core Evidence em artefato congelado."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from consultor_juridico.consultation.core_evidence import (
    CORE_EVIDENCE_POLICY_A,
    CORE_EVIDENCE_POLICY_V1,
    CORE_EVIDENCE_POLICY_V2,
    select_core_evidence_v2,
)
from consultor_juridico.evaluation.dataset import load_dataset
from consultor_juridico.evaluation.target_fidelity import allowed_targets

DEFAULT_DATASET = Path("evaluation/datasets/real_world_short_v1.json")


def audit_core_evidence_policy(
    artifact: dict[str, Any], cases_by_id: dict[str, Any]
) -> dict[str, Any]:
    records = []
    v1_hits = policy_a_hits = policy_b_hits = 0
    for result in artifact["results"]:
        case = cases_by_id[result["case_id"]]
        if not case.expect_answer:
            continue
        targets = allowed_targets(case)
        selected = [
            item
            for item in result["evidence_selection"]["diagnostics"]
            if item["selected_position"] is not None
        ]
        selected.sort(key=lambda item: item["selected_position"])
        entries = [
            {
                "evidence_code": f"EV{item['selected_position']:03d}",
                "identity_key": item["identity_key"],
                "query_coverage": item["query_coverage"],
                "marginal_coverage": item["marginal_coverage"],
                "base_relevance": item["base_relevance"],
                "final_score": item["final_score"],
                "selected_position": item["selected_position"],
                "is_allowed_target": item["identity_key"] in targets,
            }
            for item in selected
        ]
        v1 = entries[0] if entries else None
        policy_a = _select(entries, marginal=False)
        policy_b = _select(entries, marginal=True)
        v1_hits += bool(v1 and v1["is_allowed_target"])
        policy_a_hits += bool(policy_a and policy_a["is_allowed_target"])
        policy_b_hits += bool(policy_b and policy_b["is_allowed_target"])
        records.append(
            {
                "case_id": case.id,
                "allowed_targets": list(targets),
                "selected_evidence": entries,
                "v1_core_evidence": v1["evidence_code"] if v1 else None,
                "policy_a_core_evidence": policy_a["evidence_code"]
                if policy_a
                else None,
                "policy_b_core_evidence": policy_b["evidence_code"]
                if policy_b
                else None,
            }
        )
    return {
        "raw_artifact_unchanged": "YES",
        "core_evidence_v1_policy": CORE_EVIDENCE_POLICY_V1,
        "policy_a_candidate": CORE_EVIDENCE_POLICY_A,
        "policy_b_candidate": CORE_EVIDENCE_POLICY_V2,
        "core_evidence_v1_target_hits": v1_hits,
        "policy_a_target_hits": policy_a_hits,
        "policy_b_target_hits": policy_b_hits,
        "results": records,
    }


def _select(entries: list[dict[str, Any]], *, marginal: bool) -> dict[str, Any] | None:
    if not entries:
        return None
    if not marginal:
        return max(
            entries,
            key=lambda item: (
                item["query_coverage"],
                item["base_relevance"],
                -item["selected_position"],
            ),
        )
    items = tuple(
        SimpleNamespace(
            evidence_code=item["evidence_code"],
            validation_metadata={
                "query_coverage": item["query_coverage"],
                "marginal_coverage": item["marginal_coverage"],
                "base_relevance": item["base_relevance"],
                "selected_position": item["selected_position"],
            },
        )
        for item in entries
    )
    core = select_core_evidence_v2(items)
    return (
        next(
            (item for item in entries if item["evidence_code"] == core.evidence_code),
            None,
        )
        if core
        else None
    )


def main(artifact_path: Path, output: Path | None = None) -> Path:
    artifact_bytes = artifact_path.read_bytes()
    artifact = json.loads(artifact_bytes)
    _version, cases = load_dataset(DEFAULT_DATASET)
    payload = {
        "artifact": str(artifact_path),
        "raw_artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "dataset": str(DEFAULT_DATASET),
        **audit_core_evidence_policy(artifact, {case.id: case for case in cases}),
    }
    target = output or artifact_path.with_name("core_evidence_policy_audit.json")
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
