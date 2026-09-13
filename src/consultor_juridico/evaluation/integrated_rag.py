"""Primeira medição Integrated DEV do pipeline RAG real do MVP2."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from statistics import median
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
    case_application_result,
    parse_answer_contract,
    validate_citations,
)
from consultor_juridico.application.retrieval.ports import SearchUnitRetriever
from consultor_juridico.domain.rag import (
    CitationStatus,
    QueryMode,
    RagQueryRequest,
)
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


class IntegratedDevProfile(StrEnum):
    V1 = "integrated-dev-v1"
    TWO_MODE_V2 = "integrated-dev-v2-two-mode"


def _load_query_mode_mapping(
    path: Path, *, dataset_sha256: str
) -> tuple[str, dict[str, QueryMode]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("dataset_sha256") != dataset_sha256:
        raise ValueError("Query-mode mapping não corresponde ao dataset DEV")
    raw_mapping = payload.get("category_to_mode")
    if not isinstance(raw_mapping, dict):
        raise ValueError("Query-mode mapping inválido")
    expected_categories = {
        "SINGLE_SUPPORT",
        "COMPOSITE_SUPPORT",
        "INSUFFICIENT_EVIDENCE",
        "AMBIGUOUS",
    }
    if set(raw_mapping) != expected_categories:
        raise ValueError("Query-mode mapping não cobre exatamente as categorias DEV")
    mapping = {
        category: QueryMode(mode.lower().replace("_", "-"))
        for category, mode in raw_mapping.items()
    }
    return str(payload["mapping_id"]), mapping


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
    query_mode: QueryMode = QueryMode.LEGAL_RULE,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if query_mode is QueryMode.CASE_APPLICATION:
        started = perf_counter()
        result = case_application_result(
            RagQueryRequest(case.question, version_hash, query_mode)
        )
        candidates = result.retrieved
        evidence = result.evidence
    else:
        request = RetrievalRequest(case.question, version_hash, 10)
        candidates = retriever.search(request)
        evidence = EvidenceAssembler(repository).assemble(version_hash, candidates)
        started = perf_counter()
    retrieved_keys = tuple(
        dict.fromkeys(
            key for candidate in candidates for key in candidate.provision_stable_keys
        )
    )
    evidence_keys = tuple(item.stable_key for item in evidence)
    required = set(case.required_provisions)
    retrieval_covered = required.issubset(retrieved_keys)
    assembly_covered = required.issubset(evidence_keys)

    raw_response: str | None = None
    error_category = None
    parsed = None
    citation_validation = None
    try:
        if query_mode is QueryMode.CASE_APPLICATION:
            parsed = result.output
            citation_validation = result.citation_validation
        elif evidence:
            raw_response = answerer.generate(
                system_prompt=system_prompt_for(PROMPT_VERSION_V2),
                user_prompt=build_user_prompt(case.question, evidence),
            )
            parsed = None
            citation_validation = None
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
            parsed = None
            citation_validation = None
    except Exception as error:  # fronteira de campanha: preservar a falha por caso
        error_category = str(error)
    latency_ms = (perf_counter() - started) * 1000

    json_valid = False
    output_schema_valid = False
    decision_payload_valid = False
    if query_mode is QueryMode.CASE_APPLICATION:
        json_valid = True
        output_schema_valid = True
        decision_payload_valid = True
    elif not error_category:
        try:
            assert raw_response is not None
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
        "query_mode": query_mode.name,
        "expected_decision": case.expected_decision.value,
        "required_provisions": list(case.required_provisions),
        "gold_provisions": list(case.gold_provisions),
        "retrieved_stable_keys": list(retrieved_keys),
        "assembled_evidence_stable_keys": list(evidence_keys),
        "structural_expansion_items": [
            key for key in evidence_keys if key not in retrieved_keys
        ],
        "raw_model_response": raw_response,
        "retrieval_executed": query_mode is QueryMode.LEGAL_RULE,
        "answerer_executed": (query_mode is QueryMode.LEGAL_RULE and bool(evidence)),
        "routing_reason": (
            "CASE_APPLICATION_NOT_SUPPORTED_IN_MVP2"
            if query_mode is QueryMode.CASE_APPLICATION
            else None
        ),
        "model": SELECTED_MODEL if query_mode is QueryMode.LEGAL_RULE else None,
        "model_digest": (
            SELECTED_MODEL_DIGEST if query_mode is QueryMode.LEGAL_RULE else None
        ),
        "freeze_id": FREEZE_ID if query_mode is QueryMode.LEGAL_RULE else None,
        "prompt_identity": (
            f"{PROMPT_NAME}/{PROMPT_VERSION_V2}"
            if query_mode is QueryMode.LEGAL_RULE
            else None
        ),
        "ollama_format": (
            SELECTED_OLLAMA_FORMAT if query_mode is QueryMode.LEGAL_RULE else None
        ),
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
    profile: IntegratedDevProfile = IntegratedDevProfile.V1,
    query_mode_mapping_path: Path | None = None,
) -> dict[str, Any]:
    """Executa uma campanha única e cria artifacts imutáveis."""
    dataset_bytes = dataset_path.read_bytes()
    dataset_sha256 = sha256(dataset_bytes).hexdigest()
    dataset = load_gold_dataset(dataset_path)
    context = repository.context(version_hash)
    if context.legal_act_code != dataset.legal_act_code:
        raise ValueError("ActVersion não corresponde ao ato do dataset DEV")
    retriever.context(version_hash)

    if profile is IntegratedDevProfile.TWO_MODE_V2:
        if query_mode_mapping_path is None:
            raise ValueError("Integrated DEV v2 exige query-mode mapping explícito")
        mapping_id, category_modes = _load_query_mode_mapping(
            query_mode_mapping_path, dataset_sha256=dataset_sha256
        )
        suffix = "v2"
    else:
        mapping_id = None
        category_modes = {
            category: QueryMode.LEGAL_RULE
            for category in {
                "SINGLE_SUPPORT",
                "COMPOSITE_SUPPORT",
                "INSUFFICIENT_EVIDENCE",
                "AMBIGUOUS",
            }
        }
        suffix = "v1"
    paths = {
        "raw": output_dir / f"integrated_dev_raw_{suffix}.json",
        "automatic": output_dir / f"integrated_dev_automatic_{suffix}.json",
        "diagnostic": output_dir / f"integrated_dev_retrieval_diagnostic_{suffix}.json",
        "review": output_dir / f"integrated_dev_human_review_{suffix}.json",
    }
    if profile is IntegratedDevProfile.TWO_MODE_V2:
        paths["comparison"] = output_dir / "integrated_dev_v1_vs_v2_comparison.json"
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(f"Artifacts não podem ser sobrescritos: {existing}")

    automatic_cases = []
    diagnostic_cases = []
    for case in dataset.cases:
        query_mode = category_modes[case.category.value]
        automatic, diagnostic = _evaluate_case(
            case,
            version_hash=version_hash,
            retriever=retriever,
            repository=repository,
            answerer=answerer,
            query_mode=query_mode,
        )
        automatic_cases.append(automatic)
        diagnostic_cases.append(diagnostic)

    metadata = {
        "evaluation": (
            "INTEGRATED_DEV_V2_TWO_MODE_FIRST_MEASUREMENT"
            if profile is IntegratedDevProfile.TWO_MODE_V2
            else "INTEGRATED_DEV_FIRST_MEASUREMENT"
        ),
        "evaluation_profile": profile.value,
        "query_mode_mapping_id": mapping_id,
        "query_mode_mapping_sha256": (
            _sha(query_mode_mapping_path) if query_mode_mapping_path else None
        ),
        "evaluated_at": datetime.now(UTC).isoformat(),
        "dataset": str(dataset_path),
        "dataset_id": dataset.dataset_id,
        "dataset_sha256": dataset_sha256,
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
        "source_kind": "LOCAL_VERSIONED",
        "runtime_web_fetch": "NOT_IMPLEMENTED",
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
        "rubric": [
            "LEGAL_CORRECTNESS",
            "GROUNDEDNESS",
            "COMPLETENESS",
            "MODE_BOUNDARY_CORRECTNESS",
        ],
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
                "mode_boundary_correctness": None,
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
    legal_cases = [
        case for case in automatic_cases if case["query_mode"] == "LEGAL_RULE"
    ]
    case_application_cases = [
        case for case in automatic_cases if case["query_mode"] == "CASE_APPLICATION"
    ]
    legal_latencies = [case["latency_ms"] for case in legal_cases]
    case_latencies = [case["latency_ms"] for case in case_application_cases]
    metrics = {
        "json_valid": sum(check["json_valid"] for check in checks),
        "output_schema_valid": sum(check["output_schema_valid"] for check in checks),
        "decision_payload_valid": sum(
            check["decision_payload_valid"] for check in checks
        ),
        "expected_decision_match": sum(
            check["expected_decision_match"] for check in checks
        ),
        "automatic_pass": sum(case["automatic_pass"] for case in automatic_cases),
        "false_abstention": sum(check["false_abstention"] for check in checks),
        "unsafe_insufficient": sum(check["unsafe_insufficient"] for check in checks),
        "missed_clarification": sum(check["missed_clarification"] for check in checks),
        "invalid_citations": sum(bool(check["invalid_citations"]) for check in checks),
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
            case["checks"]["assembly_required_evidence_covered"] for case in legal_cases
        ),
        "query_mode_match": len(automatic_cases),
        "legal_rule_cases": len(legal_cases),
        "case_application_cases": len(case_application_cases),
        "legal_rule_expected_decision_match": sum(
            case["checks"]["expected_decision_match"] for case in legal_cases
        ),
        "case_application_expected_decision_match": sum(
            case["checks"]["expected_decision_match"] for case in case_application_cases
        ),
        "case_application_clarify_rate": sum(
            case["parsed_decision"] == "CLARIFY" for case in case_application_cases
        ),
        "case_application_retrieval_calls": sum(
            case["retrieval_executed"] for case in case_application_cases
        ),
        "case_application_llm_calls": sum(
            case["answerer_executed"] for case in case_application_cases
        ),
        "case_application_non_empty_citations": sum(
            bool(case["citations"]) for case in case_application_cases
        ),
        "query_mode_policy_violations": sum(
            not (
                case["parsed_decision"] == "CLARIFY"
                and not case["retrieval_executed"]
                and not case["answerer_executed"]
                and not case["citations"]
            )
            for case in case_application_cases
        ),
        "legal_rule_mean_latency_ms": (
            sum(legal_latencies) / len(legal_latencies) if legal_latencies else None
        ),
        "legal_rule_median_latency_ms": (
            median(legal_latencies) if legal_latencies else None
        ),
        "legal_rule_max_latency_ms": max(legal_latencies, default=None),
        "case_application_mean_latency_ms": (
            sum(case_latencies) / len(case_latencies) if case_latencies else None
        ),
        "case_application_median_latency_ms": (
            median(case_latencies) if case_latencies else None
        ),
        "case_application_max_latency_ms": max(case_latencies, default=None),
        "total_llm_generation_time_ms": sum(
            case["latency_ms"] for case in legal_cases if case["answerer_executed"]
        ),
        "timeouts": sum(
            "TIMEOUT" in (case["error_category"] or "") for case in automatic_cases
        ),
        "failure_classes": dict(sorted(failure_counts.items())),
    }
    if profile is IntegratedDevProfile.TWO_MODE_V2:
        v1_path = Path(
            "evaluation/results/integrated_dev_mvp2_v1/integrated_dev_automatic_v1.json"
        )
        v1_cases = json.loads(v1_path.read_text(encoding="utf-8"))["cases"]
        comparison = {
            "metadata": metadata,
            "v1_artifact": str(v1_path),
            "v1_sha256": _sha(v1_path),
            "v1": {
                "expected_decision_match": sum(
                    case["checks"]["expected_decision_match"] for case in v1_cases
                ),
                "automatic_pass": sum(case["automatic_pass"] for case in v1_cases),
                "false_abstention": sum(
                    case["checks"]["false_abstention"] for case in v1_cases
                ),
                "missed_clarification": sum(
                    case["checks"]["missed_clarification"] for case in v1_cases
                ),
                "invalid_citations": sum(
                    bool(case["checks"]["invalid_citations"]) for case in v1_cases
                ),
                "out_of_evidence": sum(
                    bool(case["checks"]["out_of_evidence"]) for case in v1_cases
                ),
                "llm_call_count": sum(
                    bool(case["assembled_evidence_stable_keys"]) for case in v1_cases
                ),
                "risk_01": "OBSERVED",
                "risk_05": "OBSERVED_IN_6_OF_6_AMBIGUOUS_CASES",
            },
            "v2": metrics
            | {
                "risk_01": "CONTAINED_BY_EXPLICIT_QUERY_MODE_CONTRACT",
                "risk_05": "CONTAINED_BY_EXPLICIT_QUERY_MODE_CONTRACT",
            },
        }
        _write_new_json(paths["comparison"], comparison)

    return {
        "paths": {name: str(path) for name, path in paths.items()},
        "sha256": {name: _sha(path) for name, path in paths.items()},
        "metrics": metrics,
    }
