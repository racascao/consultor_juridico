"""Contratos da avaliação isolada com Gold Evidence."""

import json
from collections import Counter
from hashlib import sha256
from inspect import signature
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from consultor_juridico.application.gold_evidence.prompt import (
    DEFAULT_EXPORT_PROMPT_VERSION,
    PROMPT_NAME,
    PROMPT_VERSION,
    PROMPT_VERSION_V1,
    PROMPT_VERSION_V2,
    PROMPT_VERSION_V3,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_V1,
    SYSTEM_PROMPT_V2,
    SYSTEM_PROMPT_V3,
    build_user_prompt,
    system_prompt_for,
)
from consultor_juridico.application.gold_evidence.services import (
    MaterializeGoldEvidence,
)
from consultor_juridico.application.gold_evidence.types import (
    GoldEvidenceContext,
    GoldEvidenceItem,
)
from consultor_juridico.cli.main import app
from consultor_juridico.config import Settings
from consultor_juridico.evaluation.gold_evidence import (
    GoldCategory,
    GoldEvidenceCase,
    ResponseRecord,
    evaluate_structured_response,
    export_gold_bundle,
    human_review_path_for,
    load_gold_dataset,
    summarize_gold_review,
    validate_gold_responses,
)
from consultor_juridico.evaluation.gold_stability import (
    STABILITY_SEEDS,
    export_stability_bundle,
    select_stability_cases,
    summarize_gold_stability,
)

VERSION_HASH = "a" * 64
FROZEN_DATASET_PATH = Path("evaluation/datasets/lei_9784_gold_evidence_dev_v1.json")
FROZEN_DATASET_SHA256 = (
    "68a319031b7ca3f9da912761ab5328ef6bf37251f8750b3e24207c7258622f65"
)
FROZEN_V2_BUNDLE_PATH = Path("evaluation/runs/gold_evidence_input_prompt_v2.jsonl")


def _item(key: str, order: int) -> GoldEvidenceItem:
    return GoldEvidenceItem(
        stable_key=key,
        provision_type="CAPUT",
        citation_text=f"Texto oficial {key}",
        source_locator={"paragraph_start": order, "paragraph_end": order},
        source_snapshot_sha256="b" * 64,
        official_url="https://example.test/lei",
        document_order=order,
    )


class FakeGoldRepository:
    def __init__(self) -> None:
        self.items = {"A": _item("A", 2), "B": _item("B", 1), "C": _item("C", 3)}
        self.requested: list[tuple[str, tuple[str, ...]]] = []

    def context(self, version_hash: str) -> GoldEvidenceContext:
        if version_hash != VERSION_HASH:
            raise LookupError("ActVersion não encontrada")
        return GoldEvidenceContext(
            "ACT", version_hash, "b" * 64, "https://example.test/lei"
        )

    def materialize(
        self, version_hash: str, stable_keys: tuple[str, ...]
    ) -> tuple[GoldEvidenceItem, ...]:
        self.context(version_hash)
        self.requested.append((version_hash, stable_keys))
        return tuple(
            sorted(
                (self.items[key] for key in stable_keys if key in self.items),
                key=lambda item: item.document_order,
            )
        )

    def provision_keys(self, version_hash: str) -> frozenset[str]:
        self.context(version_hash)
        return frozenset(self.items)

    def validate_citation_namespace(self, citations: frozenset[str]) -> None:
        """O fake representa um namespace integral."""


def _case_payload(**changes) -> dict:
    payload = {
        "case_id": "GOLD-001",
        "category": "SINGLE_SUPPORT",
        "question": "Qual é a regra?",
        "gold_provisions": ["A"],
        "required_provisions": ["A"],
        "expected_decision": "ANSWER",
    }
    payload.update(changes)
    return payload


def _dataset(path: Path, cases: list[dict]) -> Path:
    path.write_text(
        json.dumps(
            {"dataset_id": "gold_test_v1", "legal_act_code": "ACT", "cases": cases}
        ),
        encoding="utf-8",
    )
    return path


