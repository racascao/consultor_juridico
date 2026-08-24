"""Diagnóstico congelado de abstention do generator (Fase 9.19)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from consultor_juridico.config import settings
from consultor_juridico.consultation.attribution import deterministically_attribute
from consultor_juridico.consultation.llm import OllamaLegalGenerator
from consultor_juridico.consultation.polarity import validate_response_polarity
from consultor_juridico.consultation.semantic import OllamaSemanticSupportValidator
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.models import EvidenceSet

ROOT = Path(__file__).parents[1]
CASES = ("rw-racismo", "rw-direito-vida")
P1_SUFFIX = (
    "\nSe as evidências contêm material suficiente para responder por paráfrase "
    "fiel ou síntese direta, responda. Use abstain somente quando não for "
    "possível produzir uma resposta materialmente suportada pelas evidências."
)


def run_case(case_id: str, evidence_set: EvidenceSet, *, prompt_variant: str):
    generator = OllamaLegalGenerator(
        settings.ollama_base_url,
        settings.ollama_model,
        settings.consultation_timeout,
        settings.consultation_max_tokens,
    )
    if prompt_variant == "P1":
        original = generator.generate

        def generate(question, items, *, correction=()):
            return original(question + P1_SUFFIX, items, correction=correction)

        generator.generate = generate  # type: ignore[method-assign]
    validator = OllamaSemanticSupportValidator(
        settings.ollama_base_url,
        settings.semantic_judge_model or settings.ollama_model,
        settings.consultation_timeout,
    )
    items = tuple(evidence_set.items)
    rows = []
    for repetition in range(1, 6):
        started = time.perf_counter()
        try:
            response = generator.generate(evidence_set.query_text, items)
            row = {
                "repetition": repetition,
                "abstain": response.abstain,
                "claims": [
                    {
                        "id": c.claim_code,
                        "text": c.text,
                        "evidence_ids": list(c.evidence_codes),
                    }
                    for c in response.claims
                ],
                "raw_response": response.answer,
                "json_valid": True,
                "error": None,
            }
            if not response.abstain:
                attribution = deterministically_attribute(response, items)
                row["attribution"] = {
                    "abstained": attribution.abstained,
                    "reasons": list(attribution.reasons),
                }
                if not attribution.abstained:
                    polarity = validate_response_polarity(attribution.response, items)
                    row["polarity"] = [
                        {
                            "status": x.status.value,
                            "reason": x.reason,
                            "reason_code": x.reason_code.value
                            if x.reason_code
                            else None,
                        }
                        for x in polarity.results
                    ]
                    semantic = validator.validate(attribution.response, items)
                    row["semantic"] = {
                        "valid": semantic.is_valid,
                        "error": semantic.technical_error,
                        "claims": [
                            {
                                "id": x.claim_code,
                                "status": x.status.value,
                                "reason": x.reason,
                            }
                            for x in semantic.claims
                        ],
                    }
            rows.append(row)
        except Exception as exc:  # diagnóstico preserva falhas do harness
            rows.append(
                {
                    "repetition": repetition,
                    "abstain": None,
                    "claims": [],
                    "raw_response": None,
                    "json_valid": False,
                    "error": str(exc),
                }
            )
        rows[-1]["latency_seconds"] = time.perf_counter() - started
    return rows


def main() -> None:
    e2e = json.loads(
        (ROOT / "evaluation/results/real_world_short_e2e_9_18.json").read_text()
    )
    ids = {
        x["case_id"]: x["generation"]["evidence_set_id"]
        for x in e2e["results"]
        if x["case_id"] in CASES
    }
    session = SessionLocal()
    frozen = {}
    repetitions = {}
    counterfactual = {}
    for case_id in CASES:
        evidence_set = session.get(EvidenceSet, ids[case_id])
        frozen[case_id] = {
            "evidence_set_id": str(evidence_set.id),
            "question": evidence_set.query_text,
            "items": [
                {
                    "code": x.evidence_code,
                    "text_snapshot": x.text_snapshot,
                    "parent_context": (x.validation_metadata or {}).get(
                        "parent_context"
                    ),
                    "citation_label": x.citation_label,
                }
                for x in evidence_set.items
            ],
            "configuration": {
                "generator": settings.ollama_model,
                "semantic_judge": settings.semantic_judge_model,
                "embedding": settings.embedding_model,
                "evidence_limit": 3,
            },
        }
        repetitions[case_id] = {
            "P0": run_case(case_id, evidence_set, prompt_variant="P0")
        }
        p0 = repetitions[case_id]["P0"]
        if all(row.get("abstain") is True for row in p0):
            counterfactual[case_id] = {
                "P1": run_case(case_id, evidence_set, prompt_variant="P1")
            }
    (ROOT / "evaluation/results/generator_abstention_9_19_frozen.json").write_text(
        json.dumps(frozen, ensure_ascii=False, indent=2) + "\n"
    )
    (ROOT / "evaluation/results/generator_abstention_9_19_repetitions.json").write_text(
        json.dumps(repetitions, ensure_ascii=False, indent=2) + "\n"
    )
    (
        ROOT / "evaluation/results/generator_abstention_9_19_prompt_counterfactual.json"
    ).write_text(json.dumps(counterfactual, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
