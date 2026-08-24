"""Experimento congelado da fronteira Polarity -> Semantic (Fase 9.17)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from consultor_juridico.consultation.polarity import (
    PolarityReason,
    PolarityStatus,
    validate_polarity,
)
from consultor_juridico.consultation.semantic import (
    OllamaSemanticSupportValidator,
)
from consultor_juridico.consultation.types import GeneratedClaim, GeneratedResponse

ROOT = Path(__file__).parents[1]


def main() -> None:
    frozen = json.loads(
        (ROOT / "evaluation/results/evidenceset_9_14_AB.json").read_text()
    )
    runs = json.loads(
        (ROOT / "evaluation/results/e2e_causal_9_14_repetitions.json").read_text()
    )["results"]
    by_case = {item["case_id"]: item for item in frozen}
    validator = OllamaSemanticSupportValidator(
        "http://ollama:11434", "granite4.1:3b", timeout=90
    )
    output = []
    for run in runs:
        if run["case_id"] not in {"rw-direito-vida", "rw-estado-sitio"}:
            continue
        strategy = by_case[run["case_id"]]["strategies"][run["strategy"]]
        items = tuple(
            SimpleNamespace(
                evidence_code=f"EV{i:03d}",
                text_snapshot=candidate["text_snapshot"],
                validation_metadata={"parent_context": candidate.get("parent_context")},
            )
            for i, candidate in enumerate(strategy["candidates"], 1)
        )
        claims = tuple(
            GeneratedClaim(item["id"], item["text"], tuple(item["evidence_ids"]))
            for item in run["claims"]
        )
        response = GeneratedResponse("", claims, run["generator_abstain"])
        polarity = tuple(validate_polarity(claim, items) for claim in claims)
        routed = [
            result.status is PolarityStatus.CONSISTENT
            or (
                result.status is PolarityStatus.UNRESOLVED
                and result.reason_code is PolarityReason.NO_POLARITY_RELATION
            )
            for result in polarity
        ]
        semantic = None
        if all(routed) and claims:
            semantic = validator.validate(response, items)
        output.append(
            {
                "case_id": run["case_id"],
                "strategy": run["strategy"],
                "repetition": run["repetition"],
                "claims": [
                    {
                        "claim_code": result.claim_code,
                        "evidence_codes": list(result.evidence_codes),
                        "status": result.status.value,
                        "reason_code": result.reason_code.value
                        if result.reason_code
                        else None,
                        "reason": result.reason,
                    }
                    for result in polarity
                ],
                "routed_to_semantic": all(routed),
                "semantic": (
                    {
                        "valid": semantic.is_valid,
                        "error": semantic.technical_error,
                        "claims": [
                            {
                                "claim_code": item.claim_code,
                                "status": item.status.value,
                                "evidence_codes": list(item.evidence_codes),
                                "reason": item.reason,
                            }
                            for item in semantic.claims
                        ],
                    }
                    if semantic is not None
                    else None
                ),
            }
        )
    result = {
        "phase": "9.17",
        "semantic_judge": "granite4.1:3b",
        "executions": output,
        "counts": {
            "analyzed": len(output),
            "no_polarity_relation": sum(
                1
                for run in output
                for claim in run["claims"]
                if claim["reason_code"] == "NO_POLARITY_RELATION"
            ),
            "exception_scope_ambiguity": sum(
                1
                for run in output
                for claim in run["claims"]
                if claim["reason_code"] == "EXCEPTION_SCOPE_AMBIGUITY"
            ),
            "routed_to_semantic": sum(run["routed_to_semantic"] for run in output),
        },
    }
    path = ROOT / "evaluation/results/polarity_boundary_9_17_experiment.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
