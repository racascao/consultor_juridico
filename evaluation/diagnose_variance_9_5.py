"""Diagnóstico repetido da variância gerador/juiz observada na Fase 9.4.

Este programa não altera configuração, retrieval, dataset ou comportamento de
produção. As evidências são recuperadas uma vez por caso, copiadas para um
snapshot em memória e todas as repetições usam exatamente esse snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from consultor_juridico.config import settings
from consultor_juridico.consultation.attribution import deterministically_attribute
from consultor_juridico.consultation.errors import LLMResponseError
from consultor_juridico.consultation.evidence import build_evidence_set
from consultor_juridico.consultation.llm import (
    SYSTEM_PROMPT,
    build_evidence_prompt,
    parse_generated_response,
    response_schema,
)
from consultor_juridico.consultation.selection import select_evidence_candidates
from consultor_juridico.consultation.semantic import (
    SEMANTIC_SCHEMA,
    SEMANTIC_SYSTEM_PROMPT,
    build_semantic_support_prompt,
    parse_semantic_support,
)
from consultor_juridico.consultation.types import GeneratedResponse
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.evaluation.dataset import load_dataset
from consultor_juridico.retrieval import hybrid_search
from consultor_juridico.retrieval.embeddings import OllamaEmbeddingProvider

UNSTABLE_CASE_IDS = (
    "rw-pena-morte",
    "rw-prisao-perpetua",
    "rw-voto-obrigatorio",
)

ATTRIBUTION_EXPERIMENT_SYSTEM_PROMPT = """Você é um consultor da Constituição Federal
de 1988 e do ADCT.
Use EXCLUSIVAMENTE as evidências fornecidas. Não use conhecimento externo.
Produza claims atômicas, curtas e diretamente afirmadas pelo conteúdo das
evidências. Para cada claim, escolha primeiro o(s) bloco(s) cujo texto e contexto
estrutural sustentam especificamente todo o conteúdo material da claim.
Em evidence_ids, use somente os IDs desses blocos. Não cite um bloco apenas por
compartilhar palavras, número de artigo, assunto geral ou proximidade na lista.
Se uma claim exigir mais de um bloco, cite todos e somente os blocos diretamente
necessários. Não misture assuntos de blocos diferentes em uma claim.
Se nenhuma claim atômica puder ser sustentada diretamente, responda abstain=true
com claims vazias. Cada claim factual deve citar ao menos um evidence_id existente.
Responda somente no JSON solicitado, em português, sem markdown."""

ATTRIBUTION_EXPERIMENT_V2_SYSTEM_PROMPT = (
    SYSTEM_PROMPT
    + "\nAo atribuir evidence_ids, cite somente os IDs cujo próprio texto ou contexto "
    "estrutural sustenta diretamente a claim. Não cite IDs por assunto, número ou "
    "proximidade. Use o menor conjunto suficiente e não misture conteúdos de "
    "blocos que não sustentem a mesma claim."
)


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    evidence_code: str
    citation_label: str
    source_url: str | None
    text_snapshot: str
    validation_metadata: dict[str, Any]


def _ollama_chat(
    *,
    system_prompt: str,
    user_prompt: str,
    schema: dict[str, Any],
    model: str,
    num_predict: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    with httpx.Client(timeout=settings.consultation_timeout) as client:
        response = client.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json={
                "model": model,
                "stream": False,
                "format": schema,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": {"temperature": 0, "num_predict": num_predict},
            },
        )
    response.raise_for_status()
    raw_response = response.json()
    content = raw_response["message"]["content"]
    try:
        payload = json.loads(content)
        parse_error = None
    except json.JSONDecodeError as exc:
        payload = None
        parse_error = str(exc)
    return {
        "elapsed_seconds": time.perf_counter() - started,
        "raw_http_response": raw_response,
        "raw_content": content,
        "payload": payload,
        "parse_error": parse_error,
    }


def _serialize_generated(response: GeneratedResponse) -> dict[str, Any]:
    return {
        "answer": response.answer,
        "abstain": response.abstain,
        "claims": [
            {
                "claim_code": claim.claim_code,
                "text": claim.text,
                "evidence_codes": list(claim.evidence_codes),
            }
            for claim in response.claims
        ],
    }


def _generator_signature(response: GeneratedResponse) -> str:
    if response.abstain:
        return "ABSTAINED"
    claims = tuple(
        (claim.text, tuple(claim.evidence_codes)) for claim in response.claims
    )
    return json.dumps(claims, ensure_ascii=False, separators=(",", ":"))


def _semantic_signature(report: Any) -> str:
    if report.technical_error:
        return f"TECHNICAL_ERROR:{report.technical_error}"
    return "+".join(item.status.value for item in report.claims)


def _pairwise_flip_rate(signatures: list[str]) -> float:
    pairs = math.comb(len(signatures), 2)
    if not pairs:
        return 0.0
    disagreements = sum(
        left != right
        for index, left in enumerate(signatures)
        for right in signatures[index + 1 :]
    )
    return disagreements / pairs


def _distribution(signatures: list[str]) -> dict[str, int]:
    return dict(Counter(signatures).most_common())


def _snapshot_evidence(question: str) -> tuple[EvidenceSnapshot, ...]:
    provider = OllamaEmbeddingProvider(
        settings.ollama_base_url,
        settings.embedding_model,
        settings.embedding_timeout,
    )
    with SessionLocal() as session:
        retrieved = hybrid_search(
            session,
            question,
            provider,
            model_name=settings.embedding_model,
            limit=settings.consultation_top_k,
        )
        selected = select_evidence_candidates(
            retrieved,
            limit=settings.consultation_evidence_limit,
            question=question,
        )
        evidence_set = build_evidence_set(
            session,
            question,
            selected,
            retrieval_metadata={"diagnostic": "phase_9_5_variance"},
        )
        snapshots = tuple(
            EvidenceSnapshot(
                evidence_code=item.evidence_code,
                citation_label=item.citation_label,
                source_url=item.source_url,
                text_snapshot=item.text_snapshot,
                validation_metadata=dict(item.validation_metadata or {}),
            )
            for item in evidence_set.items
        )
        session.rollback()
    return snapshots


def _generate(
    question: str,
    evidence: tuple[EvidenceSnapshot, ...],
    model: str,
    *,
    attribution_experiment: str = "none",
    deterministic_attribution: bool = False,
) -> dict[str, Any]:
    if attribution_experiment == "attribution_v1":
        prompt = _build_attribution_prompt(question, evidence)
        system_prompt = ATTRIBUTION_EXPERIMENT_SYSTEM_PROMPT
    elif attribution_experiment == "attribution_v2":
        prompt = _build_attribution_prompt_v2(question, evidence)
        system_prompt = ATTRIBUTION_EXPERIMENT_V2_SYSTEM_PROMPT
    else:
        prompt = build_evidence_prompt(question, evidence)  # type: ignore[arg-type]
        system_prompt = SYSTEM_PROMPT
    raw = _ollama_chat(
        system_prompt=system_prompt,
        user_prompt=prompt,
        schema=response_schema(evidence),  # type: ignore[arg-type]
        model=model,
        num_predict=settings.consultation_max_tokens,
    )
    if raw["payload"] is None:
        raw["parsed"] = None
        raw["signature"] = f"TECHNICAL_ERROR:{raw['parse_error']}"
        return raw
    try:
        parsed = parse_generated_response(raw["payload"])
    except LLMResponseError as exc:
        raw["parsed"] = None
        raw["contract_error"] = str(exc)
        raw["signature"] = f"INVALID_CONTRACT:{exc}"
        return raw
    raw["parsed"] = _serialize_generated(parsed)
    raw["signature"] = _generator_signature(parsed)
    if deterministic_attribution:
        decision = deterministically_attribute(parsed, evidence)
        deterministic_response = decision.response
        raw["deterministic_attribution"] = {
            "changed_claims": decision.changed_claims,
            "abstained": decision.abstained,
            "reasons": list(decision.reasons),
            "parsed": _serialize_generated(deterministic_response),
            "signature": _generator_signature(deterministic_response),
            "payload": {
                "answer": deterministic_response.answer,
                "abstain": deterministic_response.abstain,
                "claims": [
                    {
                        "id": claim.claim_code,
                        "text": claim.text,
                        "evidence_ids": list(claim.evidence_codes),
                    }
                    for claim in deterministic_response.claims
                ],
            },
        }
    return raw


def _build_attribution_prompt(
    question: str, evidence: tuple[EvidenceSnapshot, ...]
) -> str:
    blocks = []
    for item in evidence:
        parent = item.validation_metadata.get("parent_context")
        context = f"\nCONTEXTO ESTRUTURAL: {parent}" if parent else ""
        blocks.append(
            f"EVIDENCE_ID: {item.evidence_code}\n"
            f"TEXTO VINCULADO EXCLUSIVAMENTE A {item.evidence_code}: "
            f"{item.text_snapshot}{context}"
        )
    return (
        f"PERGUNTA:\n{question}\n\n"
        "EVIDÊNCIAS AUTORIZADAS (cada ID deve ser citado somente quando seu "
        "próprio texto sustentar a claim):\n"
        + "\n\n".join(blocks)
        + "\n\nProduza answer, abstain e claims. Use IDs C1, C2... e os "
        "evidence_ids exatamente como apresentados."
    )


def _build_attribution_prompt_v2(
    question: str, evidence: tuple[EvidenceSnapshot, ...]
) -> str:
    blocks = []
    for item in evidence:
        parent = item.validation_metadata.get("parent_context")
        context = f" | contexto: {parent}" if parent else ""
        blocks.append(f"[{item.evidence_code}] texto: {item.text_snapshot}{context}")
    return (
        f"PERGUNTA:\n{question}\n\nEVIDÊNCIAS:\n"
        + "\n".join(blocks)
        + "\n\nProduza answer, abstain e claims. Use apenas IDs entre colchetes "
        "e atribua cada claim aos IDs que a sustentam diretamente."
    )


def _judge(
    generated: GeneratedResponse,
    evidence: tuple[EvidenceSnapshot, ...],
    model: str,
) -> dict[str, Any]:
    raw = _ollama_chat(
        system_prompt=SEMANTIC_SYSTEM_PROMPT,
        user_prompt=build_semantic_support_prompt(  # type: ignore[arg-type]
            generated, evidence
        ),
        schema=SEMANTIC_SCHEMA,
        model=model,
        num_predict=500,
    )
    if raw["payload"] is None:
        raw["parsed"] = {
            "technical_error": raw["parse_error"],
            "is_valid": False,
            "claims": [],
        }
        raw["signature"] = f"TECHNICAL_ERROR:{raw['parse_error']}"
        return raw
    report = parse_semantic_support(  # type: ignore[arg-type]
        raw["payload"], generated, evidence
    )
    raw["parsed"] = {
        "technical_error": report.technical_error,
        "is_valid": report.is_valid,
        "claims": [
            {
                "claim_code": item.claim_code,
                "status": item.status.value,
                "evidence_codes": list(item.evidence_codes),
                "reason": item.reason,
            }
            for item in report.claims
        ],
    }
    raw["signature"] = _semantic_signature(report)
    return raw


def _parsed_response(
    run: dict[str, Any], *, deterministic: bool = False
) -> GeneratedResponse:
    if run["payload"] is None or run.get("contract_error"):
        return GeneratedResponse("", (), abstain=True)
    if deterministic and run.get("deterministic_attribution"):
        return parse_generated_response(run["deterministic_attribution"]["payload"])
    return parse_generated_response(run["payload"])


def _diagnose_case(
    case: Any,
    repetitions: int,
    generator_model: str,
    judge_model: str,
    *,
    attribution_experiment: str = "none",
    deterministic_attribution: bool = False,
) -> dict[str, Any]:
    evidence = _snapshot_evidence(case.question)
    evidence_payload = [asdict(item) for item in evidence]
    evidence_hash = hashlib.sha256(
        json.dumps(evidence_payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()

    generator_runs = [
        _generate(
            case.question,
            evidence,
            generator_model,
            attribution_experiment=attribution_experiment,
            deterministic_attribution=deterministic_attribution,
        )
        for _ in range(repetitions)
    ]
    usable = [
        run
        for run in generator_runs
        if not _parsed_response(run, deterministic=deterministic_attribution).abstain
        and _parsed_response(run, deterministic=deterministic_attribution).claims
    ]
    if not usable:
        canonical = None
        isolated_judge_runs: list[dict[str, Any]] = []
    else:
        signatures = Counter(run["signature"] for run in usable)
        canonical_signature = signatures.most_common(1)[0][0]
        canonical_run = next(
            run for run in usable if run["signature"] == canonical_signature
        )
        canonical = _parsed_response(
            canonical_run, deterministic=deterministic_attribution
        )
        isolated_judge_runs = [
            _judge(canonical, evidence, judge_model) for _ in range(repetitions)
        ]

    combined_runs = []
    for generator_run in generator_runs:
        generated = _parsed_response(
            generator_run, deterministic=deterministic_attribution
        )
        if generated.abstain or not generated.claims:
            combined_runs.append(
                {
                    "generator_signature": generator_run["signature"],
                    "judge": None,
                    "outcome": "ABSTAINED_BY_GENERATOR",
                }
            )
            continue
        judge_run = _judge(generated, evidence, judge_model)
        combined_runs.append(
            {
                "generator_signature": generator_run["signature"],
                "judge": judge_run,
                "outcome": (
                    "ANSWERABLE"
                    if judge_run["parsed"]["is_valid"]
                    else "REJECTED_BY_JUDGE"
                ),
            }
        )

    generator_signatures = [run["signature"] for run in generator_runs]
    judge_signatures = [run["signature"] for run in isolated_judge_runs]
    combined_signatures = [run["outcome"] for run in combined_runs]
    return {
        "case_id": case.id,
        "question": case.question,
        "evidence_snapshot_sha256": evidence_hash,
        "evidence": evidence_payload,
        "generator_variance": {
            "runs": generator_runs,
            "distribution": _distribution(generator_signatures),
            "unique_claim_citation_signatures": len(set(generator_signatures)),
            "pairwise_flip_rate": _pairwise_flip_rate(generator_signatures),
        },
        "deterministic_attribution": {
            "enabled": deterministic_attribution,
            "runs": [run.get("deterministic_attribution") for run in generator_runs],
            "distribution": _distribution(
                [
                    run.get("deterministic_attribution", {}).get("signature", "NOT_RUN")
                    for run in generator_runs
                ]
            ),
            "changed_claims": sum(
                run.get("deterministic_attribution", {}).get("changed_claims", 0)
                for run in generator_runs
            ),
        },
        "judge_variance": {
            "canonical_response": (
                _serialize_generated(canonical) if canonical is not None else None
            ),
            "runs": isolated_judge_runs,
            "distribution": _distribution(judge_signatures),
            "pairwise_flip_rate": _pairwise_flip_rate(judge_signatures),
        },
        "combined_variance": {
            "runs": combined_runs,
            "distribution": _distribution(combined_signatures),
            "pairwise_flip_rate": _pairwise_flip_rate(combined_signatures),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument(
        "--dataset", default="evaluation/datasets/real_world_short_v1.json"
    )
    parser.add_argument(
        "--output", default="evaluation/results/variance_9_5_diagnostic.json"
    )
    parser.add_argument(
        "--experiment",
        choices=("none", "attribution_v1", "attribution_v2"),
        default="none",
    )
    parser.add_argument("--deterministic-attribution", action="store_true")
    args = parser.parse_args()
    if args.repetitions < 2:
        parser.error("--repetitions deve ser pelo menos 2")

    version, all_cases = load_dataset(args.dataset)
    by_id = {case.id: case for case in all_cases}
    cases = tuple(by_id[case_id] for case_id in UNSTABLE_CASE_IDS)
    generator_model = settings.ollama_model
    judge_model = settings.semantic_judge_model or settings.ollama_model
    started = time.perf_counter()
    results = []
    for case in cases:
        print(f"diagnosing {case.id} ({args.repetitions}x)", flush=True)
        results.append(
            _diagnose_case(
                case,
                args.repetitions,
                generator_model,
                judge_model,
                attribution_experiment=args.experiment,
                deterministic_attribution=args.deterministic_attribution,
            )
        )
    payload = {
        "diagnostic": "phase_9_5_generator_judge_variance",
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_version": version,
        "case_ids": list(UNSTABLE_CASE_IDS),
        "repetitions": args.repetitions,
        "generator_model": generator_model,
        "semantic_judge_model": judge_model,
        "embedding_model": settings.embedding_model,
        "controls": {
            "temperature": 0,
            "retrieval_runs_per_case": 1,
            "evidence_frozen_per_case": True,
            "retrieval_changed": False,
            "dataset_changed": False,
            "thresholds_changed": False,
            "experiment": args.experiment,
            "deterministic_attribution": args.deterministic_attribution,
        },
        "cases": results,
        "elapsed_seconds": time.perf_counter() - started,
    }
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {destination}", flush=True)


if __name__ == "__main__":
    main()
