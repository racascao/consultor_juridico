"""Screen E2E da configuração single-LLM usando o serviço real de consulta."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from consultor_juridico.config import settings
from consultor_juridico.consultation import (
    EvidenceBoundControlledGenerator,
    OllamaSemanticSupportValidator,
)
from consultor_juridico.consultation.core_evidence import CORE_EVIDENCE_POLICY_V2
from consultor_juridico.evaluation.dataset import load_dataset
from consultor_juridico.evaluation.real_world import evaluate_real_world
from consultor_juridico.retrieval.embeddings import OllamaEmbeddingProvider

GENERATION_MODE = "EBCG_V2"


@dataclass(frozen=True)
class FrozenDataset:
    """Dataset E2E permitido e sua identificação científica imutável."""

    path: Path
    sha256: str
    phase: str
    evaluation_context: str


DATASETS: dict[str, FrozenDataset] = {
    "v1": FrozenDataset(
        path=Path("evaluation/datasets/real_world_short_v1.json"),
        sha256="c6b496d20dd9b7b5952f7abecca92e64c0179ce134794f5e3b39e579025f441f",
        phase="96",
        evaluation_context="PHASE_96_HISTORICAL",
    ),
    "v2": FrozenDataset(
        path=Path("evaluation/datasets/real_world_short_v2.json"),
        sha256="a6ef0c9e0f3a95a44637c80d061c854a9848aaea5aad1443e7f9f0ee9b710a89",
        phase="MVP1_FINAL",
        evaluation_context="MVP1_FINAL_NATIVE_V2",
    ),
}


def prepare_output_path(output: Path) -> Path:
    """Recusa sobrescrever resultados E2E congelados antes de qualquer inferência."""
    if output.exists():
        raise FileExistsError(f"OUTPUT_ALREADY_EXISTS: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def resolve_dataset(version: str) -> FrozenDataset:
    """Resolve somente uma versão de dataset conhecida pelo protocolo E2E."""
    try:
        return DATASETS[version]
    except KeyError as exc:
        raise ValueError(f"dataset-version desconhecida: {version}") from exc


def verify_dataset_hash(dataset: FrozenDataset) -> str:
    """Confere o artefato antes de criar providers ou iniciar inferência."""
    digest = hashlib.sha256(dataset.path.read_bytes()).hexdigest()
    if digest != dataset.sha256:
        raise RuntimeError(f"hash do dataset divergente: {digest}")
    return digest


def main(output: Path, *, dataset_version: str) -> None:
    """Executa o E2E apenas com um dataset fechado selecionado explicitamente."""
    output = prepare_output_path(output)
    dataset = resolve_dataset(dataset_version)
    digest = verify_dataset_hash(dataset)
    _version, cases = load_dataset(dataset.path)
    provider = OllamaEmbeddingProvider(
        settings.ollama_base_url, settings.embedding_model, settings.embedding_timeout
    )
    generator = EvidenceBoundControlledGenerator()
    semantic = OllamaSemanticSupportValidator(
        settings.ollama_base_url,
        settings.semantic_judge_model or settings.ollama_model,
        settings.consultation_timeout,
    )
    result = evaluate_real_world(
        cases,
        provider,
        generator,
        semantic,
        settings.ollama_model,
        settings.embedding_model,
    )
    payload = {
        "phase": dataset.phase,
        "evaluation_context": dataset.evaluation_context,
        "dataset_version": dataset_version,
        "dataset": dataset.path.name,
        "dataset_sha256": digest,
        "configuration": {
            "generation_mode": GENERATION_MODE,
            "core_evidence_policy": CORE_EVIDENCE_POLICY_V2,
            "generator_model": None,
            "semantic_model": settings.semantic_judge_model or settings.ollama_model,
            "semantic_num_predict": 500,
            "semantic_think": False,
            "relevance_mode": "DETERMINISTIC",
            "relevance_model": None,
            "embedding_model": settings.embedding_model,
        },
        "timestamp": datetime.now(UTC).isoformat(),
        **result,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_parser() -> argparse.ArgumentParser:
    """Constrói a interface explícita do harness sem executar avaliação."""
    parser = argparse.ArgumentParser(
        description="Executa o screen E2E com dataset congelado e versão explícita."
    )
    parser.add_argument(
        "--dataset-version",
        choices=tuple(DATASETS),
        required=True,
        help="Versão congelada do dataset E2E a executar.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destino novo para o JSON de resultado; sobrescrita é recusada.",
    )
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    main(args.output, dataset_version=args.dataset_version)
