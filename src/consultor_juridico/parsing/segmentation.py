"""Segmentação factual dos blocos em regiões documentais constitucionais."""

import re
from dataclasses import dataclass
from time import perf_counter

from consultor_juridico.parsing.blocks import DocumentBlock
from consultor_juridico.parsing.errors import (
    AmbiguousDocumentSentinelError,
    InvalidDocumentOrderError,
    MissingDocumentSentinelError,
)

CF_START = "preâmbulo"
ADCT_HEADING = "ato das disposições constitucionais transitórias"
ARTICLE_250 = re.compile(r"^art\.\s*250(?:\D|$)")
ARTICLE_138 = re.compile(r"^art\.\s*138(?:\D|$)")


@dataclass(frozen=True, slots=True)
class ConstitutionDocumentSegments:
    """Partição completa dos blocos, ainda sem semântica jurídica."""

    leading_blocks: tuple[DocumentBlock, ...]
    cf_blocks: tuple[DocumentBlock, ...]
    transition_blocks: tuple[DocumentBlock, ...]
    adct_blocks: tuple[DocumentBlock, ...]
    trailing_blocks: tuple[DocumentBlock, ...]
    segmentation_duration_ms: float


def segment_constitution_document(
    blocks: tuple[DocumentBlock, ...],
) -> ConstitutionDocumentSegments:
    """Particiona blocos por sentinelas factuais e falha diante de ambiguidade."""
    started_at = perf_counter()
    _validate_source_order(blocks)

    cf_start = _unique_exact(blocks, CF_START, "início da CF", outside_table=True)
    article_250 = _unique_pattern(
        blocks,
        ARTICLE_250,
        "Art. 250 da CF",
        after=cf_start,
    )

    all_adct_headings = tuple(
        index
        for index, block in enumerate(blocks)
        if not block.inside_table and block.normalized_text_for_matching == ADCT_HEADING
    )
    if all_adct_headings and all(index <= article_250 for index in all_adct_headings):
        raise InvalidDocumentOrderError(
            "Cabeçalho documental do ADCT ocorre antes do Art. 250 da CF."
        )
    adct_start = _unique_indices(
        tuple(index for index in all_adct_headings if index > article_250),
        "início documental do ADCT",
    )
    adct_end = _unique_pattern(
        blocks,
        ARTICLE_138,
        "Art. 138 do ADCT",
        after=adct_start,
    )

    if not (cf_start <= article_250 < adct_start <= adct_end):
        raise InvalidDocumentOrderError("Ordem impossível entre sentinelas CF/ADCT.")

    result = ConstitutionDocumentSegments(
        leading_blocks=blocks[:cf_start],
        cf_blocks=blocks[cf_start : article_250 + 1],
        transition_blocks=blocks[article_250 + 1 : adct_start],
        adct_blocks=blocks[adct_start : adct_end + 1],
        trailing_blocks=blocks[adct_end + 1 :],
        segmentation_duration_ms=(perf_counter() - started_at) * 1000,
    )
    _validate_partition(blocks, result)
    return result


def _unique_exact(
    blocks: tuple[DocumentBlock, ...],
    value: str,
    label: str,
    *,
    outside_table: bool,
) -> int:
    return _unique_indices(
        tuple(
            index
            for index, block in enumerate(blocks)
            if (not outside_table or not block.inside_table)
            and block.normalized_text_for_matching == value
        ),
        label,
    )


def _unique_pattern(
    blocks: tuple[DocumentBlock, ...],
    pattern: re.Pattern[str],
    label: str,
    *,
    after: int,
) -> int:
    return _unique_indices(
        tuple(
            index
            for index, block in enumerate(blocks)
            if index > after and pattern.match(block.normalized_text_for_matching)
        ),
        label,
    )


def _unique_indices(indices: tuple[int, ...], label: str) -> int:
    if not indices:
        raise MissingDocumentSentinelError(f"Sentinela ausente: {label}.")
    if len(indices) > 1:
        raise AmbiguousDocumentSentinelError(
            f"Sentinela ambígua: {label}; candidatas={indices}."
        )
    return indices[0]


def _validate_source_order(blocks: tuple[DocumentBlock, ...]) -> None:
    observed = tuple(block.block_index for block in blocks)
    expected = tuple(range(1, len(blocks) + 1))
    if observed != expected:
        raise InvalidDocumentOrderError(
            "block_index deve ser contínuo, crescente e começar em 1."
        )


def _validate_partition(
    source: tuple[DocumentBlock, ...],
    result: ConstitutionDocumentSegments,
) -> None:
    projected = (
        result.leading_blocks
        + result.cf_blocks
        + result.transition_blocks
        + result.adct_blocks
        + result.trailing_blocks
    )
    if projected != source:
        raise InvalidDocumentOrderError(
            "A segmentação duplicou, removeu ou reordenou blocos."
        )
    if not result.cf_blocks or not result.adct_blocks:
        raise InvalidDocumentOrderError("Segmentos CF e ADCT não podem ser vazios.")