def _response(case_id: str, decision: str, citations: list[str]) -> ResponseRecord:
    return ResponseRecord(
        case_id=case_id,
        raw_response=json.dumps(
            {"decision": decision, "answer": "Resposta", "citations": citations}
        ),
    )


def test_dataset_schema_accepts_all_four_categories(tmp_path):
    dataset = load_gold_dataset(
        _dataset(
            tmp_path / "dataset.json",
            [
                _case_payload(),
                _case_payload(
                    case_id="GOLD-002",
                    category="COMPOSITE_SUPPORT",
                    gold_provisions=["A", "B"],
                    required_provisions=["A", "B"],
                ),
                _case_payload(
                    case_id="GOLD-003",
                    category="INSUFFICIENT_EVIDENCE",
                    gold_provisions=[],
                    required_provisions=[],
                    expected_decision="ABSTAIN",
                ),
                _case_payload(
                    case_id="GOLD-004",
                    category="AMBIGUOUS",
                    gold_provisions=["A", "B"],
                    required_provisions=[],
                    expected_decision="CLARIFY",
                ),
            ],
        )
    )
    assert {case.category for case in dataset.cases} == set(GoldCategory)


def test_frozen_dev_dataset_has_declared_quota_and_no_corpus_text():
    raw = FROZEN_DATASET_PATH.read_bytes()
    dataset = load_gold_dataset(FROZEN_DATASET_PATH)
    assert sha256(raw).hexdigest() == FROZEN_DATASET_SHA256
    assert len(dataset.cases) == 32
    assert Counter(case.category for case in dataset.cases) == {
        GoldCategory.SINGLE_SUPPORT: 12,
        GoldCategory.COMPOSITE_SUPPORT: 8,
        GoldCategory.INSUFFICIENT_EVIDENCE: 6,
        GoldCategory.AMBIGUOUS: 6,
    }
    assert b"citation_text" not in raw
    assert b"version_hash" not in raw


def test_dataset_rejects_duplicate_case_id(tmp_path):
    with pytest.raises(ValidationError, match="case_id deve ser único"):
        load_gold_dataset(
            _dataset(tmp_path / "dataset.json", [_case_payload(), _case_payload()])
        )


def test_dataset_rejects_required_not_in_gold():
    with pytest.raises(ValidationError, match="subconjunto"):
        GoldEvidenceCase.model_validate(_case_payload(required_provisions=["B"]))


def test_dataset_requires_empty_evidence_for_insufficient():
    with pytest.raises(ValidationError, match="evidência vazia"):
        GoldEvidenceCase.model_validate(
            _case_payload(
                category="INSUFFICIENT_EVIDENCE",
                expected_decision="ABSTAIN",
            )
        )


def test_materializer_requires_explicit_version_and_orders_by_document():
    repository = FakeGoldRepository()
    evidence = MaterializeGoldEvidence(repository).execute(
        version_hash=VERSION_HASH, stable_keys=("A", "B")
    )
    assert [item.stable_key for item in evidence] == ["B", "A"]
    with pytest.raises(LookupError, match="ActVersion"):
        MaterializeGoldEvidence(repository).execute(
            version_hash="c" * 64, stable_keys=("A",)
        )


def test_materializer_rejects_unknown_stable_key():
    with pytest.raises(LookupError, match="Provisions ausentes"):
        MaterializeGoldEvidence(FakeGoldRepository()).execute(
            version_hash=VERSION_HASH, stable_keys=("UNKNOWN",)
        )


