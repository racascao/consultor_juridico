"""Validação determinística mínima da cadeia citada no MVP2."""

from consultor_juridico.domain import (
    AnswerDraft,
    CitationValidation,
    SelectedEvidence,
)


class TraceableCitationValidator:
    def validate(
        self, answer: AnswerDraft, evidence: tuple[SelectedEvidence, ...]
    ) -> CitationValidation:
        selected = {item.candidate_id: item for item in evidence}
        if not answer.citations:
            return CitationValidation(False, "Resposta não possui evidência citada.")
        for citation in answer.citations:
            item = selected.get(citation.candidate_id)
            if item is None:
                return CitationValidation(
                    False, "Evidência citada não foi selecionada."
                )
            if not item.stable_reference or not item.source_url:
                return CitationValidation(
                    False, "Proveniência da evidência está incompleta."
                )
            if not item.source_snapshot_sha or len(item.source_snapshot_sha) != 64:
                return CitationValidation(False, "Snapshot da evidência é inválido.")
            if item.citation_items and not all(
                citation_item.stable_key for citation_item in item.citation_items
            ):
                return CitationValidation(False, "Provision citável sem referência.")
        return CitationValidation(True, "Cadeia de citação válida.")
