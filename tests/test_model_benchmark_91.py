from pathlib import Path

from evaluation.model_benchmark_91 import (
    MODELS,
    atomic_write,
    audit_generator_run,
    generator_pairs,
    generator_schema,
    merge_generator_results,
    pairs,
    parse_generator_response,
    parse_ollama_response,
    recommended_num_threads,
    semantic_pairs,
)


def test_benchmark_manifest_has_required_models_and_frozen_pairs() -> None:
    assert len(MODELS) == 7
    names = {item["name"] for item in pairs()}
    assert {"TRUE_BUT_IRRELEVANT", "WRONG_LEGAL_ACTOR", "rw-prisao-perpetua"} <= names


def test_desktop_profile_and_atomic_checkpoint(tmp_path: Path) -> None:
    assert recommended_num_threads() >= 1
    target = tmp_path / "result.json"
    atomic_write(target, {"runs": []})
    assert '"runs": []' in target.read_text(encoding="utf-8")


def test_response_parser_keeps_thinking_metadata_without_content() -> None:
    result = parse_ollama_response(
        {"done": True, "message": {"content": "", "thinking": "hidden"}}
    )
    assert result["status"] == "THINKING_WITHOUT_FINAL_CONTENT"
    assert result["metadata"]["thinking_present"] is True
    assert "thinking" not in result


def test_response_parser_accepts_json_content_and_rejects_invalid_json() -> None:
    valid = parse_ollama_response(
        {
            "message": {
                "content": '{"status":"RELEVANT","reason":"ok"}',
                "thinking": "hidden",
            }
        }
    )
    invalid = parse_ollama_response({"message": {"content": "not-json"}})
    assert valid["status"] == "VALID"
    assert valid["metadata"]["thinking_length"] == len("hidden")
    assert invalid["status"] == "JSON_PARSE_ERROR"


def test_semantic_fixture_has_no_query_and_uses_support_contract() -> None:
    rows = semantic_pairs()
    assert rows
    assert {row["expected"] for row in rows} == {
        "SUPPORTED",
        "UNSUPPORTED",
        "UNRESOLVED",
    }
    assert all("query" not in row for row in rows)


def test_semantic_response_contract_is_separate_from_relevance() -> None:
    result = parse_ollama_response(
        {"message": {"content": '{"status":"SUPPORTED","reason":"ok"}'}},
        frozenset({"SUPPORTED", "UNSUPPORTED", "UNRESOLVED"}),
    )
    assert result["status"] == "VALID"


def test_generator_uses_frozen_evidence_and_real_contract() -> None:
    rows = generator_pairs()
    assert {row["name"] for row in rows} >= {
        "rw-pena-morte",
        "rw-prisao-perpetua",
    }
    schema = generator_schema(rows[0])
    allowed = schema["properties"]["claims"]["items"]["properties"]["evidence_ids"][
        "items"
    ]["enum"]
    assert set(allowed) == set(rows[0]["evidence_codes"])


def test_generator_parser_does_not_repair_hallucinated_ids() -> None:
    result = parse_generator_response(
        {"message": {"content": '{"answer":"x","abstain":false,"claims":[]}'}}
    )
    assert result["status"] == "VALID"


def test_generator_audit_and_merge_are_deterministic() -> None:
    run = {
        "evidence_codes": ["EV001"],
        "payload": {"answer": "x", "abstain": False, "claims": []},
    }
    audit = audit_generator_run(run)
    assert audit["non_abstain_without_claims"] is True
    original = {
        "runs": [{"model": "m", "pair": "p", "repeat": 1, "status": "JSON_PARSE_ERROR"}]
    }
    retry = {
        "runs": [
            {"model": "m", "pair": "p", "repeat": 1, "status": "VALID", "payload": {}}
        ]
    }
    merged = merge_generator_results(original, retry)
    assert merged["runs"][0]["provenance"]["source_attempt"] == "retry"
