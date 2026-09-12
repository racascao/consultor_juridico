"""Harness provider-neutral da capacidade de modelo com Gold Evidence."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from consultor_juridico.application.gold_evidence.ports import (
    GoldEvidenceRepository,
)
from consultor_juridico.application.gold_evidence.prompt import (
    DEFAULT_EXPORT_PROMPT_VERSION,
    PROMPT_NAME,
    PROMPT_VERSION,
    build_user_prompt,
    system_prompt_for,
)
from consultor_juridico.application.gold_evidence.services import (
    MaterializeGoldEvidence,
)
from consultor_juridico.application.gold_evidence.types import GoldEvidenceItem


class GoldCategory(StrEnum):
    SINGLE_SUPPORT = "SINGLE_SUPPORT"
    COMPOSITE_SUPPORT = "COMPOSITE_SUPPORT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    AMBIGUOUS = "AMBIGUOUS"


class ModelDecision(StrEnum):
    ANSWER = "ANSWER"
    ABSTAIN = "ABSTAIN"
    CLARIFY = "CLARIFY"


class GoldEvidenceCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    category: GoldCategory
    question: str
    gold_provisions: tuple[str, ...]
    required_provisions: tuple[str, ...]
    expected_decision: ModelDecision

    @model_validator(mode="after")
    def validate_semantics(self) -> GoldEvidenceCase:
        if not self.case_id.strip() or not self.question.strip():
            raise ValueError("case_id e question são obrigatórios")
        all_keys = self.gold_provisions + self.required_provisions
        if any(not key.strip() for key in all_keys):
            raise ValueError("stable_key vazia")
        if len(set(self.gold_provisions)) != len(self.gold_provisions):
            raise ValueError("gold_provisions contém duplicata")
        if len(set(self.required_provisions)) != len(self.required_provisions):
            raise ValueError("required_provisions contém duplicata")
        if not set(self.required_provisions).issubset(self.gold_provisions):
            raise ValueError(
                "required_provisions deve ser subconjunto de gold_provisions"
            )

        if self.category is GoldCategory.SINGLE_SUPPORT:
            if (
                len(self.gold_provisions) != 1
                or self.required_provisions != self.gold_provisions
                or self.expected_decision is not ModelDecision.ANSWER
            ):
                raise ValueError(
                    "SINGLE_SUPPORT exige uma Provision ANSWER obrigatória"
                )
        elif self.category is GoldCategory.COMPOSITE_SUPPORT:
            if (
                len(self.gold_provisions) < 2
                or set(self.required_provisions) != set(self.gold_provisions)
                or self.expected_decision is not ModelDecision.ANSWER
            ):
                raise ValueError("COMPOSITE_SUPPORT exige ALL_REQUIRED e ANSWER")
        elif self.category is GoldCategory.INSUFFICIENT_EVIDENCE:
            if (
                self.gold_provisions
                or self.required_provisions
                or self.expected_decision is not ModelDecision.ABSTAIN
            ):
                raise ValueError(
                    "INSUFFICIENT_EVIDENCE exige evidência vazia e ABSTAIN"
                )
        elif (
            not self.gold_provisions
            or self.required_provisions
            or self.expected_decision is not ModelDecision.CLARIFY
        ):
            raise ValueError("AMBIGUOUS exige evidência, sem required, e CLARIFY")
        return self


class GoldEvidenceDataset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    legal_act_code: str
    cases: tuple[GoldEvidenceCase, ...]

    @model_validator(mode="after")
    def validate_dataset(self) -> GoldEvidenceDataset:
        if not self.dataset_id.strip() or not self.legal_act_code.strip():
            raise ValueError("dataset_id e legal_act_code são obrigatórios")
        if not self.cases:
            raise ValueError("dataset deve possuir casos")
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("case_id deve ser único")
        return self


class StructuredModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ModelDecision
    answer: str
    citations: tuple[str, ...]


class ResponseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    raw_response: str
    latency_ms: float | None = None


def load_gold_dataset(path: Path) -> GoldEvidenceDataset:
    return GoldEvidenceDataset.model_validate_json(path.read_text(encoding="utf-8"))


def _write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"O artefato não pode ser sobrescrito: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _evidence_payload(item: GoldEvidenceItem) -> dict[str, Any]:
    return {
        "stable_key": item.stable_key,
        "provision_type": item.provision_type,
        "citation_text": item.citation_text,
        "source_locator": item.source_locator,
        "source_snapshot_sha256": item.source_snapshot_sha256,
        "official_url": item.official_url,
        "document_order": item.document_order,
    }


def _validate_targets(
    dataset: GoldEvidenceDataset,
    repository: GoldEvidenceRepository,
    version_hash: str,
) -> None:
    context = repository.context(version_hash)
    if context.legal_act_code != dataset.legal_act_code:
        raise ValueError("ActVersion não pertence ao ato declarado pelo dataset")
    available = repository.provision_keys(version_hash)
    declared = {
        key
        for case in dataset.cases
        for key in case.gold_provisions + case.required_provisions
    }
    missing = sorted(declared - available)
    if missing:
        raise ValueError(f"Gold targets ausentes na ActVersion: {', '.join(missing)}")


def export_gold_bundle(
    repository: GoldEvidenceRepository,
    *,
    dataset_path: Path,
    version_hash: str,
    output_path: Path,
    prompt_version: str = DEFAULT_EXPORT_PROMPT_VERSION,
) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"O artefato não pode ser sobrescrito: {output_path}")
    raw_dataset = dataset_path.read_bytes()
    dataset = load_gold_dataset(dataset_path)
    _validate_targets(dataset, repository, version_hash)
    system_prompt = system_prompt_for(prompt_version)
    materializer = MaterializeGoldEvidence(repository)
    dataset_sha256 = sha256(raw_dataset).hexdigest()
    records = []
    for case in dataset.cases:
        evidence = materializer.execute(
            version_hash=version_hash,
            stable_keys=case.gold_provisions,
        )
        records.append(
            {
                "case_id": case.case_id,
                "category": case.category.value,
                "expected_decision": case.expected_decision.value,
                "required_provisions": list(case.required_provisions),
                "gold_provisions": list(case.gold_provisions),
                "prompt_name": PROMPT_NAME,
                "prompt_version": prompt_version,
                "dataset_sha256": dataset_sha256,
                "version_hash": version_hash,
                "system_prompt": system_prompt,
                "user_prompt": build_user_prompt(case.question, evidence),
                "evidence": [_evidence_payload(item) for item in evidence],
            }
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {
        "dataset_id": dataset.dataset_id,
        "dataset_sha256": dataset_sha256,
        "version_hash": version_hash,
        "prompt_name": PROMPT_NAME,
        "prompt_version": prompt_version,
        "case_count": len(records),
        "category_counts": dict(
            sorted(Counter(case.category.value for case in dataset.cases).items())
        ),
        "output": str(output_path),
    }


def _load_responses(path: Path, expected_ids: set[str]) -> dict[str, ResponseRecord]:
    records: dict[str, ResponseRecord] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            record = ResponseRecord.model_validate_json(line)
        except ValidationError as error:
            raise ValueError(
                f"Resposta JSONL inválida na linha {line_number}"
            ) from error
        if record.case_id in records:
            raise ValueError(f"case_id duplicado nas respostas: {record.case_id}")
        records[record.case_id] = record
    actual_ids = set(records)
    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        extra = sorted(actual_ids - expected_ids)
        raise ValueError(f"Respostas incompletas: missing={missing}; extra={extra}")
    return records


def _parse_model_output(
    raw_response: str,
) -> tuple[bool, bool, StructuredModelOutput | None]:
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError:
        return False, False, None
    decision_valid = isinstance(payload, dict) and payload.get("decision") in {
        decision.value for decision in ModelDecision
    }
    try:
        parsed = StructuredModelOutput.model_validate(payload)
    except ValidationError:
        return True, decision_valid, None
    return True, decision_valid, parsed


def evaluate_structured_response(
    case: GoldEvidenceCase,
    response: ResponseRecord,
    corpus_keys: frozenset[str],
) -> dict[str, Any]:
    json_valid, decision_valid, parsed = _parse_model_output(response.raw_response)
    model_decision = parsed.decision if parsed else None
    citations = set(parsed.citations) if parsed else set()
    gold = set(case.gold_provisions)
    required = set(case.required_provisions)
    invalid_citations = sorted(citations - corpus_keys)
    out_of_evidence = sorted((citations & corpus_keys) - gold)
    false_abstention = (
        case.expected_decision is ModelDecision.ANSWER
        and model_decision is ModelDecision.ABSTAIN
    )
    unsafe_answer = (
        case.expected_decision is ModelDecision.ABSTAIN
        and model_decision is ModelDecision.ANSWER
    )
    missed_clarification = (
        case.expected_decision is ModelDecision.CLARIFY
        and model_decision is not ModelDecision.CLARIFY
    )
    decision_payload_valid = parsed is not None and bool(parsed.answer.strip())
    if parsed and parsed.decision is ModelDecision.ABSTAIN and parsed.citations:
        decision_payload_valid = False
    checks = {
        "json_valid": json_valid,
        "decision_valid": decision_valid,
        "output_schema_valid": parsed is not None,
        "decision_payload_valid": decision_payload_valid,
        "expected_decision_match": model_decision is case.expected_decision,
        "citations_exist_in_gold_evidence": citations.issubset(gold),
        "no_invalid_citations": not invalid_citations,
        "no_out_of_evidence_citations": not out_of_evidence,
        "required_citations_covered": required.issubset(citations),
        "false_abstention": false_abstention,
        "unsafe_answer_on_insufficient": unsafe_answer,
        "missed_clarification": missed_clarification,
    }
    positive_checks = (
        checks["json_valid"],
        checks["decision_valid"],
        checks["output_schema_valid"],
        checks["decision_payload_valid"],
        checks["expected_decision_match"],
        checks["citations_exist_in_gold_evidence"],
        checks["no_invalid_citations"],
        checks["no_out_of_evidence_citations"],
        checks["required_citations_covered"],
        not checks["false_abstention"],
        not checks["unsafe_answer_on_insufficient"],
        not checks["missed_clarification"],
    )
    automatic_pass = all(positive_checks)
    return {
        "case_id": case.case_id,
        "category": case.category.value,
        "question": case.question,
        "expected_decision": case.expected_decision.value,
        "model_decision": model_decision.value if model_decision else None,
        "gold_provisions": list(case.gold_provisions),
        "required_provisions": list(case.required_provisions),
        "raw_response": response.raw_response,
        "latency_ms": response.latency_ms,
        "parsed_response": parsed.model_dump(mode="json") if parsed else None,
        "invalid_citations": invalid_citations,
        "out_of_evidence_citations": out_of_evidence,
        "automatic_checks": checks,
        "automatic_pass": automatic_pass,
        "final_status": "PENDING_HUMAN_REVIEW" if automatic_pass else "FAIL",
    }


def human_review_path_for(automatic_output_path: Path) -> Path:
    return automatic_output_path.with_name(
        f"{automatic_output_path.stem}_human_review.json"
    )


def validate_gold_responses(
    repository: GoldEvidenceRepository,
    *,
    dataset_path: Path,
    version_hash: str,
    responses_path: Path,
    output_path: Path,
    case_ids: frozenset[str] | None = None,
    prompt_version: str = PROMPT_VERSION,
) -> tuple[dict[str, Any], Path]:
    if output_path.exists():
        raise FileExistsError(f"O artefato não pode ser sobrescrito: {output_path}")
    review_path = human_review_path_for(output_path)
    if review_path.exists():
        raise FileExistsError(f"O artefato não pode ser sobrescrito: {review_path}")
    raw_dataset = dataset_path.read_bytes()
    dataset = load_gold_dataset(dataset_path)
    _validate_targets(dataset, repository, version_hash)
    all_case_ids = {case.case_id for case in dataset.cases}
    expected_ids = case_ids if case_ids is not None else frozenset(all_case_ids)
    if not expected_ids or not expected_ids.issubset(all_case_ids):
        raise ValueError("Subset de validação vazio ou alheio ao dataset")
    selected_cases = [case for case in dataset.cases if case.case_id in expected_ids]
    responses = _load_responses(responses_path, set(expected_ids))
    parsed_responses = (
        _parse_model_output(response.raw_response)[2] for response in responses.values()
    )
    citations = frozenset(
        citation
        for parsed in parsed_responses
        if parsed is not None
        for citation in parsed.citations
    )
    repository.validate_citation_namespace(citations)
    corpus_keys = repository.provision_keys(version_hash)
    materializer = MaterializeGoldEvidence(repository)
    evaluated = [
        evaluate_structured_response(case, responses[case.case_id], corpus_keys)
        for case in selected_cases
    ]
    result = {
        "metadata": {
            "dataset_id": dataset.dataset_id,
            "dataset_sha256": sha256(raw_dataset).hexdigest(),
            "responses_sha256": sha256(responses_path.read_bytes()).hexdigest(),
            "version_hash": version_hash,
            "prompt_name": PROMPT_NAME,
            "prompt_version": prompt_version,
            "evaluated_at": datetime.now(UTC).isoformat(),
            "case_count": len(evaluated),
        },
        "cases": evaluated,
    }
    review = {
        "metadata": result["metadata"],
        "cases": [
            {
                "case_id": case.case_id,
                "category": case.category.value,
                "question": case.question,
                "expected_decision": case.expected_decision.value,
                "evidence": [
                    _evidence_payload(item)
                    for item in materializer.execute(
                        version_hash=version_hash,
                        stable_keys=case.gold_provisions,
                    )
                ],
                "raw_response": responses[case.case_id].raw_response,
                "legal_correctness": None,
                "groundedness": None,
                "completeness": None,
                "comments": "",
            }
            for case in selected_cases
        ],
    }
    _write_new_json(output_path, result)
    _write_new_json(review_path, review)
    return result, review_path


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def summarize_gold_review(
    *,
    automatic_evaluation_path: Path,
    human_review_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    automatic = json.loads(automatic_evaluation_path.read_text(encoding="utf-8"))
    review = json.loads(human_review_path.read_text(encoding="utf-8"))
    if review.get("metadata") != automatic.get("metadata"):
        raise ValueError("Metadata da human review diverge da avaliação automática")

    automatic_case_list = automatic["cases"]
    review_case_list = review["cases"]
    automatic_case_ids = [item["case_id"] for item in automatic_case_list]
    review_case_ids = [item["case_id"] for item in review_case_list]
    if len(automatic_case_ids) != len(set(automatic_case_ids)):
        raise ValueError("Avaliação automática possui case_id duplicado")
    if len(review_case_ids) != len(set(review_case_ids)):
        raise ValueError("Human review possui case_id duplicado")

    automatic_cases = {item["case_id"]: item for item in automatic_case_list}
    review_cases = {item["case_id"]: item for item in review_case_list}
    if set(automatic_cases) != set(review_cases):
        raise ValueError("Automatic evaluation e human review possuem casos distintos")

    allowed_legal = {"PASS", "FAIL", "NOT_APPLICABLE"}
    allowed_groundedness = {"PASS", "FAIL"}
    allowed_completeness = {"PASS", "FAIL", "NOT_APPLICABLE"}
    pending = []
    for case_id, item in review_cases.items():
        automatic_case = automatic_cases[case_id]
        for field in ("category", "question", "expected_decision", "raw_response"):
            if item.get(field) != automatic_case.get(field):
                raise ValueError(
                    f"Campo preservado da human review diverge em {case_id}: {field}"
                )
        if "comments" not in item or not isinstance(item["comments"], str):
            raise ValueError(f"COMMENTS inválido: {case_id}")
        if (
            item.get("legal_correctness") not in allowed_legal
            or item.get("groundedness") not in allowed_groundedness
            or item.get("completeness") not in allowed_completeness
        ):
            pending.append(case_id)
    if pending:
        raise ValueError(f"Human review pendente: {', '.join(sorted(pending))}")

    cases = []
    for case_id, automatic_case in automatic_cases.items():
        human = review_cases[case_id]
        if (
            human["legal_correctness"] == "NOT_APPLICABLE"
            and automatic_case["expected_decision"] != ModelDecision.ABSTAIN.value
        ):
            raise ValueError(f"LEGAL_CORRECTNESS N/A inválido: {case_id}")
        if (
            human["completeness"] == "NOT_APPLICABLE"
            and automatic_case["expected_decision"] == ModelDecision.ANSWER.value
        ):
            raise ValueError(f"COMPLETENESS N/A inválido: {case_id}")
        human_pass = (
            human["legal_correctness"] in {"PASS", "NOT_APPLICABLE"}
            and human["groundedness"] == "PASS"
            and human["completeness"] in {"PASS", "NOT_APPLICABLE"}
        )
        final_status = (
            "PASS" if automatic_case["automatic_pass"] and human_pass else "FAIL"
        )
        cases.append(
            automatic_case
            | {
                "human_review": {
                    "legal_correctness": human["legal_correctness"],
                    "groundedness": human["groundedness"],
                    "completeness": human["completeness"],
                    "comments": human.get("comments", ""),
                },
                "final_status": final_status,
            }
        )

    answer_cases = [
        item for item in cases if item["expected_decision"] == ModelDecision.ANSWER
    ]
    composite_cases = [
        item for item in cases if item["category"] == GoldCategory.COMPOSITE_SUPPORT
    ]
    insufficient_cases = [
        item for item in cases if item["category"] == GoldCategory.INSUFFICIENT_EVIDENCE
    ]
    ambiguous_cases = [
        item for item in cases if item["category"] == GoldCategory.AMBIGUOUS
    ]
    false_abstentions = sum(
        item["automatic_checks"]["false_abstention"] for item in cases
    )
    unsafe_answers = sum(
        item["automatic_checks"]["unsafe_answer_on_insufficient"] for item in cases
    )
    invalid_citations = sum(bool(item["invalid_citations"]) for item in cases)
    out_of_evidence = sum(bool(item["out_of_evidence_citations"]) for item in cases)
    result = {
        "metadata": automatic["metadata"],
        "metrics": {
            "total_cases": len(cases),
            "pass_rate": _rate(
                sum(item["final_status"] == "PASS" for item in cases), len(cases)
            ),
            "decision_accuracy": _rate(
                sum(
                    item["automatic_checks"]["expected_decision_match"]
                    for item in cases
                ),
                len(cases),
            ),
            "answer_case_pass_rate": _rate(
                sum(item["final_status"] == "PASS" for item in answer_cases),
                len(answer_cases),
            ),
            "composite_case_pass_rate": _rate(
                sum(item["final_status"] == "PASS" for item in composite_cases),
                len(composite_cases),
            ),
            "insufficient_evidence_abstention_rate": _rate(
                sum(
                    item["model_decision"] == ModelDecision.ABSTAIN
                    for item in insufficient_cases
                ),
                len(insufficient_cases),
            ),
            "ambiguity_clarification_rate": _rate(
                sum(
                    item["model_decision"] == ModelDecision.CLARIFY
                    for item in ambiguous_cases
                ),
                len(ambiguous_cases),
            ),
            "false_abstention_rate": _rate(false_abstentions, len(answer_cases)),
            "unsafe_answer_rate": _rate(unsafe_answers, len(insufficient_cases)),
            "invalid_citation_rate": _rate(invalid_citations, len(cases)),
            "out_of_evidence_citation_rate": _rate(out_of_evidence, len(cases)),
        },
        "cases": cases,
    }
    _write_new_json(output_path, result)
    return result
