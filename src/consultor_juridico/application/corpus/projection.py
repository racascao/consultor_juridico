"""Projeção textual deliberadamente simples da Fase 0."""

from consultor_juridico.domain.corpus import ParsedDocument, ProjectedSearchUnit


class ProvisionTextProjection:
    def project(self, parsed: ParsedDocument) -> tuple[ProjectedSearchUnit, ...]:
        return tuple(
            ProjectedSearchUnit(
                unit_key=provision.stable_key,
                search_text=provision.citation_text,
                provision_stable_keys=(provision.stable_key,),
            )
            for provision in parsed.provisions
            if provision.citation_text and provision.citation_text.strip()
        )
