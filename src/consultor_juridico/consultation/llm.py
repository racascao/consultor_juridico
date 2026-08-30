"""Geração controlada e determinística de claims jurídicas."""

from typing import Protocol

from consultor_juridico.consultation.core_evidence import select_core_evidence_v2
from consultor_juridico.consultation.types import GeneratedClaim, GeneratedResponse
from consultor_juridico.models import EvidenceItem


class LegalGenerator(Protocol):
    """Contrato mínimo do gerador controlado usado pela consulta."""

    def generate(
        self,
        question: str,
        evidence_items: tuple[EvidenceItem, ...],
        *,
        correction: tuple[str, ...] = (),
    ) -> GeneratedResponse: ...


class EvidenceBoundControlledGenerator:
    """Produz uma única claim literal da Core Evidence selecionada.

    EBCG-v2 não interpreta, resume nem combina texto. A Core Evidence é
    escolhida somente entre itens já autorizados pelos diagnostics da seleção.
    O construtor é puro e não possui I/O.
    """

    generation_mode = "EBCG_V2"

    def generate(
        self,
        question: str,
        evidence_items: tuple[EvidenceItem, ...],
        *,
        correction: tuple[str, ...] = (),
    ) -> GeneratedResponse:
        del question, correction
        core = select_core_evidence_v2(evidence_items)
        if (
            core is None
            or not bool(getattr(core, "is_validated", False))
            or not isinstance(getattr(core, "text_snapshot", None), str)
            or not core.text_snapshot.strip()
        ):
            return GeneratedResponse("", (), abstain=True)
        claim = GeneratedClaim("C1", core.text_snapshot, (core.evidence_code,))
        return GeneratedResponse(core.text_snapshot, (claim,), abstain=False)
