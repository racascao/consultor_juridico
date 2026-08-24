"""Orquestração experimental de geração atômica vinculada à evidência."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

from consultor_juridico.consultation.completeness import (
    QueryScope,
    classify_query_scope,
)
from consultor_juridico.consultation.errors import LLMResponseError
from consultor_juridico.consultation.polarity import (
    can_route_to_semantic,
    validate_response_polarity,
)
from consultor_juridico.consultation.qualifiers import validate_material_qualifiers
from consultor_juridico.consultation.support_slots import (
    SupportSlot,
    build_support_slots,
    support_slot_manifest,
)
from consultor_juridico.consultation.types import (
    ConsultationOutcome,
    GeneratedClaim,
    GeneratedResponse,
    ScopedGeneration,
)
from consultor_juridico.consultation.validator import validate_citations
from consultor_juridico.models import EvidenceSet


class ScopedGenerator(Protocol):
    def generate_scoped(
        self,
        question: str,
        slot: SupportSlot,
        *,
        correction: tuple[str, ...] = (),
    ) -> ScopedGeneration: ...


class SemanticValidator(Protocol):
    def validate(self, response: GeneratedResponse, items: tuple[Any, ...]): ...


@dataclass(frozen=True, slots=True)
class SlotGenerationDiagnostic:
    slot_id: str
    evidence_codes: tuple[str, ...]
    generator_calls: int
    generated_claim: str | None
    approved: bool
    qualifier_status: str | None
    polarity_status: str | None
    semantic_status: str | None
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceBoundResult:
    outcome: ConsultationOutcome
    query_scope: QueryScope
    answer: str
    claims: tuple[GeneratedClaim, ...]
    slots: tuple[SupportSlot, ...]
    diagnostics: tuple[SlotGenerationDiagnostic, ...]
    errors: tuple[str, ...]
    manifest: dict[str, object]
    generator_calls: int
    semantic_calls: int
    elapsed_seconds: float


def run_evidence_bound_downstream(
    session: Session,
    question: str,
    evidence_set: EvidenceSet,
    *,
    generator: ScopedGenerator,
    semantic_validator: SemanticValidator,
    max_generation_attempts: int = 2,
) -> EvidenceBoundResult:
    """Executa somente o downstream B, sem persistir Claim ou Citation."""
    started = time.perf_counter()
    scope = classify_query_scope(question)
    slots = build_support_slots(session, tuple(evidence_set.items))
    manifest = support_slot_manifest(question, slots)
    if scope in {QueryScope.EXPLICITLY_EXHAUSTIVE, QueryScope.UNRESOLVED}:
        reason = (
            "Consulta exige completude não demonstrada pelos slots."
            if scope is QueryScope.EXPLICITLY_EXHAUSTIVE
            else "Escopo da consulta não pôde ser determinado com segurança."
        )
        return EvidenceBoundResult(
            ConsultationOutcome.ABSTAINED,
            scope,
            "",
            (),
            slots,
            (),
            (reason,),
            manifest,
            0,
            0,
            time.perf_counter() - started,
        )

    approved: list[GeneratedClaim] = []
    diagnostics: list[SlotGenerationDiagnostic] = []
    all_errors: list[str] = []
    generator_calls = 0
    semantic_calls = 0
    for slot_index, slot in enumerate(slots, start=1):
        errors: tuple[str, ...] = ()
        generated_text: str | None = None
        qualifier_status: str | None = None
        polarity_status: str | None = None
        semantic_status: str | None = None
        calls = 0
        slot_approved = False
        for _attempt in range(max_generation_attempts):
            calls += 1
            generator_calls += 1
            try:
                generated = generator.generate_scoped(question, slot, correction=errors)
            except LLMResponseError as exc:
                errors = (str(exc),)
                continue
            if generated.abstain:
                errors = ("Generator scoped declarou insuficiência para o slot.",)
                break
            generated_text = generated.claim
            claim = GeneratedClaim(
                claim_code=f"C{slot_index}",
                text=generated.claim,
                evidence_codes=slot.evidence_codes,
            )
            response = GeneratedResponse("", (claim,), abstain=False)
            citations = validate_citations(
                session, evidence_set, response, support_slots=(slot,)
            )
            if not citations.is_valid:
                errors = citations.errors
                continue
            qualifiers = validate_material_qualifiers(claim.text, slot)
            qualifier_status = "PASS" if qualifiers.is_valid else "FAIL"
            if not qualifiers.is_valid:
                errors = qualifiers.errors
                continue
            view = slot.evidence_view()
            polarity = validate_response_polarity(response, (view,))
            result = polarity.results[0]
            polarity_status = result.status.value
            if not can_route_to_semantic(result):
                errors = polarity.errors
                continue
            semantic_calls += 1
            semantic = semantic_validator.validate(response, (view,))
            semantic_status = (
                semantic.claims[0].status.value
                if semantic.claims
                else "TECHNICAL_ERROR"
            )
            if not semantic.is_valid:
                errors = semantic.errors
                continue
            approved.append(claim)
            errors = ()
            slot_approved = True
            break
        if errors:
            all_errors.extend(f"{slot.slot_id}: {error}" for error in errors)
        diagnostics.append(
            SlotGenerationDiagnostic(
                slot.slot_id,
                slot.evidence_codes,
                calls,
                generated_text,
                slot_approved,
                qualifier_status,
                polarity_status,
                semantic_status,
                errors,
            )
        )

    if approved:
        answer = (
            "Com base exclusivamente nas evidências selecionadas:\n\n"
            + "\n\n".join(
                f"{claim.text} [{', '.join(claim.evidence_codes)}]"
                for claim in approved
            )
        )
        outcome = ConsultationOutcome.ANSWERED
    else:
        answer = ""
        outcome = ConsultationOutcome.ABSTAINED
    return EvidenceBoundResult(
        outcome,
        scope,
        answer,
        tuple(approved),
        slots,
        tuple(diagnostics),
        tuple(all_errors),
        manifest,
        generator_calls,
        semantic_calls,
        time.perf_counter() - started,
    )
