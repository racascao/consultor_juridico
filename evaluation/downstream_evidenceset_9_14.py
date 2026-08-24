"""Executa o downstream sobre snapshots A/B sem retrieval nem persistência."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from types import SimpleNamespace

from consultor_juridico.config import settings
from consultor_juridico.consultation.attribution import deterministically_attribute
from consultor_juridico.consultation.errors import LLMResponseError
from consultor_juridico.consultation.llm import OllamaLegalGenerator
from consultor_juridico.consultation.polarity import validate_response_polarity
from consultor_juridico.consultation.semantic import OllamaSemanticSupportValidator


def _items(snapshot: dict) -> tuple[SimpleNamespace, ...]:
    items = []
    for position, value in enumerate(snapshot["selected"], 1):
        items.append(
            SimpleNamespace(
                evidence_code=f"EV{position:03d}",
                text_snapshot=value.get("text_snapshot") or "",
                citation_label=value.get("identity_key", ""),
                source_url="https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
                validation_metadata={
                    "parent_context": value.get("parent_context"),
                    "identity_key": value.get("identity_key"),
                },
            )
        )
    return tuple(items)


def _citation_ok(response, items):
    allowed = {item.evidence_code for item in items}
    return all(
        code in allowed for claim in response.claims for code in claim.evidence_codes
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--snapshots", default="evaluation/results/evidenceset_9_14_AB.json"
    )
    parser.add_argument(
        "--output", default="evaluation/results/e2e_causal_9_14_repetitions.json"
    )
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    snapshots = json.loads(Path(args.snapshots).read_text(encoding="utf-8"))
    wanted = {"rw-liberdade-religiosa", "rw-direito-vida", "rw-estado-sitio"}
    generator = OllamaLegalGenerator(
        settings.ollama_base_url,
        settings.ollama_model,
        settings.consultation_timeout,
        settings.consultation_max_tokens,
    )
    judge = OllamaSemanticSupportValidator(
        settings.ollama_base_url,
        settings.semantic_judge_model or settings.ollama_model,
        settings.consultation_timeout,
    )
    results = []
    for case in snapshots:
        if case["case_id"] not in wanted:
            continue
        for strategy in ("A", "B"):
            items = _items(case["strategies"][strategy])
            for repetition in range(1, args.repetitions + 1):
                started = time.perf_counter()
                row = {
                    "case_id": case["case_id"],
                    "strategy": strategy,
                    "repetition": repetition,
                    "evidence_codes": [item.evidence_code for item in items],
                    "evidence_order": [
                        item.validation_metadata["identity_key"] for item in items
                    ],
                }
                try:
                    response = generator.generate(case["query"], items)
                    row["generator_abstain"] = response.abstain
                    row["claims"] = [
                        {
                            "id": c.claim_code,
                            "text": c.text,
                            "evidence_ids": list(c.evidence_codes),
                        }
                        for c in response.claims
                    ]
                    row["citation_validation"] = _citation_ok(response, items)
                    attribution = deterministically_attribute(response, items)
                    row["attribution"] = {
                        "abstained": attribution.abstained,
                        "changed_claims": attribution.changed_claims,
                        "reasons": list(attribution.reasons),
                    }
                    row["polarity"] = (
                        "NOT_RUN"
                        if response.abstain
                        else validate_response_polarity(response, items).is_valid
                    )
                    if (
                        attribution.abstained
                        or not row["citation_validation"]
                        or row["polarity"] is False
                    ):
                        row["first_failure"] = "ATTRIBUTION_OR_POLARITY"
                        row["final"] = "ABSTAINED"
                    else:
                        semantic = judge.validate(attribution.response, items)
                        row["semantic"] = {
                            "valid": semantic.is_valid,
                            "errors": list(semantic.errors),
                        }
                        row["first_failure"] = None if semantic.is_valid else "SEMANTIC"
                        row["final"] = "ANSWERED" if semantic.is_valid else "ABSTAINED"
                except (LLMResponseError, RuntimeError, TimeoutError) as exc:
                    row["error"] = str(exc)
                    row["first_failure"] = "TECHNICAL"
                    row["final"] = "ABSTAINED"
                row["latency_seconds"] = time.perf_counter() - started
                results.append(row)
                print(case["case_id"], strategy, repetition, row["final"], flush=True)
    Path(args.output).write_text(
        json.dumps(
            {"repetitions": args.repetitions, "results": results},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
