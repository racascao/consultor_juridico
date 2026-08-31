"""Catálogo explícito do único ato piloto da Fase 0."""

from consultor_juridico.application.corpus.ports import SourceSpec
from consultor_juridico.domain.corpus import LegalActIdentity

LEI_9784_SOURCE = SourceSpec(
    authority_code="BR-PLANALTO",
    official_url="https://www.planalto.gov.br/ccivil_03/leis/l9784.htm",
    name="Planalto — Lei nº 9.784/1999",
    encoding="windows-1252",
)

LEI_9784_ACT = LegalActIdentity(
    act_code="BR-FED-LEI-9784-1999",
    jurisdiction="BR-FED",
    act_type="LEI",
    number="9784",
    year=1999,
    title="Lei nº 9.784, de 29 de janeiro de 1999",
)
