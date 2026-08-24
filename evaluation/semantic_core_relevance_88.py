"""Experimento offline de relevância semântica Query -> Core Assertion.

Não integra o pipeline de consulta. Consome somente os artefatos congelados
das fases 86 e 87, calcula embeddings efêmeros e, opcionalmente, consulta um
judge local para comparar capacidades de relevância.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from consultor_juridico.config import settings
from consultor_juridico.retrieval.embeddings import OllamaEmbeddingProvider
from evaluation.relevance_core_86 import (
    AnswerRole,
    RelevanceStatus,
    evaluate_claim_relevance,
)

LLM_RELEVANCE_PROMPT = """Você classifica somente relevância material entre uma
pergunta e uma assertion normativa verificada. Não avalie se a assertion é
verdadeira, completa ou juridicamente correta. Não use conhecimento externo.

RELEVANT: a assertion responde diretamente à proposição principal perguntada.
IRRELEVANT: pode ser verdadeira ou temática, mas não responde materialmente à
pergunta.
UNRESOLVED: não há base segura para decidir.

Não considere suficiente uma associação ampla de tema, políticas públicas ou
consequências indiretas. Quando a query pede agente, prazo, condição, objeto ou
relação normativa específicos, a assertion deve tratar desse mesmo elemento.
Uma assertion que apenas menciona o tema, descreve um efeito auxiliar ou trata
de outra relação é IRRELEVANT. Uma assertion que responde diretamente, mas pode
estar juridicamente errada, continua RELEVANT: correção e suporte são avaliados
por outros validadores.