def test_export_uses_only_repository_and_does_not_leak_case_labels(tmp_path):
    dataset_path = _dataset(tmp_path / "dataset.json", [_case_payload()])
    output_path = tmp_path / "bundle.jsonl"
    result = export_gold_bundle(
        FakeGoldRepository(),
        dataset_path=dataset_path,
        version_hash=VERSION_HASH,
        output_path=output_path,
    )
    record = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["prompt_name"] == PROMPT_NAME
    assert result["prompt_version"] == PROMPT_VERSION_V1
    assert record["system_prompt"] == SYSTEM_PROMPT_V1
    assert "SINGLE_SUPPORT" not in record["system_prompt"]
    assert "SINGLE_SUPPORT" not in record["user_prompt"]
    assert "expected_decision" not in record["user_prompt"]
    assert "Texto oficial A" in record["user_prompt"]
    assert record["evidence"][0]["source_snapshot_sha256"] == "b" * 64


def test_gold_materializer_has_no_retrieval_dependency():
    assert tuple(signature(MaterializeGoldEvidence).parameters) == ("repository",)


def test_prompt_is_generic_and_requests_no_reasoning():
    first = build_user_prompt("Pergunta 1", (_item("A", 1),))
    second = build_user_prompt("Pergunta 2", ())
    assert first != second
    assert "cadeia de pensamento" in SYSTEM_PROMPT
    assert "reasoning" not in SYSTEM_PROMPT.lower()
    assert PROMPT_NAME == "gold-evidence-answering"
    assert PROMPT_VERSION == "3"
    assert SYSTEM_PROMPT == SYSTEM_PROMPT_V3
    assert DEFAULT_EXPORT_PROMPT_VERSION == "1"


def test_prompt_v1_remains_byte_for_byte_preserved():
    assert sha256(SYSTEM_PROMPT_V1.encode()).hexdigest() == (
        "80c8537b3e76e1174ab3518be15e470285e58cf441a2982e298f4c322019d9d5"
    )
    assert system_prompt_for(PROMPT_VERSION_V1) == SYSTEM_PROMPT_V1


def test_prompt_v2_makes_the_output_contract_explicit_without_case_tuning():
    prompt = system_prompt_for(PROMPT_VERSION_V2)
    assert sha256(prompt.encode()).hexdigest() == (
        "700999a44c81d6c4625b238d3ddb0be33f8d3a069c3e3107cefd8a4d02ef8c00"
    )
    required_fragments = (
        "sempre exatamente os três campos",
        "decision, answer e citations",
        "string não vazia",
        "sem nenhum campo adicional",
        "justificativa curta e não vazia",
        "citations deve ser exatamente []",
        "pergunta curta, específica e não vazia",
        "citations deve estar presente",
    )
    assert all(fragment in prompt for fragment in required_fragments)
    assert "cadeia de pensamento" in prompt
    assert "cite TODAS" not in prompt
    assert "required_provisions" not in prompt
    assert "expected_decision" not in prompt
    assert "case_id" not in prompt
    assert "GOLD-" not in prompt
    assert "Art." not in prompt


def test_prompt_v3_only_clarifies_the_exact_citation_value():
    prompt = system_prompt_for(PROMPT_VERSION_V3)
    v2_answer_rule = (
        "- ANSWER: answer deve conter uma resposta concisa e não vazia; citations "
        "deve\n  conter somente EVIDENCE_IDs fornecidos na EVIDENCE."
    )
    v3_answer_rule = (
        """- ANSWER: answer deve conter uma resposta concisa e não vazia; citations deve
  conter somente os valores exatos dos IDs fornecidos na EVIDENCE.

Regra sobre o valor de cada citation:
- EVIDENCE_ID: é somente o rótulo apresentado no bloco EVIDENCE.
- Cada string em citations deve ser somente o valor exibido depois do rótulo.
- O prefixo literal EVIDENCE_ID: não faz parte do valor e não deve ser incluído.
- Não adicione prefixos ou sufixos, não reformule e não invente IDs.

Exemplo abstrato:
Se a EVIDENCE mostrar:
EVIDENCE_ID: EXAMPLE-ID-1

CORRETO:
{"decision":"ANSWER","answer":"Texto da resposta.","citations":["EXAMPLE-ID-1"]}

INCORRETO:
{"decision":"ANSWER","answer":"Texto da resposta.","citations":["""
        '"EVIDENCE_ID: EXAMPLE-ID-1"]}'
    )

    assert prompt == SYSTEM_PROMPT_V2.replace(v2_answer_rule, v3_answer_rule, 1)
    assert prompt != SYSTEM_PROMPT_V2
    assert system_prompt_for(PROMPT_VERSION_V3) == SYSTEM_PROMPT_V3
    assert (
        prompt.split("- ABSTAIN:", 1)[1] == SYSTEM_PROMPT_V2.split("- ABSTAIN:", 1)[1]
    )
    assert 'citations:["EXAMPLE-ID-1"]' not in prompt
    assert '"citations":["EXAMPLE-ID-1"]' in prompt
    assert '"citations":["EVIDENCE_ID: EXAMPLE-ID-1"]' in prompt
    assert "required_provisions" not in prompt
    assert "expected_decision" not in prompt
    assert "case_id" not in prompt
    assert "GOLD-" not in prompt
    assert "Art." not in prompt
    assert "ARTICLE:" not in prompt
    assert "COMPOSITE_SUPPORT" not in prompt
    assert "De que formas um processo" not in prompt
    assert "qwen" not in prompt.lower()


