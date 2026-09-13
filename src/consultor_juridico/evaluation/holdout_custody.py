"""Validação estrutural e silenciosa de um pacote HOLDOUT sob custódia externa."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from consultor_juridico.evaluation.gold_evidence import GoldCategory, ModelDecision

DATASET_SCHEMA_ID = "blind-holdout-dataset/1"
MAPPING_SCHEMA_ID = "blind-holdout-query-mode-mapping/1"
MANIFEST_SCHEMA_ID = "blind-holdout-manifest/1"
RUNTIME_FREEZE_ID = "integrated-runtime-mvp2/1"
RUNTIME_FREEZE_SHA256 = (
    "5f0df6b41f0d35fcba0a514777a2370385620007ff3e6122473ca6793067514d"
)
BASELINE_GIT_COMMIT = "ea888a5f70d570e0ab4d505e4b3f5d695eb78cd5"
DATASET_PRIVATE_PATH = "evaluation/holdout/private/blind_holdout_mvp2_v1.json"
MAPPING_PRIVATE_PATH = (
    "evaluation/holdout/private/blind_holdout_query_mode_mapping_v1.json"
)
SHA256_PATTERN = re.compile(r"[a-f0-9]{64}")


def _require_sha256(value: str) -> str:
    if SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError("SHA-256 deve conter 64 caracteres hexadecimais minúsculos")
    return value


class HoldoutCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    question: str
    expected_decision: ModelDecision
    category: GoldCategory
    gold_provisions: tuple[str, ...]
    required_provisions: tuple[str, ...]

    @field_validator("case_id", "question")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("campo textual obrigatório vazio")
        return value

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, value: str) -> str:
        if re.fullmatch(r"HOLDOUT-[0-9]+", value) is None:
            raise ValueError("case_id deve seguir HOLDOUT-<número>")
        return value

    @model_validator(mode="after")
    def validate_evaluator_contract(self) -> HoldoutCase:
        if not set(self.required_provisions).issubset(self.gold_provisions):
            raise ValueError(
                "required_provisions deve ser subconjunto de gold_provisions"
            )
        if self.category is GoldCategory.SINGLE_SUPPORT:
            valid = (
                len(self.gold_provisions) == 1
                and self.required_provisions == self.gold_provisions
                and self.expected_decision is ModelDecision.ANSWER
            )
        elif self.category is GoldCategory.COMPOSITE_SUPPORT:
            valid = (
                len(self.gold_provisions) >= 2
                and set(self.required_provisions) == set(self.gold_provisions)
                and self.expected_decision is ModelDecision.ANSWER
            )
        elif self.category is GoldCategory.INSUFFICIENT_EVIDENCE:
            valid = (
                not self.gold_provisions
                and not self.required_provisions
                and self.expected_decision is ModelDecision.ABSTAIN
            )
        else:
            valid = (
                bool(self.gold_provisions)
                and not self.required_provisions
                and self.expected_decision is ModelDecision.CLARIFY
            )
        if not valid:
            raise ValueError("caso diverge do contrato estrutural do evaluator")
        return self


class HoldoutDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_id: str
    dataset_id: str
    legal_act_code: str
    cases: tuple[HoldoutCase, ...]

    @model_validator(mode="after")
    def validate_contract(self) -> HoldoutDataset:
        if self.schema_id != DATASET_SCHEMA_ID:
            raise ValueError("dataset_schema_id inválido")
        if not self.dataset_id.strip() or not self.legal_act_code.strip():
            raise ValueError("identidade do dataset incompleta")
        if not self.cases:
            raise ValueError("HOLDOUT deve possuir ao menos um caso")
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("case_ids duplicados")
        return self


class HoldoutModeMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_id: str
    mapping_id: str
    dataset_sha256: str
    case_modes: dict[str, Literal["LEGAL_RULE", "CASE_APPLICATION"]]

    @field_validator("dataset_sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> HoldoutModeMapping:
        if self.schema_id != MAPPING_SCHEMA_ID:
            raise ValueError("query_mode_mapping_schema_id inválido")
        if not self.mapping_id.strip() or not self.case_modes:
            raise ValueError("mapping incompleto")
        return self


class HoldoutManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_id: str
    manifest_id: str
    created_at: datetime
    custodian: str
    dataset_path: str
    dataset_sha256: str
    query_mode_mapping_path: str
    query_mode_mapping_sha256: str
    case_count: int
    dataset_schema_id: str
    query_mode_mapping_schema_id: str
    runtime_freeze_id: str
    runtime_freeze_sha256: str
    baseline_git_commit: str
    sealed_at: datetime
    holdout_read_by_runtime: bool

    @field_validator(
        "dataset_sha256", "query_mode_mapping_sha256", "runtime_freeze_sha256"
    )
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> HoldoutManifest:
        expected = {
            "schema_id": MANIFEST_SCHEMA_ID,
            "dataset_schema_id": DATASET_SCHEMA_ID,
            "query_mode_mapping_schema_id": MAPPING_SCHEMA_ID,
            "runtime_freeze_id": RUNTIME_FREEZE_ID,
            "runtime_freeze_sha256": RUNTIME_FREEZE_SHA256,
            "baseline_git_commit": BASELINE_GIT_COMMIT,
            "dataset_path": DATASET_PRIVATE_PATH,
            "query_mode_mapping_path": MAPPING_PRIVATE_PATH,
        }
        for field, value in expected.items():
            if getattr(self, field) != value:
                raise ValueError(f"{field} diverge do contrato congelado")
        if not self.manifest_id.strip() or not self.custodian.strip():
            raise ValueError("identidade de custódia incompleta")
        if self.case_count < 1:
            raise ValueError("case_count deve ser positivo")
        if self.holdout_read_by_runtime:
            raise ValueError("pacote já marcado como lido pelo runtime")
        return self


@dataclass(frozen=True, slots=True)
class HoldoutPackageValidation:
    dataset_sha256: str
    query_mode_mapping_sha256: str
    case_count: int
    mapping_id: str


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_holdout_package(
    *, dataset_path: Path, mapping_path: Path, manifest_path: Path
) -> HoldoutPackageValidation:
    """Valida somente formato, cobertura, hashes e identidade do pacote."""
    dataset_hash = _sha(dataset_path)
    mapping_hash = _sha(mapping_path)
    dataset = HoldoutDataset.model_validate(_load(dataset_path))
    mapping = HoldoutModeMapping.model_validate(_load(mapping_path))
    manifest = HoldoutManifest.model_validate(_load(manifest_path))

    dataset_ids = {case.case_id for case in dataset.cases}
    mapping_ids = set(mapping.case_modes)
    if dataset_ids != mapping_ids:
        raise ValueError("mapping deve cobrir os case_ids do dataset em relação 1:1")
    if mapping.dataset_sha256 != dataset_hash:
        raise ValueError("mapping referencia SHA divergente do dataset")
    if manifest.dataset_sha256 != dataset_hash:
        raise ValueError("manifest referencia SHA divergente do dataset")
    if manifest.query_mode_mapping_sha256 != mapping_hash:
        raise ValueError("manifest referencia SHA divergente do mapping")
    if manifest.case_count != len(dataset.cases):
        raise ValueError("case_count do manifest diverge do dataset")
    if Path(manifest.dataset_path).name != dataset_path.name:
        raise ValueError("dataset_path do manifest diverge do arquivo validado")
    if Path(manifest.query_mode_mapping_path).name != mapping_path.name:
        raise ValueError("mapping_path do manifest diverge do arquivo validado")

    return HoldoutPackageValidation(
        dataset_hash,
        mapping_hash,
        len(dataset.cases),
        mapping.mapping_id,
    )
