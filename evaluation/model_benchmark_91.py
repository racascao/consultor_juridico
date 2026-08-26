"""Harness resumível dos estágios de relevância da Fase 91.

Experimental: não é importado pelo pipeline de produção.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from consultor_juridico.consultation.llm import RESPONSE_SCHEMA
from evaluation.semantic_core_relevance_88 import controls, load_frozen_cases

MODELS = (
    "qwen3.5:4b",
    "ministral-3:3b",
    "qwen3.5:9b",
    "ministral-3:8b",
    "granite4.1:3b",
    "granite4.1:8b",
    "deepseek-r1:8b",
)
DEFAULT_RESULT = Path("evaluation/results/model_benchmark_91_1/relevance.json")
GENERATOR_RESULT = Path("evaluation/results/model_benchmark_91_1/generator.json")
GENERATOR_RETRY_RESULT = Path(
    "evaluation/results/model_benchmark_91_1/generator_retry_512.json"
)
GENERATOR_MERGED_RESULT = Path(
    "evaluation/results/model_benchmark_91_1/generator_merged.json"
)
FROZEN_EVIDENCE = Path("evaluation/results/evidence_bound_12_frozen_evidence_sets.json")
DEFAULT_LOG = Path("evaluation/results/model_benchmark_91_1/benchmark.log")
CRITICAL_NAMES = frozenset(
    {
        "rw-prisao-perpetua",
        "rw-pena-morte",
        "TRUE_BUT_IRRELEVANT",
        "WRONG_LEGAL_ACTOR",
        "RELATED_PROVISION_WRONG_ANSWER",
        "SUPPORTED_BUT_OFF_TARGET",
        "THEMATICALLY_SIMILAR_BUT_WRONG_RELATION",
        "CORRECT_TOPIC_WRONG_NORMATIVE_ROLE",
        "AUXILIARY_FACT_WITHOUT_CORE_ANSWER",
    }
)
RERUNNABLE_STATUSES = frozenset(
    {
        "MODEL_FAIL",
        "OLLAMA_HTTP_ERROR",
        "OLLAMA_TIMEOUT",
        "EMPTY_FINAL_CONTENT",
        "THINKING_WITHOUT_FINAL_CONTENT",
        "JSON_PARSE_ERROR",
        "INVALID_STRUCTURED_OUTPUT",
    }
)
RELEVANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["RELEVANT", "IRRELEVANT", "UNRESOLVED"]},
        "reason": {"type": "string"},
    },
    "required": ["status", "reason"],
    "additionalProperties": False,
}
SEMANTIC_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["SUPPORTED", "UNSUPPORTED", "UNRESOLVED"],
        },
        "reason": {"type": "string"},
    },
    "required": ["status", "reason"],
    "additionalProperties": False,
}
SYSTEM = """Você classifica somente relevância material entre uma pergunta e uma
assertion normativa verificada. Não use conhecimento externo. RELEVANT somente
se a assertion responder diretamente à proposição principal. IRRELEVANT se for
apenas temática, auxiliar, tiver ator jurídico errado ou responder outra relação.
UNRESOLVED se não houver base segura. Não avalie verdade jurídica, citation,
provenance ou completude.
Responda exclusivamente no JSON solicitado."""
SEMANTIC_SYSTEM = """Classifique somente suporte semântico entre uma claim e a
evidência fornecida. Não receba query. SUPPORTED exige suporte integral;
UNSUPPORTED inclui
contradição, ator errado, generalização ou omissão material; UNRESOLVED é
fail-closed. Responda exclusivamente JSON."""


def pairs() -> list[dict[str, str]]:
    historical, main = load_frozen_cases(
        Path("evaluation/results/relevance_core_86.json"),
        Path("evaluation/results/vcsa_87.json"),
    )
    items = [*controls(), *historical, *main]
    return [
        {
            "name": x.name,
            "query": x.query,
            "assertion": x.assertion,
            "expected": x.expected.value,
        }
        for x in items
    ]


def semantic_pairs() -> list[dict[str, str]]:
    return [
        {
            "name": "LITERAL",
            "evidence": "A inscrição é obrigatória.",
            "claim": "A inscrição é obrigatória.",
            "expected": "SUPPORTED",
        },
        {
            "name": "VALID_PARAPHRASE",
            "evidence": "A inscrição é obrigatória.",
            "claim": "É obrigatório efetuar a inscrição.",
            "expected": "SUPPORTED",
        },
        {
            "name": "QUALIFIER_PRESERVED",
            "evidence": "A pena de morte é admitida somente em guerra declarada.",
            "claim": "A pena de morte é admitida somente em guerra declarada.",
            "expected": "SUPPORTED",
        },
        {
            "name": "WRONG_LEGAL_ACTOR",
            "evidence": "O Presidente autoriza a medida.",
            "claim": "O Tribunal autoriza a medida.",
            "expected": "UNSUPPORTED",
        },
        {
            "name": "POLARITY_INVERSION",
            "evidence": "Não haverá penas de caráter perpétuo.",
            "claim": "Penas de caráter perpétuo são permitidas.",
            "expected": "UNSUPPORTED",
        },
        {
            "name": "UNSUPPORTED_GENERALIZATION",
            "evidence": "A medida é permitida em situação excepcional.",
            "claim": "A medida é sempre permitida.",
            "expected": "UNSUPPORTED",
        },
        {
            "name": "THEMATIC_ONLY_SUPPORT",
            "evidence": "A pena será cumprida em estabelecimento distinto.",
            "claim": "A prisão perpétua é proibida.",
            "expected": "UNSUPPORTED",
        },
        {
            "name": "MATERIAL_EXCEPTION_OMITTED",
            "evidence": "A pena de morte é proibida, salvo em guerra declarada.",
            "claim": "A pena de morte é proibida.",
            "expected": "UNRESOLVED",
        },
        {
            "name": "MATERIAL_CONDITION_OMITTED",
            "evidence": "A medida depende de autorização do Congresso.",
            "claim": "A medida pode ser adotada livremente.",
            "expected": "UNSUPPORTED",
        },
        {
            "name": "PARTIAL_SUPPORT",
            "evidence": "A inscrição é obrigatória.",
            "claim": "A inscrição é obrigatória e gratuita.",
            "expected": "UNSUPPORTED",
        },
    ]


def generator_pairs() -> list[dict[str, Any]]:
    """EvidenceSets congelados; nenhum retrieval é executado nesta etapa."""
    rows = json.loads(FROZEN_EVIDENCE.read_text(encoding="utf-8"))
    result = []
    for row in rows:
        items = tuple(row.get("items", ()))
        result.append(
            {
                "name": row["case_id"],
                "query": row["query"],
                "evidence_items": items,
                "evidence_codes": tuple(item["evidence_code"] for item in items),
                "dataset_hash": hashlib.sha256(
                    json.dumps(row, ensure_ascii=False, sort_keys=True).encode()
                ).hexdigest(),
            }
        )
    return result


def generator_prompt(pair: dict[str, Any]) -> str:
    blocks = []
    for item in pair["evidence_items"]:
        context = (item.get("validation_metadata") or {}).get("parent_context")
        suffix = f"\nContexto estrutural: {context}" if context else ""
        blocks.append(
            f"[{item['evidence_code']}]\nReferência: {item.get('citation_label', '')}\n"
            f"Fonte oficial: {item.get('source_url', '')}\n"
            f"Texto: {item['text_snapshot']}{suffix}"
        )
    return f"PERGUNTA:\n{pair['query']}\n\nEVIDÊNCIAS AUTORIZADAS:\n" + "\n\n".join(
        blocks
    )


def generator_schema(pair: dict[str, Any]) -> dict[str, Any]:
    schema = json.loads(json.dumps(RESPONSE_SCHEMA))
    schema["properties"]["claims"]["items"]["properties"]["evidence_ids"]["items"][
        "enum"
    ] = list(pair["evidence_codes"])
    return schema


def audit_generator_run(run: dict[str, Any]) -> dict[str, Any]:
    """Auditoria contratual determinística de uma saída já registrada."""
    result = {
        "answer_present": False,
        "abstain": None,
        "claims_count": 0,
        "claim_evidence_ids_valid": True,
        "all_evidence_ids_allowed": True,
        "non_abstain_without_claims": False,
        "abstain_with_substantive_answer": False,
        "claim_text_present": True,
        "needs_manual_semantic_review": True,
    }
    payload = run.get("payload")
    if not isinstance(payload, dict):
        return result
    answer = payload.get("answer")
    claims = payload.get("claims")
    result["answer_present"] = isinstance(answer, str) and bool(answer.strip())
    result["abstain"] = payload.get("abstain")
    result["claims_count"] = len(claims) if isinstance(claims, list) else 0
    allowed = set(run.get("evidence_codes", ()))
    ids = [
        eid
        for claim in claims or []
        for eid in (claim.get("evidence_ids", []) if isinstance(claim, dict) else [])
    ]
    result["all_evidence_ids_allowed"] = all(eid in allowed for eid in ids)
    result["claim_evidence_ids_valid"] = all(
        isinstance(eid, str) and eid for eid in ids
    )
    result["non_abstain_without_claims"] = (
        payload.get("abstain") is False and not claims
    )
    result["abstain_with_substantive_answer"] = (
        payload.get("abstain") is True and result["answer_present"]
    )
    result["claim_text_present"] = all(
        isinstance(c, dict)
        and isinstance(c.get("text"), str)
        and bool(c["text"].strip())
        for c in claims or []
    )
    return result


def merge_generator_results(
    original: dict[str, Any], retry: dict[str, Any]
) -> dict[str, Any]:
    """Merge determinístico: mantém completions originais e usa retry válido."""
    retry_map = {(r["model"], r["pair"], r["repeat"]): r for r in retry.get("runs", [])}
    merged = []
    for run in original.get("runs", []):
        chosen = run
        if run.get("status") in RERUNNABLE_STATUSES:
            candidate = retry_map.get((run["model"], run["pair"], run["repeat"]))
            if candidate and candidate.get("status") not in RERUNNABLE_STATUSES:
                chosen = {
                    **candidate,
                    "provenance": {
                        "source_attempt": "retry",
                        "original_status": run.get("status"),
                    },
                }
        if chosen is run:
            chosen = {**run, "provenance": {"source_attempt": "original"}}
        merged.append(chosen)
    return {
        "phase": "91.1",
        "source": "generator.json + generator_retry_512.json",
        "runs": merged,
    }


def parse_ollama_response(
    raw: dict[str, Any], allowed_statuses: frozenset[str] | None = None
) -> dict[str, Any]:
    allowed_statuses = allowed_statuses or frozenset(
        {"RELEVANT", "IRRELEVANT", "UNRESOLVED"}
    )
    message = raw.get("message")
    if not isinstance(message, dict):
        return {"status": "OLLAMA_HTTP_ERROR", "error": "message ausente"}
    content = message.get("content")
    thinking = message.get("thinking")
    metadata = {
        "raw_top_level_keys": sorted(raw),
        "done": raw.get("done"),
        "done_reason": raw.get("done_reason"),
        "content_length": len(content) if isinstance(content, str) else 0,
        "thinking_present": isinstance(thinking, str) and bool(thinking),
        "thinking_length": len(thinking) if isinstance(thinking, str) else 0,
        "eval_count": raw.get("eval_count"),
    }
    if not isinstance(content, str) or not content.strip():
        status = (
            "THINKING_WITHOUT_FINAL_CONTENT"
            if metadata["thinking_present"]
            else "EMPTY_FINAL_CONTENT"
        )
        return {"status": status, "metadata": metadata}
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        return {
            "status": "JSON_PARSE_ERROR",
            "error": str(exc),
            "metadata": metadata,
        }
    valid = (
        isinstance(payload, dict)
        and payload.get("status") in allowed_statuses
        and isinstance(payload.get("reason"), str)
    )
    if not valid:
        return {"status": "INVALID_STRUCTURED_OUTPUT", "metadata": metadata}
    return {
        "status": "VALID",
        "payload": payload,
        "metadata": metadata,
    }


def parse_generator_response(raw: dict[str, Any]) -> dict[str, Any]:
    """Valida o contrato real de geração, sem corrigir IDs ou claims."""
    message = raw.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        return {"status": "OLLAMA_HTTP_ERROR", "error": "message/content ausente"}
    metadata = {
        "raw_top_level_keys": sorted(raw),
        "done": raw.get("done"),
        "done_reason": raw.get("done_reason"),
        "content_length": len(content),
        "thinking_present": bool(message.get("thinking")),
        "thinking_length": len(message.get("thinking", ""))
        if isinstance(message.get("thinking"), str)
        else 0,
        "eval_count": raw.get("eval_count"),
    }
    if not content.strip():
        return {
            "status": "THINKING_WITHOUT_FINAL_CONTENT"
            if metadata["thinking_present"]
            else "EMPTY_FINAL_CONTENT",
            "metadata": metadata,
        }
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        return {"status": "JSON_PARSE_ERROR", "error": str(exc), "metadata": metadata}
    valid = (
        isinstance(payload, dict)
        and isinstance(payload.get("answer"), str)
        and isinstance(payload.get("abstain"), bool)
        and isinstance(payload.get("claims"), list)
    )
    if not valid:
        return {"status": "INVALID_STRUCTURED_OUTPUT", "metadata": metadata}
    return {"status": "VALID", "payload": payload, "metadata": metadata}


def call(
    client: httpx.Client,
    model: str,
    pair: dict[str, str],
    *,
    think: bool = False,
    semantic: bool = False,
    generator: bool = False,
    num_predict: int = 180,
) -> dict[str, Any]:
    try:
        if generator:
            user_content = generator_prompt(pair)
        elif semantic:
            user_content = f"EVIDÊNCIA:\n{pair['evidence']}\n\nCLAIM:\n{pair['claim']}"
        else:
            user_content = (
                f"PERGUNTA:\n{pair['query']}\n\nASSERTION:\n{pair['assertion']}"
            )
        response = client.post(
            "/api/chat",
            json={
                "model": model,
                "stream": False,
                "format": generator_schema(pair)
                if generator
                else (SEMANTIC_SCHEMA if semantic else RELEVANCE_SCHEMA),
                "think": think,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Use somente as evidências autorizadas. Preserve exceções; "
                            "se insuficientes, use abstain=true e claims vazias. "
                            "Só JSON."
                            if generator
                            else (SEMANTIC_SYSTEM if semantic else SYSTEM)
                        ),
                    },
                    {"role": "user", "content": user_content},
                ],
                "options": {"temperature": 0, "num_predict": num_predict},
            },
        )
        response.raise_for_status()
        result = (
            parse_generator_response(response.json())
            if generator
            else parse_ollama_response(
                response.json(),
                frozenset({"SUPPORTED", "UNSUPPORTED", "UNRESOLVED"})
                if semantic
                else None,
            )
        )
        return result
    except httpx.TimeoutException as exc:
        return {"status": "OLLAMA_TIMEOUT", "error": str(exc)}
    except httpx.HTTPError as exc:
        return {"status": "OLLAMA_HTTP_ERROR", "error": str(exc)}
    except (
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        return {"status": "MODEL_FAIL", "error": str(exc)}


def recommended_num_threads() -> int:
    count = os.cpu_count() or 4
    return max(1, count // 2)


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"{datetime.now(UTC).isoformat()} {message}\n")


def unload_model(base_url: str, model: str) -> None:
    try:
        httpx.post(
            f"{base_url}/api/generate",
            json={"model": model, "keep_alive": 0},
            timeout=30,
        )
    except httpx.HTTPError:
        pass


def run(
    path: Path,
    repeats: int,
    stage: str,
    num_threads: int,
    log_path: Path,
    models: tuple[str, ...],
    think: bool,
    num_predict: int = 180,
    retry_from: Path | None = None,
    retry_status: str | None = None,
) -> None:
    semantic = stage in {"semantic-kill", "confirm-semantic"}
    generator = stage in {"generator-kill", "confirm-generator"}
    fixture_rows = (
        generator_pairs() if generator else (semantic_pairs() if semantic else pairs())
    )
    if stage in {"relevance-kill"}:
        fixture_rows = [item for item in fixture_rows if item["name"] in CRITICAL_NAMES]
    if stage == "confirm-relevance":
        fixture_rows = pairs()
    manifest = hashlib.sha256(
        json.dumps(fixture_rows, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    data = (
        json.loads(path.read_text(encoding="utf-8"))
        if path.exists()
        else {"phase": "91", "manifest_hash": manifest, "runs": []}
    )
    existing = {
        (x["model"], x["pair"], x["repeat"])
        for x in data["runs"]
        if x.get("status") not in RERUNNABLE_STATUSES
    }
    retry_keys = None
    if retry_from:
        source = json.loads(retry_from.read_text(encoding="utf-8"))
        retry_keys = {
            (x["model"], x["pair"], x["repeat"])
            for x in source["runs"]
            if retry_status is None or x.get("status") == retry_status
        }
    base_url = os.environ.get(
        "BENCHMARK_OLLAMA_BASE_URL", "http://127.0.0.1:11435"
    ).rstrip("/")
    append_log(log_path, f"stage={stage} num_threads={num_threads} think={think}")
    interrupted = False

    def handle_sigint(_signum: int, _frame: Any) -> None:
        nonlocal interrupted
        interrupted = True
        append_log(log_path, "SIGINT checkpoint-preserved")

    previous_handler = signal.signal(signal.SIGINT, handle_sigint)
    with httpx.Client(
        base_url=base_url, timeout=float(os.environ.get("BENCHMARK_TIMEOUT", "600"))
    ) as client:
        for model in models:
            for pair in fixture_rows:
                for repeat in range(1, repeats + 1):
                    if interrupted:
                        signal.signal(signal.SIGINT, previous_handler)
                        return
                    key = (model, pair["name"], repeat)
                    if retry_keys is not None and key not in retry_keys:
                        continue
                    if key in existing:
                        continue
                    result = call(
                        client,
                        model,
                        pair,
                        think=think,
                        semantic=semantic,
                        generator=generator,
                        num_predict=num_predict if generator else 180,
                    )
                    data["runs"].append(
                        {
                            "model": model,
                            "pair": pair["name"],
                            "repeat": repeat,
                            **pair,
                            "num_predict": num_predict if generator else 180,
                            **result,
                        }
                    )
                    atomic_write(path, data)
                    message = (
                        f"[{stage}] {model} {pair['name']} {repeat} "
                        f"{result.get('status')}"
                    )
                    append_log(log_path, message)
                    print(message, flush=True)
            unload_model(base_url, model)
    signal.signal(signal.SIGINT, previous_handler)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--merge-original", type=Path)
    parser.add_argument("--merge-retry", type=Path)
    parser.add_argument("--merge-output", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_RESULT,
    )
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--stage",
        choices=(
            "relevance-kill",
            "relevance",
            "semantic-kill",
            "generator-kill",
            "confirm-relevance",
            "confirm-semantic",
            "confirm-generator",
        ),
        default="relevance",
    )
    parser.add_argument("--resource-profile", choices=("desktop",), default="desktop")
    parser.add_argument("--num-thread", type=int, default=recommended_num_threads())
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--models", default=",".join(MODELS))
    parser.add_argument("--think", action="store_true")
    parser.add_argument("--num-predict", type=int, default=180)
    parser.add_argument("--retry-from", type=Path)
    parser.add_argument("--retry-status")
    args = parser.parse_args()
    if args.merge_original or args.merge_retry or args.merge_output:
        if not (args.merge_original and args.merge_retry and args.merge_output):
            parser.error("merge exige --merge-original, --merge-retry e --merge-output")
        merged = merge_generator_results(
            json.loads(args.merge_original.read_text(encoding="utf-8")),
            json.loads(args.merge_retry.read_text(encoding="utf-8")),
        )
        atomic_write(args.merge_output, merged)
        return
    if args.num_thread < 1:
        parser.error("--num-thread deve ser positivo")
    os.environ["OLLAMA_NUM_THREAD"] = str(args.num_thread)
    selected_models = tuple(
        item.strip() for item in args.models.split(",") if item.strip()
    )
    unknown = set(selected_models) - set(MODELS)
    if unknown:
        parser.error(f"modelos não autorizados: {sorted(unknown)}")
    run(
        args.output,
        args.repeats,
        args.stage,
        args.num_thread,
        args.log,
        selected_models,
        args.think,
        num_predict=args.num_predict,
        retry_from=args.retry_from,
        retry_status=args.retry_status,
    )


if __name__ == "__main__":
    main()