Responda somente no JSON solicitado."""

LLM_RELEVANCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": [item.value for item in RelevanceStatus]},
        "reason": {"type": "string", "maxLength": 500},
    },
    "required": ["status", "reason"],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class RelevanceFixture:
    name: str
    query: str
    assertion: str
    expected: RelevanceStatus


@dataclass(frozen=True, slots=True)
class Decision:
    status: RelevanceStatus
    reason: str
    latency_ms: float | None = None
    score: float | None = None
    raw_response: Any | None = None


class RelevanceJudge(Protocol):
    def evaluate(self, query: str, assertion: str) -> Decision: ...


class LexicalRelevanceJudge:
    """Adaptador sem alteração para a policy conservadora da fase 86."""

    def evaluate(self, query: str, assertion: str) -> Decision:
        started = time.perf_counter()
        result = evaluate_claim_relevance(query, assertion, (assertion,))
        status = result.status
        if result.role is not AnswerRole.CENTRAL and status is RelevanceStatus.RELEVANT:
            status = RelevanceStatus.IRRELEVANT
        return Decision(
            status=status,
            reason=result.reason,
            latency_ms=(time.perf_counter() - started) * 1000,
        )


@dataclass(frozen=True, slots=True)
class EmbeddingThresholds:
    irrelevant_at_or_below: float
    relevant_at_or_above: float
    separable: bool
    method: str


class EmbeddingRelevanceJudge:
    """Sinal semântico experimental com zona de incerteza fail-closed."""

    def __init__(
        self, provider: OllamaEmbeddingProvider, thresholds: EmbeddingThresholds
    ) -> None:
        self.provider = provider
        self.thresholds = thresholds

    def score(self, query: str, assertion: str) -> tuple[float, float]:
        started = time.perf_counter()
        query_vector, assertion_vector = self.provider.embed((query, assertion))
        return _cosine_similarity(query_vector, assertion_vector), (
            time.perf_counter() - started
        ) * 1000

    def evaluate(self, query: str, assertion: str) -> Decision:
        score, latency_ms = self.score(query, assertion)
        if not self.thresholds.separable:
            return Decision(
                RelevanceStatus.UNRESOLVED,
                (
                    "Os controles não produziram separação segura para congelar "
                    "thresholds."
                ),
                latency_ms,
                score,
            )
        if score >= self.thresholds.relevant_at_or_above:
            return Decision(
                RelevanceStatus.RELEVANT,
                "Similaridade acima do threshold relevante congelado.",
                latency_ms,
                score,
            )
        if score <= self.thresholds.irrelevant_at_or_below:
            return Decision(
                RelevanceStatus.IRRELEVANT,
                "Similaridade abaixo do threshold irrelevante congelado.",
                latency_ms,
                score,
            )
        return Decision(
            RelevanceStatus.UNRESOLVED,
            "Similaridade na zona de incerteza fail-closed.",
            latency_ms,
            score,
        )


class LLMRelevanceJudge:
    """Judge local exclusivo do experimento; não é o Semantic Validator."""

    def __init__(self, *, base_url: str, model: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def evaluate(self, query: str, assertion: str) -> Decision:
        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "format": LLM_RELEVANCE_SCHEMA,
                    "messages": [
                        {"role": "system", "content": LLM_RELEVANCE_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"QUERY:\n{query}\n\n"
                                f"CORE ASSERTION NORMATIVA VERIFICADA:\n{assertion}\n\n"
                                "A assertion responde materialmente à proposição "
                                "principal da query?"
                            ),
                        },
                    ],
                    "options": {"temperature": 0, "num_predict": 180},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            raw_response = response.json()
            payload = json.loads(raw_response["message"]["content"])
            status = RelevanceStatus(payload["status"])
            reason = payload["reason"]
            if not isinstance(reason, str):
                raise ValueError("reason inválido")
            return Decision(
                status,
                reason,
                (time.perf_counter() - started) * 1000,
                raw_response=raw_response,
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            return Decision(
                RelevanceStatus.UNRESOLVED,
                f"Falha do judge local fail-closed: {exc}",
                (time.perf_counter() - started) * 1000,
            )


def controls() -> tuple[RelevanceFixture, ...]:
    """Controles abstratos, sem case_id, artigo ou regra de produção."""
    return (
        RelevanceFixture(
            "TRUE_BUT_IRRELEVANT",
            "licença parental",
            "A administração deve publicar seus gastos trimestralmente.",
            RelevanceStatus.IRRELEVANT,
        ),
        RelevanceFixture(
            "SUPPORTED_BUT_OFF_TARGET",
            "requisitos de idade para candidatura",
            "O órgão eleitoral divulgará o calendário das eleições.",
            RelevanceStatus.IRRELEVANT,
        ),
        RelevanceFixture(
            "WRONG_LEGAL_ACTOR",
            "o presidente autoriza a medida",
            "O tribunal autoriza a medida.",
            RelevanceStatus.IRRELEVANT,
        ),
        RelevanceFixture(
            "RELATED_PROVISION_WRONG_ANSWER",
            "qual é o prazo de 30 dias para recurso",
            "O recurso é apresentado perante a autoridade competente.",
            RelevanceStatus.IRRELEVANT,
        ),
        RelevanceFixture(
            "AUXILIARY_FACT_WITHOUT_CORE_ANSWER",
            "a medida é obrigatória ou facultativa",
            "A medida será registrada em relatório anual.",
            RelevanceStatus.IRRELEVANT,
        ),
        # Relevância não substitui suporte nem completude: estes dois pares
        # respondem à query, embora devam ser rejeitados por validadores posteriores.
        RelevanceFixture(
            "PARTIAL_TRUE_ANSWER_TO_BINARY_QUERY",
            "a medida é sempre permitida",
            "A medida é permitida em situação excepcional.",
            RelevanceStatus.RELEVANT,
        ),
        RelevanceFixture(
            "THEMATICALLY_SIMILAR_BUT_WRONG_RELATION",
            "quem deve prestar contas",
            "A prestação de contas deve ser publicada.",
            RelevanceStatus.IRRELEVANT,
        ),
        RelevanceFixture(
            "CORRECT_TOPIC_WRONG_NORMATIVE_ROLE",
            "a inscrição é obrigatória",
            "A inscrição é facultativa.",
            RelevanceStatus.RELEVANT,
        ),
        RelevanceFixture(
            "SEMANTICALLY_CLOSE_BUT_IRRELEVANT",
            "proteção à moradia",
            "O Estado promoverá programas de transporte urbano.",
            RelevanceStatus.IRRELEVANT,
        ),
        RelevanceFixture(
            "VALID_PARAPHRASE",
            "a inscrição é obrigatória",
            "É obrigatório efetuar a inscrição.",
            RelevanceStatus.RELEVANT,
        ),
        RelevanceFixture(
            "MORPHOLOGICAL_VARIATION",
            "direitos trabalhistas",
            "Os trabalhadores têm direito às garantias laborais previstas.",
            RelevanceStatus.RELEVANT,
        ),
        RelevanceFixture(
            "VALID_ALTERNATIVE_WORDING",
            "quem pode apresentar recurso",
            "A parte interessada está autorizada a interpor o recurso.",
            RelevanceStatus.RELEVANT,
        ),
    )


def derive_embedding_thresholds(
    scores: dict[str, float], fixtures: tuple[RelevanceFixture, ...]
) -> EmbeddingThresholds:
    positives = [
        scores[item.name]
        for item in fixtures
        if item.expected is RelevanceStatus.RELEVANT
    ]
    negatives = [
        scores[item.name]
        for item in fixtures
        if item.expected is RelevanceStatus.IRRELEVANT
    ]
    if not positives or not negatives:
        raise ValueError("Controles insuficientes para derivar thresholds.")
    minimum_positive, maximum_negative = min(positives), max(negatives)
    return EmbeddingThresholds(
        irrelevant_at_or_below=maximum_negative,
        relevant_at_or_above=minimum_positive,
        separable=maximum_negative < minimum_positive,
        method="min_positive_vs_max_negative_controls_v1",
    )


def load_frozen_cases(
    relevance_path: Path, vcsa_path: Path
) -> tuple[tuple[RelevanceFixture, ...], tuple[RelevanceFixture, ...]]:
    relevance_rows = json.loads(relevance_path.read_text(encoding="utf-8"))["rows"]
    historical: list[RelevanceFixture] = []
    for row in relevance_rows:
        if not row.get("previously_correct"):
            continue
        central = next(
            (
                item["claim"]["text"]
                for item in row["decisions"]
                if item["decision"]["status"] == RelevanceStatus.RELEVANT
                and item["decision"]["role"] == AnswerRole.CENTRAL
            ),
            None,
        )
        if central:
            historical.append(
                RelevanceFixture(
                    row["case_id"], row["question"], central, RelevanceStatus.RELEVANT
                )
            )

    vcsa_rows = {
        item["case_id"]: item
        for item in json.loads(vcsa_path.read_text(encoding="utf-8"))["rows"]
    }
    main: list[RelevanceFixture] = []
    for case_id in ("rw-pena-morte", "rw-prisao-perpetua"):
        assertion = next(
            (
                item["reconstructed_text"]
                for item in vcsa_rows[case_id]["assertions"]
                if item["status"] == "VERIFIED"
            ),
            None,
        )
        if assertion:
            main.append(
                RelevanceFixture(
                    case_id,
                    vcsa_rows[case_id]["query"],
                    assertion,
                    RelevanceStatus.RELEVANT,
                )
            )
    return tuple(historical), tuple(main)


def run_experiment(
    *,
    relevance_path: Path,
    vcsa_path: Path,
    run_llm: bool = True,
) -> dict[str, Any]:
    """Executa uma única rodada congelada: controles, thresholds, casos reais."""
    fixture_controls = controls()
    historical, main = load_frozen_cases(relevance_path, vcsa_path)
    lexical = LexicalRelevanceJudge()
    provider = OllamaEmbeddingProvider(
        settings.ollama_base_url, settings.embedding_model, settings.embedding_timeout
    )

    # A distribuição é calculada somente sobre controles antes de qualquer caso real.
    raw_scores: dict[str, float] = {}
    control_embedding_latency: dict[str, float] = {}
    for fixture in fixture_controls:
        vectors_started = time.perf_counter()
        query_vector, assertion_vector = provider.embed(
            (fixture.query, fixture.assertion)
        )
        raw_scores[fixture.name] = _cosine_similarity(query_vector, assertion_vector)
        control_embedding_latency[fixture.name] = (
            time.perf_counter() - vectors_started
        ) * 1000
    thresholds = derive_embedding_thresholds(raw_scores, fixture_controls)
    embedding = EmbeddingRelevanceJudge(provider, thresholds)
    llm: RelevanceJudge | None = (
        LLMRelevanceJudge(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=settings.consultation_timeout,
        )
        if run_llm
        else None
    )

    all_fixtures = (*fixture_controls, *historical, *main)
    strategies: dict[str, dict[str, Any]] = {}
    for name, judge in (
        ("LEXICAL_BASELINE", lexical),
        ("EMBEDDING_RELEVANCE", embedding),
        ("LLM_RELEVANCE_JUDGE", llm),
    ):
        if judge is None:
            strategies[name] = {"status": "NOT_RUN", "rows": [], "metrics": {}}
            continue
        rows = []
        for fixture in all_fixtures:
            decision = judge.evaluate(fixture.query, fixture.assertion)
            if name == "EMBEDDING_RELEVANCE" and fixture.name in raw_scores:
                decision = Decision(
                    decision.status,
                    decision.reason,
                    control_embedding_latency[fixture.name],
                    raw_scores[fixture.name],
                )
            rows.append(
                {
                    "name": fixture.name,
                    "query": fixture.query,
                    "assertion": fixture.assertion,
                    "expected": fixture.expected.value,
                    "decision": asdict(decision),
                }
            )
        strategies[name] = {
            "status": "COMPLETED",
            "rows": rows,
            "metrics": _metrics(rows),
        }

    decisions = {
        name: _by_name(value["rows"])
        for name, value in strategies.items()
        if value["status"] == "COMPLETED"
    }
    historical_regressions = {
        name: sum(
            decisions[name][fixture.name]["decision"]["status"]
            != RelevanceStatus.RELEVANT
            for fixture in historical
        )
        for name in strategies
        if strategies[name]["status"] == "COMPLETED"
    }
    controls_pass = {
        name: _controls_pass(decisions[name], fixture_controls)
        for name in strategies
        if strategies[name]["status"] == "COMPLETED"
    }
    candidate_pass = {
        name: _candidate_pass(decisions[name], main, historical, fixture_controls)
        for name in strategies
        if strategies[name]["status"] == "COMPLETED"
    }
    return {
        "phase": "semantic_core_relevance_offline_88",
        "source_artifacts": {
            "relevance_86": str(relevance_path),
            "vcsa_87": str(vcsa_path),
        },
        "production_integration": "NOT_ENABLED",
        "retrieval_calls": 0,
        "generator_calls": 0,
        "semantic_validator_calls": 0,
        "embedding_model": settings.embedding_model,
        "llm_judge_model": settings.ollama_model if run_llm else None,
        "embedding_thresholds": asdict(thresholds),
        "embedding_control_distribution": raw_scores,
        "strategies": strategies,
        "summary": {
            "historical_cases": [item.name for item in historical],
            "main_cases": [item.name for item in main],
            "estado_sitio": "SAFE_ABSTENTION",
            "historical_correct_regressions": historical_regressions,
            "controls_pass": controls_pass,
            "candidate_pass": candidate_pass,
            "offline_correct_potential": {
                name: 7
                + int(_is_relevant(decisions[name], "rw-pena-morte"))
                + int(_is_relevant(decisions[name], "rw-prisao-perpetua"))
                for name in decisions
            },
        },
    }


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right) or not left or not right:
        raise ValueError("Vetores incompatíveis para cosine similarity.")
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        raise ValueError("Vetor nulo não possui similaridade cosseno definida.")
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    expected_rows = [
        row
        for row in rows
        if row["expected"] in {item.value for item in RelevanceStatus}
    ]
    false_relevant = sum(
        row["expected"] == "IRRELEVANT" and row["decision"]["status"] == "RELEVANT"
        for row in expected_rows
    )
    false_irrelevant = sum(
        row["expected"] == "RELEVANT" and row["decision"]["status"] == "IRRELEVANT"
        for row in expected_rows
    )
    latencies = [
        row["decision"]["latency_ms"]
        for row in rows
        if row["decision"]["latency_ms"] is not None
    ]
    return {
        "relevant_true_positives": sum(
            row["expected"] == "RELEVANT" and row["decision"]["status"] == "RELEVANT"
            for row in expected_rows
        ),
        "irrelevant_true_negatives": sum(
            row["expected"] == "IRRELEVANT"
            and row["decision"]["status"] == "IRRELEVANT"
            for row in expected_rows
        ),
        "unresolved": sum(row["decision"]["status"] == "UNRESOLVED" for row in rows),
        "false_relevant": false_relevant,
        "false_irrelevant": false_irrelevant,
        "average_latency_ms": sum(latencies) / len(latencies) if latencies else None,
    }


def _by_name(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["name"]: row for row in rows}


def _controls_pass(
    rows: dict[str, dict[str, Any]], fixtures: tuple[RelevanceFixture, ...]
) -> bool:
    return all(
        rows[item.name]["decision"]["status"] == item.expected.value
        for item in fixtures
    )


def _is_relevant(rows: dict[str, dict[str, Any]], name: str) -> bool:
    return rows[name]["decision"]["status"] == RelevanceStatus.RELEVANT.value


def _candidate_pass(
    rows: dict[str, dict[str, Any]],
    main: tuple[RelevanceFixture, ...],
    historical: tuple[RelevanceFixture, ...],
    fixtures: tuple[RelevanceFixture, ...],
) -> bool:
    return (
        all(_is_relevant(rows, item.name) for item in main)
        and all(_is_relevant(rows, item.name) for item in historical)
        and _controls_pass(rows, fixtures)
    )


def apply_llm_rows(
    result: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Anexa uma matriz de judge coletada por fixtures, sem nova inferência."""
    expected_names = {
        *result["summary"]["historical_cases"],
        *result["summary"]["main_cases"],
        *(item.name for item in controls()),
    }
    if {row["name"] for row in rows} != expected_names:
        raise ValueError(
            "A matriz do judge não contém exatamente os fixtures congelados."
        )
    result["strategies"]["LLM_RELEVANCE_JUDGE"] = {
        "status": "COMPLETED",
        "rows": rows,
        "metrics": _metrics(rows),
    }
    strategies = result["strategies"]
    decisions = {
        name: _by_name(strategy["rows"])
        for name, strategy in strategies.items()
        if strategy["status"] == "COMPLETED"
    }
    historical_names = result["summary"]["historical_cases"]
    main_names = result["summary"]["main_cases"]
    fixture_controls = controls()
    result["summary"].update(
        {
            "historical_correct_regressions": {
                name: sum(
                    not _is_relevant(decisions[name], fixture_name)
                    for fixture_name in historical_names
                )
                for name in decisions
            },
            "controls_pass": {
                name: _controls_pass(decisions[name], fixture_controls)
                for name in decisions
            },
            "candidate_pass": {
                name: (
                    all(
                        _is_relevant(decisions[name], fixture_name)
                        for fixture_name in main_names
                    )
                    and all(
                        _is_relevant(decisions[name], fixture_name)
                        for fixture_name in historical_names
                    )
                    and _controls_pass(decisions[name], fixture_controls)
                )
                for name in decisions
            },
            "offline_correct_potential": {
                name: 7
                + int(_is_relevant(decisions[name], "rw-pena-morte"))
                + int(_is_relevant(decisions[name], "rw-prisao-perpetua"))
                for name in decisions
            },
        }
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--relevance",
        type=Path,
        default=Path("evaluation/results/relevance_core_86.json"),
    )
    parser.add_argument(
        "--vcsa", type=Path, default=Path("evaluation/results/vcsa_87.json")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument(
        "--llm-fixture",
        help="Executa somente um fixture no judge local para diagnóstico isolado.",
    )
    parser.add_argument(
        "--llm-results-dir",
        type=Path,
        help="Matriz de fixtures do judge previamente coletada; não chama o judge.",
    )
    args = parser.parse_args()
    if args.llm_fixture:
        historical, main_cases = load_frozen_cases(args.relevance, args.vcsa)
        fixture = next(
            (
                item
                for item in (*controls(), *historical, *main_cases)
                if item.name == args.llm_fixture
            ),
            None,
        )
        if fixture is None:
            parser.error(f"Fixture desconhecido: {args.llm_fixture}")
        result: dict[str, Any] = {
            "name": fixture.name,
            "query": fixture.query,
            "assertion": fixture.assertion,
            "expected": fixture.expected.value,
            "decision": asdict(
                LLMRelevanceJudge(
                    base_url=settings.ollama_base_url,
                    model=settings.ollama_model,
                    timeout=settings.consultation_timeout,
                ).evaluate(fixture.query, fixture.assertion)
            ),
        }
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        return
    if args.output is None:
        parser.error("--output é obrigatório sem --llm-fixture")
    result = run_experiment(
        relevance_path=args.relevance,
        vcsa_path=args.vcsa,
        run_llm=not args.skip_llm and args.llm_results_dir is None,
    )
    if args.llm_results_dir is not None:
        rows = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(args.llm_results_dir.glob("*.json"))
        ]
        result = apply_llm_rows(result, rows)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
