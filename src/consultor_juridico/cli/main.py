"""CLI do corpus auditável e retrieval lexical do MVP2."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from consultor_juridico import __version__
from consultor_juridico.application.corpus.audit import (
    CorpusAuditor,
    list_versions,
    trace_unit,
)
from consultor_juridico.application.corpus.catalog import LEI_9784_ACT, LEI_9784_SOURCE
from consultor_juridico.application.corpus.parser import PlanaltoLeiParser
from consultor_juridico.application.corpus.projection import ProvisionTextProjection
from consultor_juridico.application.corpus.services import (
    AcquireOfficialSource,
    MaterializeFromSnapshot,
)
from consultor_juridico.application.rag.services import (
    RagError,
    RunRagQuery,
)
from consultor_juridico.application.retrieval.ports import SearchUnitRetriever
from consultor_juridico.application.retrieval.services import RetrieveSearchUnits
from consultor_juridico.config import settings
from consultor_juridico.domain.retrieval import RetrievalMode, RetrievalRequest
from consultor_juridico.evaluation.frozen_gold_bundle import (
    FrozenGoldBundleRepository,
)
from consultor_juridico.evaluation.gold_evidence import (
    export_gold_bundle,
    summarize_gold_review,
    validate_gold_responses,
)
from consultor_juridico.evaluation.gold_stability import (
    export_stability_bundle,
    stability_subset_contract,
    summarize_gold_stability,
)
from consultor_juridico.evaluation.integrated_rag import run_integrated_dev
from consultor_juridico.evaluation.ollama_gold_runner import (
    MAX_GENERATION_TIME_SECONDS,
    OllamaGoldRunError,
    OllamaModelNotAvailableError,
    ThinkingMode,
    run_ollama_gold_bundle,
)
from consultor_juridico.evaluation.retrieval_baseline import run_retrieval_baseline
from consultor_juridico.evaluation.selected_answerer import (
    DEFAULT_FREEZE_PATH,
    validate_selected_answerer_freeze,
)
from consultor_juridico.infrastructure.corpus.http import HttpxSourceAcquirer
from consultor_juridico.infrastructure.corpus.materializer import (
    SqlAlchemyCorpusMaterializer,
)
from consultor_juridico.infrastructure.corpus.models import (
    ActVersionModel,
    ProvisionModel,
    SearchUnitModel,
)
from consultor_juridico.infrastructure.corpus.repositories import (
    SqlAlchemySnapshotRepository,
)
from consultor_juridico.infrastructure.gold_evidence import (
    SqlAlchemyGoldEvidenceRepository,
)
from consultor_juridico.infrastructure.ollama.selected_answerer import (
    OllamaSelectedAnswerer,
    SelectedAnswererError,
)
from consultor_juridico.infrastructure.retrieval import (
    PostgresFullTextSearchRetriever,
    PostgresRelaxedOrCoverageFullTextSearchRetriever,
    PostgresRelaxedOrFullTextSearchRetriever,
)


class GoldEvidenceSource(StrEnum):
    DATABASE = "database"
    FROZEN_BUNDLE = "frozen-bundle"


app = typer.Typer(
    name="consultor-juridico",
    help="Fundação documental auditável do Consultor Jurídico MVP2.",
    add_completion=False,
)
db_app = typer.Typer(help="Banco de dados e migrations.")
corpus_app = typer.Typer(help="Aquisição, materialização e auditoria do corpus.")
retrieval_app = typer.Typer(help="Busca lexical isolada em versão explícita.")
rag_app = typer.Typer(help="Consulta RAG rastreável com o answerer congelado.")
eval_app = typer.Typer(help="Avaliações reproduzíveis no filesystem.")
gold_eval_app = typer.Typer(help="Capacidade de modelo com Gold Evidence explícita.")
app.add_typer(db_app, name="db")
app.add_typer(corpus_app, name="corpus")
app.add_typer(retrieval_app, name="retrieval")
app.add_typer(rag_app, name="rag")
app.add_typer(eval_app, name="eval")
eval_app.add_typer(gold_eval_app, name="gold")
console = Console()


def _session_factory():
    from consultor_juridico.db.session import SessionLocal

    return SessionLocal


def _compose_retriever(session, mode: RetrievalMode) -> SearchUnitRetriever:
    if mode is RetrievalMode.RELAXED_OR_COVERAGE:
        return PostgresRelaxedOrCoverageFullTextSearchRetriever(session)
    if mode is RetrievalMode.RELAXED_OR:
        return PostgresRelaxedOrFullTextSearchRetriever(session)
    return PostgresFullTextSearchRetriever(session)


@app.command()
def version() -> None:
    """Exibe a versão do pacote."""
    console.print(f"Consultor Jurídico {__version__}")


@db_app.command("migrate")
def db_migrate() -> None:
    """Aplica migrations pendentes."""
    from consultor_juridico.services import db_service

    db_service.run_migrations()
    console.print("[green]Migrations aplicadas.[/green]")


@db_app.command("status")
def db_status() -> None:
    """Exibe conexão, revision e tabelas."""
    from consultor_juridico.services import db_service

    status = db_service.check_db_status()
    if not status.get("connected"):
        console.print(f"[red]Banco indisponível: {status.get('error')}[/red]")
        raise typer.Exit(1)
    console.print(f"database_url={status['database_url']}")
    console.print(f"alembic={status['alembic_version'] or 'NONE'}")
    console.print(f"tables={','.join(status['tables'])}")


@corpus_app.command("adquirir")
def corpus_acquire() -> None:
    """Adquire ou reutiliza captura oficial da Lei nº 9.784/1999."""
    timeout = httpx.Timeout(
        connect=settings.ingestion_connect_timeout,
        read=settings.ingestion_read_timeout,
        write=settings.ingestion_write_timeout,
        pool=settings.ingestion_pool_timeout,
    )
    with httpx.Client(timeout=timeout) as client, _session_factory()() as session:
        use_case = AcquireOfficialSource(
            HttpxSourceAcquirer(client, user_agent=settings.planalto_user_agent),
            SqlAlchemySnapshotRepository(session),
        )
        with session.begin():
            result = use_case.execute(LEI_9784_SOURCE)
    snapshot = result.snapshot
    console.print(f"source={LEI_9784_SOURCE.name}")
    console.print(f"url={LEI_9784_SOURCE.official_url}")
    console.print(f"http_status={result.status_code}")
    console.print(f"snapshot_id={snapshot.id}")
    console.print(f"sha256={snapshot.sha256}")
    console.print(f"byte_length={snapshot.byte_length}")
    console.print(f"etag={snapshot.etag}")
    console.print(f"last_modified={snapshot.last_modified}")
    console.print(f"acquired_at={snapshot.acquired_at.isoformat()}")
    console.print(f"outcome={'CREATED' if result.created else 'REUSED'}")


def _materialize(snapshot_sha: str):
    session_factory = _session_factory()
    with session_factory() as read_session:
        use_case = MaterializeFromSnapshot(
            SqlAlchemySnapshotRepository(read_session),
            SqlAlchemyCorpusMaterializer(session_factory),
            PlanaltoLeiParser(),
            ProvisionTextProjection(),
        )
        return use_case.execute(
            snapshot_sha=snapshot_sha,
            source=LEI_9784_SOURCE,
            act=LEI_9784_ACT,
        )


def _show_materialization(result) -> None:
    console.print(f"legal_act={LEI_9784_ACT.act_code}")
    console.print(f"act_version_id={result.act_version_id}")
    console.print(f"version_hash={result.version_hash}")
    console.print("parser=planalto-lei-structural/1")
    console.print("projection=provision-text/1")
    console.print(f"provision_count={result.provision_count}")
    console.print(f"search_unit_count={result.search_unit_count}")
    console.print(f"outcome={'CREATED' if result.created else 'REUSED'}")


@corpus_app.command("materializar")
def corpus_materialize(
    snapshot_sha: Annotated[str, typer.Option("--snapshot-sha")],
) -> None:
    """Materializa explicitamente um snapshot persistido, sem HTTP."""
    _show_materialization(_materialize(snapshot_sha))


@corpus_app.command("reprojetar")
def corpus_reproject(
    snapshot_sha: Annotated[str, typer.Option("--snapshot-sha")],
) -> None:
    """Reexecuta parser/projeção correntes somente a partir do snapshot local."""
    _show_materialization(_materialize(snapshot_sha))


@corpus_app.command("versoes")
def corpus_versions() -> None:
    """Lista versões explícitas do corpus, sem conceito de versão ativa."""
    with _session_factory()() as session:
        rows = list_versions(session)
    for row in rows:
        console.print(" | ".join(f"{key}={value}" for key, value in row.items()))


@corpus_app.command("auditar")
def corpus_audit(
    version_hash: Annotated[str, typer.Option("--version-hash")],
) -> None:
    """Audita integridade, conteúdo, projeção e proveniência."""
    with _session_factory()() as session:
        report = CorpusAuditor(
            session, PlanaltoLeiParser(), ProvisionTextProjection()
        ).audit(version_hash, encoding=LEI_9784_SOURCE.encoding)
    for name, passed in report.checks.items():
        console.print(f"{name}={'PASS' if passed else 'FAIL'}")
    console.print(f"provisions={report.provision_count}")
    console.print(f"search_units={report.search_unit_count}")
    console.print(f"AUDIT={'PASS' if report.passed else 'FAIL'}")
    if not report.passed:
        raise typer.Exit(1)


@corpus_app.command("rastrear")
def corpus_trace(
    version_hash: Annotated[str, typer.Option("--version-hash")],
    unit_key: Annotated[str, typer.Option("--unit-key")],
) -> None:
    """Mostra a cadeia de uma SearchUnit até a fonte oficial."""
    with _session_factory()() as session:
        result = trace_unit(session, version_hash, unit_key)
    for key, value in result.items():
        console.print(f"{key}={value}")


@retrieval_app.command("buscar")
def retrieval_search(
    question: Annotated[str, typer.Argument(help="Pergunta jurídica")],
    version_hash: Annotated[str, typer.Option("--version-hash")],
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 10,
    mode: Annotated[RetrievalMode, typer.Option("--mode")] = RetrievalMode.STRICT,
) -> None:
    """Busca SearchUnits com PostgreSQL FTS, sem geração de resposta."""
    request = RetrievalRequest(question, version_hash, limit)
    with _session_factory()() as session:
        retriever = _compose_retriever(session, mode)
        candidates = RetrieveSearchUnits(retriever).execute(request)
    console.print(f"version_hash={version_hash}")
    console.print(f"retrieval_implementation={retriever.implementation_name}")
    table = Table("rank", "score", "unit_key", "provisions", "search_text")
    for candidate in candidates:
        excerpt = candidate.search_text.replace("\n", " ")
        if len(excerpt) > 140:
            excerpt = excerpt[:137] + "..."
        table.add_row(
            str(candidate.rank),
            f"{candidate.score:.6f}",
            candidate.unit_key,
            ", ".join(candidate.provision_stable_keys),
            excerpt,
        )
    console.print(table)


@rag_app.command("status")
def rag_status() -> None:
    """Exibe readiness do corpus RAG sem chamar Ollama."""
    freeze = validate_selected_answerer_freeze()
    try:
        with _session_factory()() as session:
            available_versions = list_versions(session)
            auditor = CorpusAuditor(
                session, PlanaltoLeiParser(), ProvisionTextProjection()
            )
            version_readiness = {
                str(version["version_hash"]): auditor.audit(
                    str(version["version_hash"]),
                    encoding=LEI_9784_SOURCE.encoding,
                ).passed
                for version in available_versions
            }
            versions = session.scalar(select(func.count()).select_from(ActVersionModel))
            provisions = session.scalar(
                select(func.count()).select_from(ProvisionModel)
            )
            search_units = session.scalar(
                select(func.count()).select_from(SearchUnitModel)
            )
    except SQLAlchemyError as error:
        console.print(f"[red]RAG_READINESS=DATABASE_UNAVAILABLE: {error}[/red]")
        raise typer.Exit(1) from error
    ready = freeze.valid and any(version_readiness.values())
    console.print(f"selected_answerer_freeze={'VALID' if freeze.valid else 'INVALID'}")
    console.print(f"act_versions={versions or 0}")
    console.print(f"provisions={provisions or 0}")
    console.print(f"search_units={search_units or 0}")
    for version in available_versions:
        version_ready = version_readiness[str(version["version_hash"])]
        console.print(
            f"version_hash={version['version_hash']} "
            f"act={version['act_code']} "
            f"snapshot={version['source_snapshot_sha256']} "
            f"parser={version['parser']} projection={version['projection']} "
            f"ready={'YES' if version_ready else 'NO'}"
        )
    console.print("chunks=NOT_APPLICABLE_SEARCH_UNITS_ARE_RETRIEVAL_UNITS")
    console.print("embeddings=NOT_IMPLEMENTED_VECTOR_NOT_JUSTIFIED")
    console.print(f"RAG_READINESS={'READY' if ready else 'NOT_READY'}")
    if not ready:
        raise typer.Exit(1)


@app.command("ask")
def rag_ask(
    question: Annotated[str, typer.Argument(help="Pergunta jurídica")],
    version_hash: Annotated[str, typer.Option("--version-hash")],
    limit: Annotated[int, typer.Option("--limit", min=1, max=10)] = 10,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    base_url: Annotated[str, typer.Option("--base-url")] = settings.ollama_base_url,
) -> None:
    """Consulta o corpus local com geração vinculada às evidências recuperadas."""
    timeout = httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0)
    try:
        with _session_factory()() as session, httpx.Client(timeout=timeout) as client:
            audit = CorpusAuditor(
                session, PlanaltoLeiParser(), ProvisionTextProjection()
            ).audit(version_hash, encoding=LEI_9784_SOURCE.encoding)
            if not audit.passed:
                raise RagError("CORPUS_NOT_READY")
            retriever = _compose_retriever(session, RetrievalMode.RELAXED_OR_COVERAGE)
            result = RunRagQuery(
                retriever,
                SqlAlchemyGoldEvidenceRepository(session),
                OllamaSelectedAnswerer(client, base_url),
            ).execute(RetrievalRequest(question, version_hash, limit))
    except (LookupError, RagError, SelectedAnswererError, SQLAlchemyError) as error:
        console.print(f"[red]RAG_FAILED: {error}[/red]")
        raise typer.Exit(1) from error

    console.print(f"[bold]Decisão:[/bold] {result.output.decision.value}")
    console.print(f"\n[bold]Resposta:[/bold]\n{result.output.answer}")
    if result.output.citations:
        console.print("\n[bold]Fontes:[/bold]")
        evidence = {item.stable_key: item for item in result.evidence}
        for citation in result.output.citations:
            item = evidence[citation]
            console.print(f"- {citation} — {item.official_url}")
    if trace:
        console.print("\n[bold]Trace:[/bold]")
        for candidate in result.retrieved:
            console.print(
                f"rank={candidate.rank} score={candidate.score:.6f} "
                f"unit={candidate.unit_key} "
                f"evidence={','.join(candidate.provision_stable_keys)}"
            )
        console.print(
            "assembled_evidence="
            + ",".join(item.stable_key for item in result.evidence)
        )
        console.print(f"citations={','.join(result.output.citations)}")
        console.print(f"citation_validation={result.citation_validation.status.value}")
        console.print(f"model={result.identity.model}")
        console.print(f"freeze={result.identity.freeze_id}")
        console.print(f"prompt={result.identity.prompt_identity}")


@eval_app.command("retrieval")
def evaluate_retrieval(
    dataset: Annotated[Path, typer.Option("--dataset")],
    version_hash: Annotated[str, typer.Option("--version-hash")],
    output: Annotated[Path, typer.Option("--output")],
    mode: Annotated[RetrievalMode, typer.Option("--mode")] = RetrievalMode.STRICT,
) -> None:
    """Executa uma avaliação lexical e grava um artefato JSON novo."""
    with _session_factory()() as session:
        retriever = _compose_retriever(session, mode)
        result = run_retrieval_baseline(
            retriever,
            dataset_path=dataset,
            version_hash=version_hash,
            output_path=output,
        )
    overall = result["overall"]
    console.print(f"dataset={result['metadata']['dataset_id']}")
    console.print(f"version_hash={version_hash}")
    console.print(f"hit_at_1={overall['hit_at_1']:.6f}")
    console.print(f"hit_at_3={overall['hit_at_3']:.6f}")
    console.print(f"hit_at_5={overall['hit_at_5']:.6f}")
    console.print(f"hit_at_10={overall['hit_at_10']:.6f}")
    console.print(f"mrr={overall['mrr']:.6f}")
    console.print(f"output={output}")


@eval_app.command("rag-dev")
def evaluate_integrated_rag_dev(
    dataset: Annotated[Path, typer.Option("--dataset")],
    version_hash: Annotated[str, typer.Option("--version-hash")],
    output_dir: Annotated[Path, typer.Option("--output-dir")],
    base_url: Annotated[str, typer.Option("--base-url")] = settings.ollama_base_url,
) -> None:
    """Executa uma campanha Integrated DEV pelo pipeline RAG real."""
    timeout = httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0)
    with _session_factory()() as session, httpx.Client(timeout=timeout) as client:
        retriever = _compose_retriever(session, RetrievalMode.RELAXED_OR_COVERAGE)
        result = run_integrated_dev(
            retriever,
            SqlAlchemyGoldEvidenceRepository(session),
            OllamaSelectedAnswerer(client, base_url),
            dataset_path=dataset,
            version_hash=version_hash,
            output_dir=output_dir,
        )
    console.print("INTEGRATED_DEV=COMPLETE_FIRST_MEASUREMENT")
    for name, path in result["paths"].items():
        console.print(f"{name}={path}")
        console.print(f"{name}_sha256={result['sha256'][name]}")
    for name, value in result["metrics"].items():
        console.print(f"{name}={value}")


@gold_eval_app.command("export")
def export_gold_evidence(
    dataset: Annotated[Path, typer.Option("--dataset")],
    version_hash: Annotated[str, typer.Option("--version-hash")],
    output: Annotated[Path, typer.Option("--output")],
    prompt_version: Annotated[str, typer.Option("--prompt-version")] = "1",
) -> None:
    """Exporta prompts Gold Evidence sem chamar retriever ou modelo."""
    with _session_factory()() as session:
        result = export_gold_bundle(
            SqlAlchemyGoldEvidenceRepository(session),
            dataset_path=dataset,
            version_hash=version_hash,
            output_path=output,
            prompt_version=prompt_version,
        )
    console.print(f"dataset={result['dataset_id']}")
    console.print(f"dataset_sha256={result['dataset_sha256']}")
    console.print(f"version_hash={version_hash}")
    console.print(f"cases={result['case_count']}")
    console.print(f"prompt={result['prompt_name']}/{result['prompt_version']}")
    console.print(f"output={output}")


@gold_eval_app.command("stability-export")
def export_gold_evidence_stability(
    dataset: Annotated[Path, typer.Option("--dataset")],
    input_bundle: Annotated[Path, typer.Option("--input")],
    output: Annotated[Path, typer.Option("--output")],
    prompt_version: Annotated[str, typer.Option("--prompt-version")] = "2",
) -> None:
    """Recorta deterministicamente o subset congelado de estabilidade."""
    result = export_stability_bundle(
        dataset_path=dataset,
        input_bundle_path=input_bundle,
        output_path=output,
        prompt_version=prompt_version,
    )
    console.print(f"dataset={result['dataset_id']}")
    console.print(f"dataset_sha256={result['dataset_sha256']}")
    console.print(f"cases={result['case_count']}")
    console.print(f"prompt={result['prompt_name']}/{result['prompt_version']}")
    console.print(f"output={output}")


@gold_eval_app.command("validate-responses")
def validate_gold_evidence_responses(
    dataset: Annotated[Path, typer.Option("--dataset")],
    version_hash: Annotated[str, typer.Option("--version-hash")],
    responses: Annotated[Path, typer.Option("--responses")],
    output: Annotated[Path, typer.Option("--output")],
    case_subset: Annotated[Path | None, typer.Option("--case-subset")] = None,
    case_id: Annotated[str | None, typer.Option("--case-id")] = None,
    prompt_version: Annotated[str | None, typer.Option("--prompt-version")] = None,
    gold_evidence_source: Annotated[
        GoldEvidenceSource, typer.Option("--gold-evidence-source")
    ] = GoldEvidenceSource.DATABASE,
    gold_bundle: Annotated[Path | None, typer.Option("--gold-bundle")] = None,
    gold_bundle_sha256: Annotated[
        str | None, typer.Option("--gold-bundle-sha256")
    ] = None,
) -> None:
    """Valida respostas estruturais e cria review humano ainda vazio."""
    if case_subset is not None and case_id is not None:
        raise typer.BadParameter("--case-subset e --case-id são mutuamente exclusivos")
    case_ids = None
    selected_prompt_version = prompt_version
    if case_subset is not None:
        case_ids, subset_prompt_version = stability_subset_contract(
            case_subset,
            dataset_path=dataset,
        )
        if (
            selected_prompt_version is not None
            and selected_prompt_version != subset_prompt_version
        ):
            raise typer.BadParameter(
                "--prompt-version diverge do prompt do --case-subset"
            )
        selected_prompt_version = subset_prompt_version
    elif case_id is not None:
        case_ids = frozenset({case_id})
    validation_kwargs = {
        "dataset_path": dataset,
        "version_hash": version_hash,
        "responses_path": responses,
        "output_path": output,
        "case_ids": case_ids,
        **(
            {"prompt_version": selected_prompt_version}
            if selected_prompt_version
            else {}
        ),
    }
    if gold_evidence_source is GoldEvidenceSource.FROZEN_BUNDLE:
        if gold_bundle is None or gold_bundle_sha256 is None:
            raise typer.BadParameter(
                "frozen-bundle exige --gold-bundle e --gold-bundle-sha256"
            )
        repository = FrozenGoldBundleRepository(
            dataset_path=dataset,
            bundle_path=gold_bundle,
            expected_bundle_sha256=gold_bundle_sha256,
        )
        result, review_path = validate_gold_responses(
            repository,
            **validation_kwargs,
        )
    else:
        if gold_bundle is not None or gold_bundle_sha256 is not None:
            raise typer.BadParameter(
                "--gold-bundle só pode ser usado com "
                "--gold-evidence-source frozen-bundle"
            )
        with _session_factory()() as session:
            result, review_path = validate_gold_responses(
                SqlAlchemyGoldEvidenceRepository(session),
                **validation_kwargs,
            )
    console.print(f"cases={result['metadata']['case_count']}")
    console.print(f"automatic_evaluation={output}")
    console.print(f"human_review={review_path}")


@gold_eval_app.command("run-ollama")
def run_gold_evidence_ollama(
    input_bundle: Annotated[Path, typer.Option("--input")],
    model: Annotated[str, typer.Option("--model")],
    output: Annotated[Path, typer.Option("--output")],
    metadata: Annotated[Path, typer.Option("--metadata")],
    base_url: Annotated[str, typer.Option("--base-url")] = settings.ollama_base_url,
    seed: Annotated[int, typer.Option("--seed")] = 42,
    thinking_mode: Annotated[
        ThinkingMode, typer.Option("--thinking-mode")
    ] = ThinkingMode.AUTO,
    ollama_format: Annotated[str | None, typer.Option("--ollama-format")] = None,
) -> None:
    """Executa manualmente um bundle no Ollama, sem avaliar ou reparar outputs."""
    timeout = httpx.Timeout(
        connect=10.0,
        read=MAX_GENERATION_TIME_SECONDS,
        write=30.0,
        pool=10.0,
    )
    try:
        with httpx.Client(timeout=timeout) as client:
            result = run_ollama_gold_bundle(
                input_path=input_bundle,
                model=model,
                base_url=base_url,
                output_path=output,
                metadata_path=metadata,
                client=client,
                seed=seed,
                thinking_mode=thinking_mode,
                ollama_format=ollama_format,
            )
    except (OllamaModelNotAvailableError, OllamaGoldRunError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(f"run_id={result['run_id']}")
    console.print(f"status={result['status']}")
    console.print(f"completed_cases={result['completed_case_count']}")
    console.print(f"responses={output}")
    console.print(f"metadata={metadata}")


@gold_eval_app.command("stability-summarize")
def summarize_gold_evidence_stability(
    dataset: Annotated[Path, typer.Option("--dataset")],
    seed42_evaluation: Annotated[Path, typer.Option("--seed42-evaluation")],
    seed43_evaluation: Annotated[Path, typer.Option("--seed43-evaluation")],
    seed44_evaluation: Annotated[Path, typer.Option("--seed44-evaluation")],
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    """Resume as três avaliações do protocolo congelado de estabilidade."""
    result = summarize_gold_stability(
        dataset_path=dataset,
        evaluations_by_seed={
            42: seed42_evaluation,
            43: seed43_evaluation,
            44: seed44_evaluation,
        },
        output_path=output,
    )
    metrics = result["metrics"]
    console.print(f"cases={metrics['total_cases']}")
    console.print(f"decision_stability={metrics['decision_stability_fraction']}")
    console.print(f"output={output}")


@gold_eval_app.command("summarize")
def summarize_gold_evidence_review(
    automatic_evaluation: Annotated[Path, typer.Option("--automatic-evaluation")],
    human_review: Annotated[Path, typer.Option("--human-review")],
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    """Resume checks e review preenchido, recusando avaliações pendentes."""
    result = summarize_gold_review(
        automatic_evaluation_path=automatic_evaluation,
        human_review_path=human_review,
        output_path=output,
    )
    console.print(f"total_cases={result['metrics']['total_cases']}")
    console.print(f"pass_rate={result['metrics']['pass_rate']:.6f}")
    console.print(f"output={output}")


@gold_eval_app.command("selected-answerer-status")
def selected_answerer_status(
    freeze: Annotated[Path, typer.Option("--freeze")] = DEFAULT_FREEZE_PATH,
) -> None:
    """Valida localmente o freeze do answerer, sem rede ou inferência."""
    report = validate_selected_answerer_freeze(freeze)
    console.print(f"FREEZE_ID: {report.freeze_id}")
    console.print(f"MODEL: {report.model}")
    console.print(
        f"MODEL_DIGEST_MATCH: {'YES' if report.checks['model_digest_match'] else 'NO'}"
    )
    prompt_matches = (
        report.checks["prompt_identity_match"] and report.checks["prompt_sha256_match"]
    )
    console.print(f"PROMPT_MATCH: {'YES' if prompt_matches else 'NO'}")
    console.print(
        "GENERATION_CONFIG_MATCH: "
        f"{'YES' if report.checks['generation_config_match'] else 'NO'}"
    )
    console.print(f"OLLAMA_FORMAT: {report.ollama_format}")
    console.print(
        "SELECTION_EVIDENCE_MATCH: "
        f"{'YES' if report.checks['artifact_hashes_match'] else 'NO'}"
    )
    console.print("HOLDOUT_READ: NO")
    console.print(f"STATUS: {'VALID' if report.valid else 'INVALID'}")
    if not report.valid:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
