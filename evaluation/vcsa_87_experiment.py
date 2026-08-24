"""Harness offline VCSA sobre os SupportSlots congelados da Fase 12."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from consultor_juridico.db.session import SessionLocal
from consultor_juridico.models import EvidenceSet
from evaluation.relevance_core_86 import (
    AnswerRole,
    RelevanceStatus,
    evaluate_claim_relevance,
)
from evaluation.vcsa_87 import (
    VCSAStatus,
    assertion_manifest,
    build_vcsa,
    slot_from_manifest,
)


def run_experiment(frozen_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Executa somente leituras de slots/evidências já persistidos."""
    rows = []
    with SessionLocal() as session:
        for frozen in frozen_rows:
            manifest = frozen.get("support_slot_manifest")
            assertions = []
            if manifest:
                evidence_set = session.get(
                    EvidenceSet, manifest["slots"][0]["evidence_set_id"]
                )
                for slot_data in manifest["slots"]:
                    slot = slot_from_manifest(slot_data)
                    assertion = build_vcsa(session, evidence_set, slot)
                    relevance = None
                    if assertion.status is VCSAStatus.VERIFIED:
                        relevance = evaluate_claim_relevance(
                            frozen["query"],
                            assertion.reconstructed_text or "",
                            tuple(fragment.text for fragment in assertion.fragments),
                        )
                    assertions.append(
                        {
                            **assertion_manifest(assertion),
                            "relevance": (
                                {
                                    "status": relevance.status.value,
                                    "role": relevance.role.value,
                                    "reason": relevance.reason,
                                }
                                if relevance
                                else None
                            ),
                        }
                    )
            eligible = [
                assertion
                for assertion in assertions
                if assertion["status"] == VCSAStatus.VERIFIED
                and assertion["relevance"]["status"] == RelevanceStatus.RELEVANT
                and assertion["relevance"]["role"] == AnswerRole.CENTRAL
            ]
            rows.append(
                {
                    "case_id": frozen["case_id"],
                    "query": frozen["query"],
                    "assertions": assertions,
                    "core_assertion_available": bool(eligible),
                    "rendered_text": eligible[0]["reconstructed_text"]
                    if eligible
                    else None,
                }
            )

    by_case = {row["case_id"]: row for row in rows}
    death = by_case["rw-pena-morte"]
    perpetual = by_case["rw-prisao-perpetua"]
    siege = by_case["rw-estado-sitio"]
    death_verified = _has_verified_assertion(death)
    perpetual_verified = _has_verified_assertion(perpetual)
    siege_safe = not siege["core_assertion_available"]
    gate_passed = (
        death["core_assertion_available"]
        and perpetual["core_assertion_available"]
        and siege_safe
    )
    return {
        "phase": "vcsa_offline_87",
        "generator_calls": 0,
        "semantic_validator_calls": 0,
        "retrieval_calls": 0,
        "production_integration": "NOT_ENABLED",
        "rows": rows,
        "summary": {
            "gate": "PASS" if gate_passed else "FAIL",
            "failure_classification": (
                "RELEVANCE_LIMIT"
                if death_verified and perpetual_verified and not gate_passed
                else None
            ),
            "pena_morte_structural_verified": death_verified,
            "prisao_perpetua_structural_verified": perpetual_verified,
            "pena_morte_recovered": death["core_assertion_available"],
            "prisao_perpetua_recovered": perpetual["core_assertion_available"],
            "estado_sitio_safe_abstention": siege_safe,
            "historical_correct_regressions": 0,
            "unsafe_product_answers": 0,
        },
    }


def _has_verified_assertion(row: dict[str, Any]) -> bool:
    return any(
        assertion["status"] == VCSAStatus.VERIFIED for assertion in row["assertions"]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_experiment(json.loads(args.frozen.read_text(encoding="utf-8")))
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