def test_export_accepts_explicit_prompt_v2_without_leaking_case_labels(tmp_path):
    dataset_path = _dataset(tmp_path / "dataset.json", [_case_payload()])
    output_path = tmp_path / "bundle-v2.jsonl"
    result = export_gold_bundle(
        FakeGoldRepository(),
        dataset_path=dataset_path,
        version_hash=VERSION_HASH,
        output_path=output_path,
        prompt_version=PROMPT_VERSION_V2,
    )
    record = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["prompt_name"] == PROMPT_NAME
    assert result["prompt_version"] == PROMPT_VERSION_V2
    assert record["prompt_version"] == PROMPT_VERSION_V2
    assert record["system_prompt"] == SYSTEM_PROMPT_V2
    assert "SINGLE_SUPPORT" not in record["system_prompt"]
    assert "expected_decision" not in record["user_prompt"]


def test_export_accepts_explicit_prompt_v3_without_changing_evidence_format(tmp_path):
    dataset_path = _dataset(tmp_path / "dataset.json", [_case_payload()])
    v2_output_path = tmp_path / "bundle-v2.jsonl"
    output_path = tmp_path / "bundle-v3.jsonl"
    export_gold_bundle(
        FakeGoldRepository(),
        dataset_path=dataset_path,
        version_hash=VERSION_HASH,
        output_path=v2_output_path,
        prompt_version=PROMPT_VERSION_V2,
    )
    result = export_gold_bundle(
        FakeGoldRepository(),
        dataset_path=dataset_path,
        version_hash=VERSION_HASH,
        output_path=output_path,
        prompt_version=PROMPT_VERSION_V3,
    )
    v2_record = json.loads(v2_output_path.read_text(encoding="utf-8"))
    record = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["prompt_version"] == PROMPT_VERSION_V3
    assert record["prompt_version"] == PROMPT_VERSION_V3
    assert record["system_prompt"] == SYSTEM_PROMPT_V3
    assert record["user_prompt"] == v2_record["user_prompt"]
    assert record["evidence"] == v2_record["evidence"]
    assert "EVIDENCE_ID: A" in record["user_prompt"]
    assert "SINGLE_SUPPORT" not in record["system_prompt"]
    assert "expected_decision" not in record["user_prompt"]


def test_export_rejects_unknown_prompt_version_without_writing(tmp_path):
    output_path = tmp_path / "bundle-invalid.jsonl"
    with pytest.raises(ValueError, match="Versão de prompt não suportada"):
        export_gold_bundle(
            FakeGoldRepository(),
            dataset_path=_dataset(tmp_path / "dataset.json", [_case_payload()]),
            version_hash=VERSION_HASH,
            output_path=output_path,
            prompt_version="999",
        )
    assert not output_path.exists()


