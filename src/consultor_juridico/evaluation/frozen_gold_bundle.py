"""Adapter read-only para avaliar respostas sobre Gold bundles congelados."""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from consultor_juridico.application.gold_evidence.prompt import (
    PROMPT_NAME,
    build_user_prompt,
    system_prompt_for,
)
from consultor_juridico.application.gold_evidence.types import (
    GoldEvidenceContext,
    GoldEvidenceItem,
)
from consultor_juridico.evaluation.gold_evidence import (
    GoldCategory,
    GoldEvidenceCase,
    ModelDecision,
    load_gold_dataset,
)

_POTENTIAL_STABLE_KEY = re.compile(
    r"(?:PREAMBLE|CHAPTER:[IVXLCDM]+(?:-[A-Z])?|"
    r"ARTICLE:\d+(?:-[A-Z])?(?:/(?:CAPUT|PARAGRAPH:(?:\d+|UNIQUE))"
    r"(?:/INCISO:[IVXLCDM]+)?)?)"
)


class IncompleteFrozenCitationNamespaceError(ValueError):
    """Uma chave plausível não pode ser classificada pelo namespace parcial."""


class _FrozenEvidencePayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stable_key: str = Field(min_length=1)
    provision_type: str = Field(min_length=1)
    citation_text: str
    source_locator: dict[str, Any]
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    official_url: str = Field(min_length=1)
    document_order: int = Field(ge=1)

    def to_item(self) -> GoldEvidenceItem:
        return GoldEvidenceItem(**self.model_dump())


class _FrozenGoldRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    category: GoldCategory
    expected_decision: ModelDecision
    required_provisions: tuple[str, ...]
    gold_provisions: tuple[str, ...]
    prompt_name: str
    prompt_version: str
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    version_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    system_prompt: str
    user_prompt: str
    evidence: tuple[_FrozenEvidencePayload, ...]

    @model_validator(mode="after")
    def validate_evidence_identity(self) -> _FrozenGoldRecord:
        evidence_keys = tuple(item.stable_key for item in self.evidence)
        if evidence_keys != self.gold_provisions:
            raise ValueError("evidence diverge de gold_provisions")
        return self


def _load_records(path: Path) -> tuple[_FrozenGoldRecord, ...]:
    records: list[_FrozenGoldRecord] = []
    seen: set[str] = set()
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = _FrozenGoldRecord.model_validate_json(line)
        except ValidationError as error:
            raise ValueError(
                f"Gold bundle JSONL inválido na linha {line_number}"
            ) from error
        if record.case_id in seen:
            raise ValueError(f"case_id duplicado no Gold bundle: {record.case_id}")
        seen.add(record.case_id)
        records.append(record)
    if not records:
        raise ValueError("Gold bundle vazio")
    return tuple(records)


class FrozenGoldBundleRepository:
    """Expõe evidências já materializadas sem consultar corpus ou PostgreSQL."""

    citation_namespace_complete = False

    def __init__(
        self,
        *,
        dataset_path: Path,
        bundle_path: Path,
        expected_bundle_sha256: str,
    ) -> None:
        bundle_sha256 = sha256(bundle_path.read_bytes()).hexdigest()
        if bundle_sha256 != expected_bundle_sha256.lower():
            raise ValueError(
                "SHA-256 do Gold bundle diverge: "
                f"expected={expected_bundle_sha256.lower()}; actual={bundle_sha256}"
            )
        self._dataset = load_gold_dataset(dataset_path)
        self._records = _load_records(bundle_path)
        self._validate_contract(dataset_path)
        self._items = self._index_items()

        first_item = next(iter(self._items.values()))
        first_record = self._records[0]
        self._context = GoldEvidenceContext(
            legal_act_code=self._dataset.legal_act_code,
            version_hash=first_record.version_hash,
            source_snapshot_sha256=first_item.source_snapshot_sha256,
            official_url=first_item.official_url,
        )

    def _validate_contract(self, dataset_path: Path) -> None:
        dataset_sha256 = sha256(dataset_path.read_bytes()).hexdigest()
        shared_fields = (
            "dataset_sha256",
            "version_hash",
            "prompt_name",
            "prompt_version",
        )
        for field in shared_fields:
            if len({getattr(record, field) for record in self._records}) != 1:
                raise ValueError(f"Gold bundle inconsistente para {field}")
        if self._records[0].dataset_sha256 != dataset_sha256:
            raise ValueError("SHA-256 do dataset diverge do Gold bundle")
        if self._records[0].prompt_name != PROMPT_NAME:
            raise ValueError("Nome de prompt diverge do contrato Gold Evidence")

        cases = {case.case_id: case for case in self._dataset.cases}
        records = {record.case_id: record for record in self._records}
        if set(cases) != set(records):
            raise ValueError("Gold bundle não representa integralmente o dataset")
        for case_id, case in cases.items():
            self._validate_case(case, records[case_id])

    @staticmethod
    def _validate_case(case: GoldEvidenceCase, record: _FrozenGoldRecord) -> None:
        if (
            record.category is not case.category
            or record.expected_decision is not case.expected_decision
            or record.gold_provisions != case.gold_provisions
            or record.required_provisions != case.required_provisions
        ):
            raise ValueError(f"Dataset diverge do Gold bundle em {case.case_id}")
        expected_system_prompt = system_prompt_for(record.prompt_version)
        if record.system_prompt != expected_system_prompt:
            raise ValueError(f"System prompt diverge em {case.case_id}")
        evidence = tuple(item.to_item() for item in record.evidence)
        if record.user_prompt != build_user_prompt(case.question, evidence):
            raise ValueError(f"User prompt diverge em {case.case_id}")

    def _index_items(self) -> dict[str, GoldEvidenceItem]:
        items: dict[str, GoldEvidenceItem] = {}
        provenance: set[tuple[str, str]] = set()
        for record in self._records:
            for payload in record.evidence:
                item = payload.to_item()
                existing = items.setdefault(item.stable_key, item)
                if existing != item:
                    raise ValueError(
                        f"Evidência divergente para stable_key {item.stable_key}"
                    )
                provenance.add((item.source_snapshot_sha256, item.official_url))
        if not items:
            raise ValueError("Gold bundle não contém evidências materializadas")
        if len(provenance) != 1:
            raise ValueError("Gold bundle possui proveniência inconsistente")
        return items

    def context(self, version_hash: str) -> GoldEvidenceContext:
        if version_hash != self._context.version_hash:
            raise LookupError(
                f"ActVersion não encontrada no Gold bundle: {version_hash}"
            )
        return self._context

    def materialize(
        self, version_hash: str, stable_keys: tuple[str, ...]
    ) -> tuple[GoldEvidenceItem, ...]:
        self.context(version_hash)
        return tuple(
            sorted(
                (self._items[key] for key in stable_keys if key in self._items),
                key=lambda item: item.document_order,
            )
        )

    def provision_keys(self, version_hash: str) -> frozenset[str]:
        self.context(version_hash)
        return frozenset(self._items)

    def validate_citation_namespace(self, citations: frozenset[str]) -> None:
        unknown = citations - self.provision_keys(self._context.version_hash)
        ambiguous = sorted(
            citation
            for citation in unknown
            if _POTENTIAL_STABLE_KEY.fullmatch(citation) is not None
        )
        if ambiguous:
            raise IncompleteFrozenCitationNamespaceError(
                "INCOMPLETE_FROZEN_CITATION_NAMESPACE: " + ", ".join(ambiguous)
            )
