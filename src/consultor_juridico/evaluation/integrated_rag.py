"""Primeira medição Integrated DEV do pipeline RAG real do MVP2."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any

from consultor_juridico.application.gold_evidence.prompt import (
    PROMPT_NAME,
    PROMPT_VERSION_V2,
    build_user_prompt,
    system_prompt_for,
)
from consultor_juridico.application.rag.ports import (
    FrozenAnswerer,
    StructuralEvidenceRepository,
)
from consultor_juridico.application.rag.services import (
    EvidenceAssembler,
    InvalidAnswerContractError,
    parse_answer_contract,
    validate_citations,
)
from consultor_juridico.application.retrieval.ports import SearchUnitRetriever
from consultor_juridico.domain.rag import CitationStatus
from consultor_juridico.domain.retrieval import RetrievalRequest
from consultor_juridico.evaluation.gold_evidence import (
    GoldEvidenceCase,
    ModelDecision,
    load_gold_dataset,
)
from consultor_juridico.evaluation.selected_answerer import (
    FREEZE_ID,
    SELECTED_MODEL,
    SELECTED_MODEL_DIGEST,
    SELECTED_OLLAMA_FORMAT,
)


def _write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"O artefato não pode ser sobrescrito: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _failure_class(
    *,
    retrieval_covered: bool,
    assembly_covered: bool,
    contract_valid: bool,
    citation_status: CitationStatus | None,
    expected_match: bool,
) -> str | None:
    if not retrieval_covered:
        return "RETRIEVAL_MISS"
    if not assembly_covered:
        return "EVIDENCE_ASSEMBLY_MISS"
    if not contract_valid:
        return "ANSWERER_OUTPUT_CONTRACT_FAILURE"
    if citation_status is not CitationStatus.VALID:
        return "CITATION_FAILURE"
    if not expected_match:
        return "ANSWERER_DECISION_FAILURE"
    return "MATERIAL_REVIEW_REQUIRED"


def _evaluate_case(
    case: GoldEvidenceCase,
    *,
    version_hash: str,
    retriever: SearchUnitRetriever,
    repository: StructuralEvidenceRepository,
    answerer: FrozenAnswerer,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = RetrievalRequest(case.question, version_hash, 10)
    candidates = retriever.search(request)
    evidence = EvidenceAssembler(repository).assemble(version_hash, candidates)
    retrieved_keys = tuple(
        dict.fromkeys(
            key for candidate in candidates for key in candidate.provision_stable_keys
        )
    )
    evidence_keys = tuple(item.stable_key for item in evidence)
    required = set(case.required_provisions)
    retrieval_covered = required.issubset(retrieved_keys)
    assembly_covered = required.issubset(evidence_keys)

    started = perf_counter()
    raw_response = ""
    error_category = None
    try:
        if evidence:
            raw_response = answerer.generate(
                system_prompt=system_prompt_for(PROMPT_VERSION_V2),
                user_prompt=build_user_prompt(case.question, evidence),
            )
        else:
            raw_response = json.dumps(
                {
                    "decision": "ABSTAIN",
                    "answer": (
                        "As evidências locais recuperadas são insuficientes para "
                        "responder."
                    ),
                    "citations": [],
                },
                ensure_ascii=False,
            )
    except Exception as error:  # fronteira de campanha: preservar a falha por caso
        error_category = str(error)
    latency_ms = (perf_counter() - started) * 1000

    json_valid = False
    output_schema_valid = False
    decision_payload_valid = False
    parsed = None
    citation_validation = None
    if not error_category:
        try:
            json.loads(raw_response)
            json_valid = True
            parsed = parse_answer_contract(raw_response)
            output_schema_valid = True
            decision_payload_valid = True
            citation_validation = validate_citations(
                parsed.citations,
                evidence_keys=frozenset(evidence_keys),
                corpus_keys=repository.provision_keys(version_hash),
            )
        except json.JSONDecodeError:
            pass
        except InvalidAnswerContractError as error:
            error_category = str(error)

    model_decision = parsed.decision.value if parsed else None
    citations = list(parsed.citations) if parsed else []
    expected_match = model_decision == case.expected_decision.value
    citation_status = citation_validation.status if citation_validation else None
    invalid = list(citation_validation.invalid_citations) if citation_validation else []
    outside = list(citation_validation.out_of_evidence) if citation_validation else []
    required_covered = required.issubset(citations)
    false_abstention = (
        case.expected_decision is ModelDecision.ANSWER
        and model_decision == ModelDecision.ABSTAIN.value
    )
    unsafe_insufficient = (
        case.expected_decision is ModelDecision.ABSTAIN
        and model_decision == ModelDecision.ANSWER.value
    )
    missed_clarification = (
        case.expected_decision is ModelDecision.CLARIFY
        and model_decision != ModelDecision.CLARIFY.value
    )
    automatic_pass = all(
        (
            json_valid,
            output_schema_valid,
            decision_payload_valid,
            expected_match,
            citation_status is CitationStatus.VALID,
            required_covered,
            not false_abstention,
            not unsafe_insufficient,
            not missed_clarification,
            error_category is None,
        )
    )
    failure_class = _failure_class(
        retrieval_covered=retrieval_covered,
        assembly_covered=assembly_covered,
        contract_valid=output_schema_valid and error_category is None,
        citation_status=citation_status,
        expected_match=expected_match,
    )
    common = {
        "case_id": case.case_id,
        "question": case.question,
        "category": case.category.value,
        "expected_decision": case.expected_decision.value,
        "required_provisions": list(case.required_provisions),
        "gold_provisions": list(case.gold_provisions),
        "retrieved_stable_keys": list(retrieved_keys),
        "assembled_evidence_stable_keys": list(evidence_keys),
        "structural_expansion_items": [
            key for key in evidence_keys if key not in retrieved_keys
        ],
        "raw_model_response": raw_response,
        "parsed_decision": model_decision,
        "answer": parsed.answer if parsed else None,
        "citations": citations,
        "citation_validation": citation_status.value if citation_status else None,
        "latency_ms": latency_ms,
        "error_category": error_category,
    }
    automatic = common | {
        "checks": {
            "json_valid": json_valid,
            "output_schema_valid": output_schema_valid,
            "decision_payload_valid": decision_payload_valid,
            "expected_decision_match": expected_match,
            "required_citation_covered": required_covered,
            "retrieval_required_evidence_covered": retrieval_covered,
            "assembly_required_evidence_covered": assembly_covered,
            "false_abstention": false_abstention,
            "unsafe_insufficient": unsafe_insufficient,
            "missed_clarification": missed_clarification,
            "invalid_citations": invalid,
            "out_of_evidence": outside,
        },
        "automatic_pass": automatic_pass,
        "failure_class": None if automatic_pass else failure_class,
        "material_review": "PENDING" if automatic_pass else "NOT_APPLICABLE",
    }
    diagnostic = {
        "case_id": case.case_id,
        "required_provisions": list(case.required_provisions),
        "retrieval_hits": [
            {
                "rank": candidate.rank,
                "score": candidate.score,
                "unit_key": candidate.unit_key,
                "provision_stable_keys": list(candidate.provision_stable_keys),
            }
            for candidate in candidates
        ],
        "retrieval_required_evidence_covered": retrieval_covered,
        "assembled_evidence_stable_keys": list(evidence_keys),
        "structural_expansion_items": common["structural_expansion_items"],
        "assembly_required_evidence_covered": assembly_covered,
        "failure_class": None if automatic_pass else failure_class,
    }
    return automatic, diagnostic


def run_integrated_dev(
    retriever: SearchUnitRetriever,
    repository: StructuralEvidenceRepository,
    answerer: FrozenAnswerer,
    *,
    dataset_path: Path,
    version_hash: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Executa uma campanha única e cria quatro artifacts imutáveis."""
    dataset_bytes = dataset_path.read_bytes()
    dataset = load_gold_dataset(dataset_path)
    context = repository.context(version_hash)
    if context.legal_act_code != dataset.legal_act_code:
        raise ValueError("ActVersion não corresponde ao ato do dataset DEV")
    retriever.context(version_hash)

    paths = {
        "raw": output_dir / "integrated_dev_raw_v1.json",
        "automatic": output_dir / "integrated_dev_automatic_v1.json",
        "diagnostic": output_dir / "integrated_dev_retrieval_diagnostic_v1.json",
        "review": output_dir / "integrated_dev_human_review_v1.json",
    }
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(f"Artifacts não podem ser sobrescritos: {existing}")

    automatic_cases = []
    diagnostic_cases = []
    for case in dataset.cases:
        automatic, diagnostic = _evaluate_case(
            case,
            version_hash=version_hash,
            retriever=retriever,
            repository=repository,
            answerer=answerer,
        )
        automatic_cases.append(automatic)
        diagnostic_cases.append(diagnostic)

    metadata = {
        "evaluation": "INTEGRATED_DEV_FIRST_MEASUREMENT",
        "evaluated_at": datetime.now(UTC).isoformat(),
        "dataset": str(dataset_path),
        "dataset_id": dataset.dataset_id,
        "dataset_sha256": sha256(dataset_bytes).hexdigest(),
        "case_count": len(dataset.cases),
        "legal_act_code": dataset.legal_act_code,
        "version_hash": version_hash,
        "source_snapshot_sha256": context.source_snapshot_sha256,
        "retrieval_strategy": "POSTGRESQL_FTS_RELAXED_OR_WEIGHTED_COVERAGE",
        "structural_evidence_expansion": "DIRECT_CHILDREN_MAX_8_GLOBAL_MAX_24",
        "model": SELECTED_MODEL,
        "model_digest": SELECTED_MODEL_DIGEST,
        "freeze_id": FREEZE_ID,
        "prompt_identity": f"{PROMPT_NAME}/{PROMPT_VERSION_V2}",
        "ollama_format": SELECTED_OLLAMA_FORMAT,
        "holdout_read": False,
        "tuning_after_measurement": False,
    }
    raw = {
        "metadata": metadata,
        "cases": [
            {key: value for key, value in case.items() if key not in {"checks"}}
            for case in automatic_cases
        ],
    }
    automatic = {"metadata": metadata, "cases": automatic_cases}
    diagnostic = {"metadata": metadata, "cases": diagnostic_cases}
    review = {
        "metadata": metadata,
        "rubric": ["LEGAL_CORRECTNESS", "GROUNDEDNESS", "COMPLETENESS"],
        "cases": [
            {
                "case_id": case["case_id"],
                "question": case["question"],
                "expected_decision": case["expected_decision"],
                "assembled_evidence_stable_keys": case[
                    "assembled_evidence_stable_keys"
                ],
                "answer": case["answer"],
                "citations": case["citations"],
                "legal_correctness": None,
                "groundedness": None,
                "completeness": None,
                "notes": "",
            }
            for case in automatic_cases
        ],
    }
    for name, payload in (
        ("raw", raw),
        ("automatic", automatic),
        ("diagnostic", diagnostic),
        ("review", review),
    ):
        _write_new_json(paths[name], payload)

    checks = [case["checks"] for case in automatic_cases]
    required_total = sum(len(case.required_provisions) for case in dataset.cases)
    retrieved_required = sum(
        len(set(case.required_provisions) & set(result["retrieved_stable_keys"]))
        for case, result in zip(dataset.cases, automatic_cases, strict=True)
    )
    assembled_required = sum(
        len(
            set(case.required_provisions)
            & set(result["assembled_evidence_stable_keys"])
        )
        for case, result in zip(dataset.cases, automatic_cases, strict=True)
    )
    failure_counts = Counter(
        case["failure_class"] for case in automatic_cases if case["failure_class"]
    )
    return {
        "paths": {name: str(path) for name, path in paths.items()},
        "sha256": {name: _sha(path) for name, path in paths.items()},
        "metrics": {
            "json_valid": sum(check["json_valid"] for check in checks),
            "output_schema_valid": sum(
                check["output_schema_valid"] for check in checks
            ),
            "decision_payload_valid": sum(
                check["decision_payload_valid"] for check in checks
            ),
            "expected_decision_match": sum(
                check["expected_decision_match"] for check in checks
            ),
            "automatic_pass": sum(case["automatic_pass"] for case in automatic_cases),
            "false_abstention": sum(check["false_abstention"] for check in checks),
            "unsafe_insufficient": sum(
                check["unsafe_insufficient"] for check in checks
            ),
            "missed_clarification": sum(
                check["missed_clarification"] for check in checks
            ),
            "invalid_citations": sum(
                bool(check["invalid_citations"]) for check in checks
            ),
            "out_of_evidence": sum(bool(check["out_of_evidence"]) for check in checks),
            "required_citation_covered": sum(
                check["required_citation_covered"] for check in checks
            ),
            "retrieval_required_citation_recall": (
                retrieved_required / required_total if required_total else 1.0
            ),
            "evidence_assembly_required_citation_recall": (
                assembled_required / required_total if required_total else 1.0
            ),
            "full_evidence_coverage": sum(
                check["assembly_required_evidence_covered"] for check in checks
            ),
            "failure_classes": dict(sorted(failure_counts.items())),
        },
    }
