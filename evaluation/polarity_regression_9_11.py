"""Reavalia claims históricas congeladas contra o guard da Fase 9.10."""

import json
from pathlib import Path
from types import SimpleNamespace

from consultor_juridico.consultation.polarity import validate_polarity
from consultor_juridico.consultation.types import GeneratedClaim

source = json.loads(
    Path("evaluation/results/variance_9_7_deterministic.json").read_text()
)
cases = []
for case in source["cases"]:
    evidence = tuple(
        SimpleNamespace(
            evidence_code=item["evidence_code"],
            text_snapshot=item["text_snapshot"],
            validation_metadata=item.get("validation_metadata", {}),
        )
        for item in case["evidence"]
    )
    runs = []
    for run in case["generator_variance"]["runs"]:
        parsed = run.get("deterministic_attribution", {}).get("parsed") or {}
        results = []
        for claim in parsed.get("claims", []):
            result = validate_polarity(
                GeneratedClaim(
                    claim["claim_code"], claim["text"], tuple(claim["evidence_codes"])
                ),
                evidence,
            )
            results.append(
                {
                    "claim_code": claim["claim_code"],
                    "claim": claim["text"],
                    "evidence_codes": list(result.evidence_codes),
                    "status": result.status.value,
                    "reason": result.reason,
                }
            )
        runs.append({"signature": run.get("signature"), "claims": results})
    cases.append({"case_id": case["case_id"], "runs": runs})

output = {
    "phase": "9.11",
    "source": "variance_9_7_deterministic.json",
    "guard": "polarity_guard_v1",
    "cases": cases,
    "contradicted_claims": sum(
        item["status"] == "CONTRADICTED"
        for case in cases
        for run in case["runs"]
        for item in run["claims"]
    ),
    "unresolved_claims": sum(
        item["status"] == "UNRESOLVED"
        for case in cases
        for run in case["runs"]
        for item in run["claims"]
    ),
}
Path("evaluation/results/polarity_regression_9_11.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2) + "\n"
)
