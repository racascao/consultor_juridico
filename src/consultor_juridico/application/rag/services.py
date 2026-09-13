"""Fluxo RAG simples, auditável e fail-closed do MVP2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

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
from consultor_juridico.application.rag.types import RagResult
from consultor_juridico.application.retrieval.ports import SearchUnitRetriever
from consultor_juridico.domain.rag import (
    AnswerContract,
    CitationStatus,
    CitationValidation,
    RagDecision,
    RagIdentity,
)
from consultor_juridico.domain.retrieval import RetrievalRequest
from consultor_juridico.evaluation.ollama_gold_runner import GENERATION_CONFIG
from consultor_juridico.evaluation.selected_answerer import (
    FREEZE_ID,
    SELECTED_MODEL,
    SELECTED_MODEL_DIGEST,
)


class RagError(RuntimeError):
    """Falha rastreável e fechada do pipeline RAG."""


class InvalidAnswerContractError(RagError):
    pass


class CitationValidationError(RagError):
    def __init__(self, validation: CitationValidation) -> None:
        super().__init__(validation.status.value)
        self.validation = validation


class _StructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: RagDecision
    answer: str
    citations: tuple[str, ...]


def parse_answer_contract(raw_response: str) -> AnswerContract:
    try:
        payload: Any = json.loads(raw_response)
        parsed = _StructuredOutput.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as error:
        raise InvalidAnswerContractError("INVALID_ANSWER_CONTRACT") from error
    if not parsed.answer.strip():
        raise InvalidAnswerContractError("ANSWER_TEXT_REQUIRED")
    if parsed.decision is RagDecision.ABSTAIN and parsed.citations:
        raise InvalidAnswerContractError("ABSTAIN_CITATIONS_MUST_BE_EMPTY")
    if parsed.decision is RagDecision.ANSWER and not parsed.citations:
        raise InvalidAnswerContractError("ANSWER_CITATIONS_REQUIRED")
    if len(set(parsed.citations)) != len(parsed.citations):
        raise InvalidAnswerContractError("DUPLICATE_CITATIONS")
    return AnswerContract(parsed.decision, parsed.answer, parsed.citations)


def validate_citations(
    citations: tuple[str, ...],
    *,
    evidence_keys: frozenset[str],
    corpus_keys: frozenset[str],
) -> CitationValidation:
    cited = frozenset(citations)
    invalid = tuple(sorted(cited - corpus_keys))
    if invalid:
        return CitationValidation(CitationStatus.INVALID_CITATION, invalid)
    outside = tuple(sorted(cited - evidence_keys))
    if outside:
        return CitationValidation(
            CitationStatus.OUT_OF_EVIDENCE, out_of_evidence=outside
        )
    return CitationValidation(CitationStatus.VALID)


@dataclass(frozen=True, slots=True)
class EvidenceAssembler:
    repository: StructuralEvidenceRepository

    max_children_per_parent: int = 8
    max_evidence_items: int = 24

    def assemble(self, version_hash: str, candidates):
        ordered_keys = tuple(
            dict.fromkeys(
                key
                for candidate in candidates
                for key in candidate.provision_stable_keys
            )
        )
        materialized = self.repository.materialize(version_hash, ordered_keys)
        by_key = {item.stable_key: item for item in materialized}
        missing = tuple(key for key in ordered_keys if key not in by_key)
        if missing:
            raise RagError(f"RETRIEVED_EVIDENCE_NOT_MATERIALIZABLE: {missing}")
        children = self.repository.direct_children(
            version_hash,
            ordered_keys,
            max_children_per_parent=self.max_children_per_parent,
        )
        expanded = []
        seen = set()
        for key in ordered_keys:
            for item in (by_key[key], *children.get(key, ())):
                if item.stable_key in seen:
                    continue
                expanded.append(item)
                seen.add(item.stable_key)
                if len(expanded) == self.max_evidence_items:
                    return tuple(expanded)
        return tuple(expanded)


class RunRagQuery:
    def __init__(
        self,
        retriever: SearchUnitRetriever,
        evidence_repository: StructuralEvidenceRepository,
        answerer: FrozenAnswerer,
    ) -> None:
        self._retriever = retriever
        self._evidence_repository = evidence_repository
        self._answerer = answerer

    def execute(self, request: RetrievalRequest) -> RagResult:
        self._retriever.context(request.version_hash)
        self._evidence_repository.context(request.version_hash)
        candidates = self._retriever.search(request)
        evidence = EvidenceAssembler(self._evidence_repository).assemble(
            request.version_hash, candidates
        )
        identity = RagIdentity(
            SELECTED_MODEL,
            SELECTED_MODEL_DIGEST,
            FREEZE_ID,
            f"{PROMPT_NAME}/{PROMPT_VERSION_V2}",
            tuple(
                sorted(
                    {
                        key: value
                        for key, value in GENERATION_CONFIG.items()
                        if key != "seed"
                    }.items()
                )
            ),
        )
        if not evidence:
            output = AnswerContract(
                RagDecision.ABSTAIN,
                "As evidências locais recuperadas são insuficientes para responder.",
                (),
            )
            return RagResult(
                request.question,
                candidates,
                evidence,
                output,
                CitationValidation(CitationStatus.VALID),
                identity,
            )
        raw = self._answerer.generate(
            system_prompt=system_prompt_for(PROMPT_VERSION_V2),
            user_prompt=build_user_prompt(request.question, evidence),
        )
        output = parse_answer_contract(raw)
        corpus_keys = self._evidence_repository.provision_keys(request.version_hash)
        validation = validate_citations(
            output.citations,
            evidence_keys=frozenset(item.stable_key for item in evidence),
            corpus_keys=corpus_keys,
        )
        if not validation.valid:
            raise CitationValidationError(validation)
        return RagResult(
            request.question, candidates, evidence, output, validation, identity
        )