def test_stability_selection_matches_frozen_hash_protocol():
    dataset = load_gold_dataset(FROZEN_DATASET_PATH)
    selected = select_stability_cases(
        dataset.cases,
        dataset_sha256=FROZEN_DATASET_SHA256,
    )
    by_category = {
        category.value: [case.case_id for case in selected if case.category is category]
        for category in GoldCategory
    }
    assert by_category == {
        "SINGLE_SUPPORT": ["GOLD-005", "GOLD-011", "GOLD-001"],
        "COMPOSITE_SUPPORT": ["GOLD-014", "GOLD-018", "GOLD-020"],
        "INSUFFICIENT_EVIDENCE": ["GOLD-025", "GOLD-026", "GOLD-022"],
        "AMBIGUOUS": ["GOLD-032", "GOLD-030", "GOLD-029"],
    }
    assert len(selected) == 12
    assert all(len(case_ids) == 3 for case_ids in by_category.values())
    assert "GOLD-012" not in {case.case_id for case in selected}


def test_stability_selection_uses_dataset_sha_in_score():
    dataset = load_gold_dataset(FROZEN_DATASET_PATH)
    frozen = select_stability_cases(
        dataset.cases,
        dataset_sha256=FROZEN_DATASET_SHA256,
    )
    changed = select_stability_cases(
        dataset.cases,
        dataset_sha256="0" * 64,
    )
    assert [case.case_id for case in frozen] != [case.case_id for case in changed]


