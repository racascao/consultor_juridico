"""Avaliação funcional e reproduzível do retrieval do MVP2."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from consultor_juridico.application.ports import CandidateRetriever
from consultor_juridico.domain import Question


@dataclass(frozen=True, slots=True)
class RetrievalCase:
    case_id: str
    question: str
    expected_targets: tuple[str, ...]
    expected_outcome: str = "CLEAR"


@dataclass(frozen=True, slots=True)
class RetrievalFailure:
    case_id: str
    question: str
    expected_targets: tuple[str, ...]
    observed_rank: int | None
    top_candidates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalCandidateObservation:
    stable_reference: str
    unit_type: str
    final_rank: int
    lexical_rank: int | None
    vector_rank: int | None
    article_family: str | None


@dataclass(frozen=True, slots=True)
class RetrievalCaseResult:
    case_id: str
    expected_targets: tuple[str, ...]
    final_rank: int | None
    hit_at_1: bool
    hit_at_3: bool
    hit_at_10: bool
    unique_article_families: int
    duplicate_family_slots: int
    candidates: tuple[RetrievalCandidateObservation, ...]


@dataclass(frozen=True, slots=True)
class RetrievalEvaluation:
    cases: int
    hit_at_1: float
    hit_at_3: float
    hit_at_10: float
    mrr: float
    failures: tuple[RetrievalFailure, ...]
    case_results: tuple[RetrievalCaseResult, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def load_retrieval_dataset(path: Path) -> tuple[str, tuple[RetrievalCase, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = tuple(
        RetrievalCase(
            case_id=item["id"],
            question=item["question"],
            expected_targets=tuple(item["expected_targets"]),
            expected_outcome=item.get("expected_outcome", "CLEAR"),
        )
        for item in payload["cases"]
    )
    return payload["version"], cases


def evaluate_retrieval(
    retriever: CandidateRetriever,
    cases: tuple[RetrievalCase, ...],
    *,
    limit: int = 10,
) -> RetrievalEvaluation:
    reciprocal_ranks: list[float] = []
    ranks: list[int | None] = []
    failures: list[RetrievalFailure] = []
    case_results: list[RetrievalCaseResult] = []
    for case in cases:
        candidates = retriever.retrieve(Question(case.question), limit)
        observed = tuple(candidate.stable_reference for candidate in candidates)
        target_ranks = tuple(
            index
            for index, reference in enumerate(observed, start=1)
            if reference in case.expected_targets
        )
        if case.expected_outcome == "AMBIGUOUS":
            success = set(case.expected_targets).issubset(observed)
            rank = max(target_ranks) if success else None
        else:
            success = bool(target_ranks)
            rank = min(target_ranks) if success else None
        ranks.append(rank)
        reciprocal_ranks.append(0.0 if rank is None else 1.0 / rank)
        observations = tuple(
            RetrievalCandidateObservation(
                stable_reference=candidate.stable_reference,
                unit_type=candidate.search_unit_type,
                final_rank=index,
                lexical_rank=candidate.lexical_rank,
                vector_rank=candidate.vector_rank,
                article_family=candidate.article_reference,
            )
            for index, candidate in enumerate(candidates, start=1)
        )
        families = tuple(
            observation.article_family
            for observation in observations
            if observation.article_family is not None
        )
        case_results.append(
            RetrievalCaseResult(
                case_id=case.case_id,
                expected_targets=case.expected_targets,
                final_rank=rank,
                hit_at_1=rank is not None and rank <= 1,
                hit_at_3=rank is not None and rank <= 3,
                hit_at_10=rank is not None and rank <= 10,
                unique_article_families=len(set(families)),
                duplicate_family_slots=len(families) - len(set(families)),
                candidates=observations,
            )
        )
        if not success:
            failures.append(
                RetrievalFailure(
                    case.case_id,
                    case.question,
                    case.expected_targets,
                    rank,
                    observed,
                )
            )
    total = len(cases)
    if total == 0:
        raise ValueError("Dataset de retrieval não pode ser vazio.")
    return RetrievalEvaluation(
        cases=total,
        hit_at_1=sum(rank is not None and rank <= 1 for rank in ranks) / total,
        hit_at_3=sum(rank is not None and rank <= 3 for rank in ranks) / total,
        hit_at_10=sum(rank is not None and rank <= 10 for rank in ranks) / total,
        mrr=sum(reciprocal_ranks) / total,
        failures=tuple(failures),
        case_results=tuple(case_results),
    )


def write_evaluation(path: Path, version: str, result: RetrievalEvaluation) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"dataset_version": version, **result.as_dict()}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
