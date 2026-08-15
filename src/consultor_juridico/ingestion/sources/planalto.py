"""Conhecimento declarativo da fonte oficial do Planalto no MVP 1."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlanaltoSourceAdapter:
    """Identidade e URL autorizada para a captura da CF/88 e do ADCT."""

    name: str = "Portal do Planalto"
    base_url: str = "https://www.planalto.gov.br"
    description: str = "Fonte oficial da Presidência da República"
    constitution_url: str = (
        "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm"
    )
    adapter_version: str = "planalto-constitution-v1"


PLANALTO_SOURCE = PlanaltoSourceAdapter()