def test_stability_export_preserves_v2_prompts_and_ignores_results(tmp_path):
    source_records = [
        json.loads(line)
        for line in FROZEN_V2_BUNDLE_PATH.read_text(encoding="utf-8").splitlines()
    ]
    enriched_bundle = tmp_path / "enriched-v2.jsonl"
    enriched_bundle.write_text(
        "".join(
            json.dumps(record | {"automatic_pass": index % 2 == 0}) + "\n"
            for index, record in enumerate(source_records)
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "stability.jsonl"
    result = export_stability_bundle(
        dataset_path=FROZEN_DATASET_PATH,
        input_bundle_path=enriched_bundle,
        output_path=output_path,
    )
    selected_records = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    source_by_id = {record["case_id"]: record for record in source_records}
    assert result["case_count"] == 12
    assert all(
        record["system_prompt"] == source_by_id[record["case_id"]]["system_prompt"]
        and record["user_prompt"] == source_by_id[record["case_id"]]["user_prompt"]
        for record in selected_records
    )
    forbidden = {
        "category",
        "expected_decision",
        "required_provisions",
        "gold_provisions",
        "evidence",
        "automatic_pass",
    }
    assert all(not forbidden.intersection(record) for record in selected_records)


def _stability_evaluation_case(
    case: GoldEvidenceCase,
    *,
    decision: str | None = None,
    citations: list[str] | None = None,
    coverage: bool = True,
) -> dict:
    model_decision = decision or case.expected_decision.value
    if citations is None:
        citations = list(case.required_provisions) if model_decision == "ANSWER" else []
    false_abstention = (
        case.expected_decision.value == "ANSWER" and model_decision == "ABSTAIN"
    )
    missed_clarification = (
        case.expected_decision.value == "CLARIFY" and model_decision != "CLARIFY"
    )
    checks = {
        "required_citations_covered": coverage,
        "false_abstention": false_abstention,
        "missed_clarification": missed_clarification,
        "unsafe_answer_on_insufficient": (
            case.expected_decision.value == "ABSTAIN" and model_decision == "ANSWER"
        ),
    }
    return {
        "case_id": case.case_id,
        "model_decision": model_decision,
        "parsed_response": {
            "decision": model_decision,
            "answer": "Resposta sintética",
            "citations": citations,
        },
        "automatic_checks": checks,
        "automatic_pass": model_decision == case.expected_decision.value and coverage,
        "invalid_citations": [],
        "out_of_evidence_citations": [],
    }


def test_stability_summary_distinguishes_decision_coverage_and_citation_variation(
    tmp_path,
):
    dataset = load_gold_dataset(FROZEN_DATASET_PATH)
    selected = select_stability_cases(
        dataset.cases,
        dataset_sha256=FROZEN_DATASET_SHA256,
    )
    evaluations = {}
    for seed in STABILITY_SEEDS:
        cases = [_stability_evaluation_case(case) for case in selected]
        by_id = {case["case_id"]: case for case in cases}
        if seed == 43:
            unstable = next(case for case in selected if case.case_id == "GOLD-005")
            by_id["GOLD-005"] = _stability_evaluation_case(unstable, decision="ABSTAIN")
            composite = next(case for case in selected if case.case_id == "GOLD-014")
            by_id["GOLD-014"] = _stability_evaluation_case(
                composite,
                citations=[composite.required_provisions[0]],
                coverage=False,
            )
            ambiguous = next(case for case in selected if case.case_id == "GOLD-032")
            by_id["GOLD-032"] = _stability_evaluation_case(
                ambiguous,
                citations=[ambiguous.gold_provisions[-1]],
            )
        path = tmp_path / f"seed-{seed}.json"
        path.write_text(
            json.dumps(
                {
                    "metadata": {
                        "dataset_sha256": FROZEN_DATASET_SHA256,
                        "prompt_name": PROMPT_NAME,
                        "prompt_version": PROMPT_VERSION_V2,
                    },
                    "cases": list(by_id.values()),
                }
            ),
            encoding="utf-8",
        )
        evaluations[seed] = path

    result = summarize_gold_stability(
        dataset_path=FROZEN_DATASET_PATH,
        evaluations_by_seed=evaluations,
        output_path=tmp_path / "summary.json",
    )
    cases = {case["case_id"]: case for case in result["cases"]}
    metrics = result["metrics"]
    assert cases["GOLD-005"]["decision_stable"] is False
    assert cases["GOLD-011"]["decision_stable"] is True
    assert cases["GOLD-014"]["required_citation_coverage_stable"] is False
    assert cases["GOLD-018"]["required_citation_coverage_stable"] is True
    assert cases["GOLD-014"]["citation_set_varied"] is True
    assert cases["GOLD-032"]["required_citation_coverage_stable"] == ("not_applicable")
    assert cases["GOLD-032"]["citation_set_varied"] is True
    assert metrics["decision_unstable_cases"] == 1
    assert metrics["required_citation_coverage_unstable_cases"] == 1
    assert metrics["citation_set_variation_cases"] == 3
    assert metrics["automatic_pass_by_seed"] == {"42": 12, "43": 10, "44": 12}
    assert metrics["false_abstention_by_seed"] == {"42": 0, "43": 1, "44": 0}


def test_cli_exposes_provider_neutral_gold_evidence_commands():
    runner = CliRunner()
    for command in (
        "export",
        "stability-export",
        "run-ollama",
        "validate-responses",
        "stability-summarize",
        "summarize",
    ):
        result = runner.invoke(app, ["eval", "gold", command, "--help"])
        assert result.exit_code == 0
    run_help = runner.invoke(app, ["eval", "gold", "run-ollama", "--help"])
    assert "--seed" in run_help.stdout
    assert "42" in run_help.stdout
    assert "--thinking-mode" in run_help.stdout
    validate_help = runner.invoke(
        app,
        ["eval", "gold", "validate-responses", "--help"],
        terminal_width=180,
    )
    assert "--case-id" in validate_help.stdout
    assert "--prompt-version" in validate_help.stdout
    assert "--gold-evidence-sour" in validate_help.stdout
    assert "--gold-bundle" in validate_help.stdout
    assert "--gold-bundle-sha256" in validate_help.stdout


def test_ollama_default_targets_only_the_compose_service():
    assert Settings(_env_file=None).ollama_base_url == "http://ollama:11434"


@pytest.mark.parametrize(
    ("case", "response", "check", "expected"),
    [
        (
            GoldEvidenceCase.model_validate(_case_payload()),
            ResponseRecord(case_id="GOLD-001", raw_response="not-json"),
            "json_valid",
            False,
        ),
        (
            GoldEvidenceCase.model_validate(_case_payload()),
            _response("GOLD-001", "MAYBE", ["A"]),
            "decision_valid",
            False,
        ),
        (
            GoldEvidenceCase.model_validate(_case_payload()),
            _response("GOLD-001", "ANSWER", ["UNKNOWN"]),
            "no_invalid_citations",
            False,
        ),
        (
            GoldEvidenceCase.model_validate(_case_payload()),
            _response("GOLD-001", "ANSWER", ["C"]),
            "no_out_of_evidence_citations",
            False,
        ),
        (
            GoldEvidenceCase.model_validate(
                _case_payload(
                    category="COMPOSITE_SUPPORT",
                    gold_provisions=["A", "B"],
                    required_provisions=["A", "B"],
                )
            ),
            _response("GOLD-001", "ANSWER", ["A"]),
            "required_citations_covered",
            False,
        ),
        (
            GoldEvidenceCase.model_validate(_case_payload()),
            _response("GOLD-001", "ABSTAIN", []),
            "false_abstention",
            True,
        ),
        (
            GoldEvidenceCase.model_validate(
                _case_payload(
                    category="INSUFFICIENT_EVIDENCE",
                    gold_provisions=[],
                    required_provisions=[],
                    expected_decision="ABSTAIN",
                )
            ),
            _response("GOLD-001", "ANSWER", []),
            "unsafe_answer_on_insufficient",
            True,
        ),
        (
            GoldEvidenceCase.model_validate(
                _case_payload(
                    category="AMBIGUOUS",
                    gold_provisions=["A"],
                    required_provisions=[],
                    expected_decision="CLARIFY",
                )
            ),
            _response("GOLD-001", "ANSWER", ["A"]),
            "missed_clarification",
            True,
        ),
    ],
)
def test_automatic_structural_checks(case, response, check, expected):
    result = evaluate_structured_response(case, response, frozenset({"A", "B", "C"}))
    assert result["automatic_checks"][check] is expected


def test_validation_creates_empty_human_review_and_summary_requires_completion(
    tmp_path,
):
    cases = [
        _case_payload(),
        _case_payload(
            case_id="GOLD-002",
            category="COMPOSITE_SUPPORT",
            gold_provisions=["A", "B"],
            required_provisions=["A", "B"],
        ),
        _case_payload(
            case_id="GOLD-003",
            category="INSUFFICIENT_EVIDENCE",
            gold_provisions=[],
            required_provisions=[],
            expected_decision="ABSTAIN",
        ),
        _case_payload(
            case_id="GOLD-004",
            category="AMBIGUOUS",
            gold_provisions=["A", "B"],
            required_provisions=[],
            expected_decision="CLARIFY",
        ),
    ]
    dataset_path = _dataset(tmp_path / "dataset.json", cases)
    responses_path = tmp_path / "responses.jsonl"
    responses = (
        _response("GOLD-001", "ANSWER", ["A"]),
        _response("GOLD-002", "ANSWER", ["A", "B"]),
        _response("GOLD-003", "ABSTAIN", []),
        _response("GOLD-004", "CLARIFY", ["A"]),
    )
    responses_path.write_text(
        "".join(record.model_dump_json() + "\n" for record in responses),
        encoding="utf-8",
    )
    automatic_path = tmp_path / "automatic.json"
    result, review_path = validate_gold_responses(
        FakeGoldRepository(),
        dataset_path=dataset_path,
        version_hash=VERSION_HASH,
        responses_path=responses_path,
        output_path=automatic_path,
    )
    assert all(item["automatic_pass"] for item in result["cases"])
    assert review_path == human_review_path_for(automatic_path)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert all(item["legal_correctness"] is None for item in review["cases"])
    with pytest.raises(ValueError, match="Human review pendente"):
        summarize_gold_review(
            automatic_evaluation_path=automatic_path,
            human_review_path=review_path,
            output_path=tmp_path / "summary.json",
        )

    for item in review["cases"]:
        if item["expected_decision"] == "ABSTAIN":
            item["legal_correctness"] = "NOT_APPLICABLE"
            item["completeness"] = "NOT_APPLICABLE"
        elif item["expected_decision"] == "CLARIFY":
            item["legal_correctness"] = "PASS"
            item["completeness"] = "NOT_APPLICABLE"
        else:
            item["legal_correctness"] = "PASS"
            item["completeness"] = "PASS"
        item["groundedness"] = "PASS"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    summary = summarize_gold_review(
        automatic_evaluation_path=automatic_path,
        human_review_path=review_path,
        output_path=tmp_path / "summary.json",
    )
    assert summary["metrics"] == {
        "total_cases": 4,
        "pass_rate": 1.0,
        "decision_accuracy": 1.0,
        "answer_case_pass_rate": 1.0,
        "composite_case_pass_rate": 1.0,
        "insufficient_evidence_abstention_rate": 1.0,
        "ambiguity_clarification_rate": 1.0,
        "false_abstention_rate": 0.0,
        "unsafe_answer_rate": 0.0,
        "invalid_citation_rate": 0.0,
        "out_of_evidence_citation_rate": 0.0,
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda review: review["metadata"].update({"prompt_version": "tampered"}),
            "Metadata",
        ),
        (
            lambda review: review["cases"][0].update({"raw_response": "alterada"}),
            "raw_response",
        ),
        (
            lambda review: review["cases"].append(dict(review["cases"][0])),
            "case_id duplicado",
        ),
        (lambda review: review["cases"][0].pop("comments"), "COMMENTS inválido"),
    ],
)
def test_summary_rejects_mutated_human_review_contract(tmp_path, mutation, message):
    dataset_path = _dataset(tmp_path / "dataset.json", [_case_payload()])
    responses_path = tmp_path / "responses.jsonl"
    responses_path.write_text(
        _response("GOLD-001", "ANSWER", ["A"]).model_dump_json() + "\n",
        encoding="utf-8",
    )
    automatic_path = tmp_path / "automatic.json"
    _, review_path = validate_gold_responses(
        FakeGoldRepository(),
        dataset_path=dataset_path,
        version_hash=VERSION_HASH,
        responses_path=responses_path,
        output_path=automatic_path,
    )
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["cases"][0].update(
        {
            "legal_correctness": "PASS",
            "groundedness": "PASS",
            "completeness": "PASS",
        }
    )
    mutation(review)
    review_path.write_text(json.dumps(review), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        summarize_gold_review(
            automatic_evaluation_path=automatic_path,
            human_review_path=review_path,
            output_path=tmp_path / "summary.json",
        )


def test_validation_can_apply_frozen_evaluator_to_explicit_subset(tmp_path):
    dataset_path = _dataset(
        tmp_path / "dataset.json",
        [
            _case_payload(),
            _case_payload(
                case_id="GOLD-002", gold_provisions=["B"], required_provisions=["B"]
            ),
        ],
    )
    responses_path = tmp_path / "responses.jsonl"
    responses_path.write_text(
        _response("GOLD-002", "ANSWER", ["B"]).model_dump_json() + "\n",
        encoding="utf-8",
    )
    result, review_path = validate_gold_responses(
        FakeGoldRepository(),
        dataset_path=dataset_path,
        version_hash=VERSION_HASH,
        responses_path=responses_path,
        output_path=tmp_path / "automatic.json",
        case_ids=frozenset({"GOLD-002"}),
        prompt_version=PROMPT_VERSION_V2,
    )
    assert result["metadata"]["prompt_version"] == PROMPT_VERSION_V2
    assert [case["case_id"] for case in result["cases"]] == ["GOLD-002"]
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert [case["case_id"] for case in review["cases"]] == ["GOLD-002"]
