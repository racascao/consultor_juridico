"""A/B congelado da Structured Evidence Unit sobre EvidenceSets da Fase 9.18."""

from __future__ import annotations

import json
import time
from argparse import ArgumentParser
from pathlib import Path
from types import SimpleNamespace

from consultor_juridico.config import settings
from consultor_juridico.consultation.attribution import deterministically_attribute
from consultor_juridico.consultation.llm import OllamaLegalGenerator
from consultor_juridico.consultation.polarity import (
    can_route_to_semantic,
    validate_response_polarity,
)
from consultor_juridico.consultation.semantic import OllamaSemanticSupportValidator
from consultor_juridico.consultation.structured_evidence import load_structured_evidence
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.models import EvidenceSet

ROOT = Path(__file__).parents[1]


def _view(item, unit):
    metadata = {
        **(item.validation_metadata or {}),
        "structured_evidence": {
            "source_element_ids": [str(value) for value in unit.source_element_ids],
            "hierarchy": list(unit.hierarchy),
            "sha256": unit.sha256,
            "original_snapshot": unit.original_snapshot,
        },
    }
    return SimpleNamespace(
        id=item.id,
        evidence_code=item.evidence_code,
        text_snapshot=unit.structured_text,
        validation_metadata=metadata,
        citation_label=item.citation_label,
        source_url=item.source_url,
    )


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evaluation/results/structured_evidence_10_ab.json",
    )
    parser.add_argument("--phase", default="10")
    args = parser.parse_args()
    baseline = json.loads(
        (ROOT / "evaluation/results/real_world_short_e2e_9_18.json").read_text()
    )
    generator = OllamaLegalGenerator(
        settings.ollama_base_url,
        settings.ollama_model,
        settings.consultation_timeout,
        settings.consultation_max_tokens,
    )
    semantic_validator = OllamaSemanticSupportValidator(
        settings.ollama_base_url,
        settings.semantic_judge_model or settings.ollama_model,
        settings.consultation_timeout,
    )
    results = []
    for original in baseline["results"]:
        started = time.perf_counter()
        with SessionLocal() as session:
            evidence_set = session.get(
                EvidenceSet, original["generation"]["evidence_set_id"]
            )
            units = tuple(
                load_structured_evidence(session, item) for item in evidence_set.items
            )
            views = tuple(
                _view(item, unit)
                for item, unit in zip(evidence_set.items, units, strict=True)
            )
            sufficient = original["sufficiency"]["is_sufficient"]
            outcome = "ABSTAINED"
            first_failure = original["result"]["failure_stage"]
            raw = None
            attribution_data = None
            polarity_data = None
            semantic_data = None
            invalid_contract = False
            if sufficient and views:
                try:
                    response = generator.generate(original["question"], views)
                    raw = {
                        "answer": response.answer,
                        "abstain": response.abstain,
                        "claims": [
                            {
                                "id": claim.claim_code,
                                "text": claim.text,
                                "evidence_ids": list(claim.evidence_codes),
                            }
                            for claim in response.claims
                        ],
                    }
                    if response.abstain:
                        first_failure = "GENERATOR_ABSTENTION"
                    else:
                        attribution = deterministically_attribute(response, views)
                        attribution_data = {
                            "abstained": attribution.abstained,
                            "reasons": list(attribution.reasons),
                        }
                        if attribution.abstained:
                            first_failure = "ATTRIBUTION_FAILURE"
                        else:
                            polarity = validate_response_polarity(
                                attribution.response, views
                            )
                            polarity_data = [
                                {
                                    "status": value.status.value,
                                    "reason_code": value.reason_code.value
                                    if value.reason_code
                                    else None,
                                }
                                for value in polarity.results
                            ]
                            if not all(
                                can_route_to_semantic(value)
                                for value in polarity.results
                            ):
                                first_failure = "POLARITY_REJECTION"
                            else:
                                semantic = semantic_validator.validate(
                                    attribution.response, views
                                )
                                semantic_data = {
                                    "valid": semantic.is_valid,
                                    "error": semantic.technical_error,
                                    "claims": [
                                        {
                                            "id": value.claim_code,
                                            "status": value.status.value,
                                        }
                                        for value in semantic.claims
                                    ],
                                }
                                if semantic.is_valid:
                                    outcome = "ANSWERED"
                                    first_failure = None
                                else:
                                    first_failure = "SEMANTIC_REJECTION"
                except Exception as exc:
                    invalid_contract = True
                    first_failure = "INVALID_CONTRACT"
                    raw = {"error": str(exc)}
            expect = original["expect_answer"]
            if expect and outcome == "ANSWERED":
                classification = "CORRECT_ANSWER"
            elif not expect and outcome == "ABSTAINED":
                classification = "CORRECT_ABSTENTION"
            elif expect:
                classification = "FALSE_ABSTENTION"
            else:
                classification = "UNSAFE_ANSWER"
            results.append(
                {
                    "case_id": original["case_id"],
                    "question": original["question"],
                    "expect_answer": expect,
                    "classification": classification,
                    "outcome": outcome,
                    "first_failure": first_failure,
                    "invalid_contract": invalid_contract,
                    "generator": raw,
                    "attribution": attribution_data,
                    "polarity": polarity_data,
                    "semantic": semantic_data,
                    "structured_units": [
                        {
                            "evidence_code": unit.evidence_code,
                            "source_element_ids": [
                                str(value) for value in unit.source_element_ids
                            ],
                            "identity_key": unit.identity_key,
                            "hierarchy": list(unit.hierarchy),
                            "original_snapshot": unit.original_snapshot,
                            "structured_text": unit.structured_text,
                            "sha256": unit.sha256,
                        }
                        for unit in units
                    ],
                    "elapsed_seconds": time.perf_counter() - started,
                }
            )
    payload = {
        "phase": args.phase,
        "strategy_a": "real_world_short_e2e_9_18.json",
        "strategy_b": "StructuredEvidenceUnit",
        "generator": settings.ollama_model,
        "semantic_judge": settings.semantic_judge_model,
        "results": results,
        "metrics": {
            "correct_answers": sum(
                value["classification"] == "CORRECT_ANSWER" for value in results
            ),
            "false_abstentions": sum(
                value["classification"] == "FALSE_ABSTENTION" for value in results
            ),
            "correct_abstentions": sum(
                value["classification"] == "CORRECT_ABSTENTION" for value in results
            ),
            "unsafe_answers": sum(
                value["classification"] == "UNSAFE_ANSWER" for value in results
            ),
            "invalid_contracts": sum(value["invalid_contract"] for value in results),
            "attribution_success": sum(
                value["attribution"] is not None
                and not value["attribution"]["abstained"]
                for value in results
            ),
            "polarity_rejections": sum(
                value["first_failure"] == "POLARITY_REJECTION" for value in results
            ),
            "semantic_success": sum(
                value["semantic"] is not None and value["semantic"]["valid"]
                for value in results
            ),
        },
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
