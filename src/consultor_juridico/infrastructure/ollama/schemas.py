"""Contratos Pydantic dos papéis LLM, sem tolerância a campos extras."""

from typing import Annotated, Literal, Union, cast

from pydantic import BaseModel, ConfigDict, Field, RootModel, create_model


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


def consultation_payload_schema(allowed_ids: tuple[str, ...]) -> type[RootModel]:
    """Cria variantes discriminadas e request-scoped da consulta."""
    if not allowed_ids:
        raise ValueError("Consulta exige ao menos uma candidata.")
    candidate_id = Literal.__getitem__(allowed_ids)
    interpretation = create_model(
        "ConsultationInterpretationPayload",
        __base__=StrictSchema,
        label=(str, Field(min_length=1, max_length=200)),
        candidate_ids=(list[candidate_id], Field(min_length=1)),
    )
    answer = create_model(
        "AnswerConsultationPayload",
        __base__=StrictSchema,
        decision=(Literal["ANSWER"], ...),
        answer=(str, Field(min_length=1)),
        evidence_ids=(list[candidate_id], Field(min_length=1)),
    )
    abstain = create_model(
        "AbstainConsultationPayload",
        __base__=StrictSchema,
        decision=(Literal["ABSTAIN"], ...),
    )
    clarify = create_model(
        "ClarifyConsultationPayload",
        __base__=StrictSchema,
        decision=(Literal["CLARIFY"], ...),
        interpretations=(list[interpretation], Field(min_length=2)),
        question=(str, Field(min_length=1, max_length=300)),
    )
    variants = Union.__getitem__((answer, clarify, abstain))
    discriminated = Annotated[variants, Field(discriminator="decision")]
    return cast(type[RootModel], RootModel[discriminated])
