"""Entrypoint da CLI do Consultor Jurídico (Typer + Rich)."""

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from sqlalchemy import func, select

from consultor_juridico import __version__
from consultor_juridico.config import settings
from consultor_juridico.consultation import (
    OllamaLegalGenerator,
    OllamaSemanticSupportValidator,
    run_consultation,
)
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.evaluation import (
    aggregate_decisions,
    benchmark_semantic_judge,
    evaluate_evidence_quality,
    evaluate_retrieval,
    load_dataset,
    load_semantic_dataset,
    write_json_report,
)
from consultor_juridico.ingestion import get_ingestion_status, run_planalto_ingestion
from consultor_juridico.models import Chunk, Embedding, SourceDocument
from consultor_juridico.parsing import materialization_status, materialize_constitution
from consultor_juridico.retrieval import (
    OllamaEmbeddingProvider,
    RetrievalFilters,
    build_search_index,
    hybrid_search,
    lexical_search,
    vector_search,
)
from consultor_juridico.services import db_service

app = typer.Typer(
    name="consultor-juridico",
    help="Mecanismo CLI-first de consulta jurídica da CF/88 e ADCT.",
    add_completion=False,
)

db_app = typer.Typer(help="Gerenciamento de banco de dados e migrations.")
ingest_app = typer.Typer(help="Comandos de ingestão de documentos oficiais.")
document_app = typer.Typer(help="Visualização de documentos jurídicos.")
parse_app = typer.Typer(help="Parsing e materialização constitucional.")
index_app = typer.Typer(help="Chunking, FTS e embeddings locais.")
retrieval_app = typer.Typer(help="Diagnóstico de retrieval jurídico.")
eval_app = typer.Typer(help="Avaliação reproduzível de qualidade do MVP1.")

app.add_typer(db_app, name="db")
app.add_typer(ingest_app, name="ingest")
app.add_typer(document_app, name="document")
app.add_typer(parse_app, name="parse")
app.add_typer(index_app, name="index")
app.add_typer(retrieval_app, name="retrieval")
app.add_typer(eval_app, name="eval")

console = Console()


@app.command()
def version() -> None:
    """Exibe a versão do Consultor Jurídico."""
    console.print(
        f"[bold green]Consultor Jurídico[/bold green] versão [cyan]{__version__}[/cyan]"
    )


@db_app.command(name="migrate")
def db_migrate() -> None:
    """Executa migrations pendentes no banco de dados."""
    console.print("[yellow]Executando migrations do banco de dados...[/yellow]")
    try:
        db_service.run_migrations()
        console.print("[bold green]Migrations executadas com sucesso![/bold green]")
    except Exception as exc:
        console.print(f"[bold red]Erro ao executar migrations:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


@db_app.command(name="status")
def db_status() -> None:
    """Exibe o status atual do banco de dados e migrations."""
    status = db_service.check_db_status()
    if status.get("connected"):
        console.print("[bold green]Status do Banco de Dados: Conectado[/bold green]")
        console.print(f"URL: {status.get('database_url')}")
        console.print(
            f"Versão Alembic: [cyan]{status.get('alembic_version') or 'Nenhuma'}[/cyan]"
        )
        tables = status.get("tables", [])
        console.print(f"Tabelas ativas ({len(tables)}): {', '.join(tables)}")
    else:
        console.print("[bold red]Status do Banco de Dados: Desconectado[/bold red]")
        console.print(f"Erro: {status.get('error')}")
        raise typer.Exit(code=1)


@ingest_app.command(name="constitution")
def ingest_constitution() -> None:
    """Executa a ingestão da CF/88 e ADCT a partir da fonte oficial."""
    console.print("[yellow]Iniciando ingestão da CF/88 e ADCT...[/yellow]")
    try:
        result = run_planalto_ingestion()
    except Exception as exc:
        console.print(f"[bold red]Falha na ingestão:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"Resultado: [bold cyan]{result.outcome.value}[/bold cyan]")
    console.print(f"Documento: {result.document_id}")
    console.print(f"URL solicitada: {result.download.requested_url}")
    console.print(f"URL final: {result.download.final_url}")
    console.print(f"Status HTTP: {result.download.status_code}")
    received_bytes = (
        len(result.download.canonical_bytes)
        if result.download.canonical_bytes is not None
        else 0
    )
    console.print(f"Bytes recebidos: {received_bytes}")
    console.print(f"SHA-256: {result.sha256}")


@ingest_app.command(name="status")
def ingest_status() -> None:
    """Exibe o status das ingestões registradas."""
    try:
        documents = get_ingestion_status()
    except Exception as exc:
        console.print(f"[bold red]Falha ao consultar ingestões:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    if not documents:
        console.print("[cyan]Status das Ingestões: Nenhuma captura registrada.[/cyan]")
        return

    console.print(f"[bold green]Capturas registradas: {len(documents)}[/bold green]")
    for document in documents:
        console.print(
            f"- {document['id']} | {document['source']} | "
            f"{document['sha256']} | {document['received_bytes']} bytes | "
            f"{document['fetched_at']}"
        )
        console.print(f"  URL: {document['url_source']}")


@parse_app.command(name="constitution")
def parse_constitution_command(document_id: str | None = None) -> None:
    """Audita e materializa atomicamente CF/88 e ADCT."""
    try:
        with SessionLocal() as session:
            if document_id is None:
                document = session.scalar(
                    select(SourceDocument).order_by(SourceDocument.fetched_at.desc())
                )
                if document is None:
                    raise LookupError("Nenhum SourceDocument disponível.")
                selected_id = document.id
            else:
                from uuid import UUID

                selected_id = UUID(document_id)
            result = materialize_constitution(session, selected_id)
    except Exception as exc:
        console.print(f"[bold red]Falha no parsing:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"Resultado: [bold cyan]{result.outcome.value}[/bold cyan]")
    console.print(f"ParsingRun: {result.parsing_run_id}")
    console.print(f"LegalVersions: {len(result.legal_version_ids)}")
    console.print(f"LegalProvisions: {result.provision_count}")
    console.print(f"LegalElements: {result.element_count}")
    console.print(f"Audit fingerprint: {result.audit_fingerprint}")


@parse_app.command(name="status")
def parse_status_command() -> None:
    """Exibe contagens e fingerprint da materialização."""
    with SessionLocal() as session:
        status = materialization_status(session)
    for key, value in status.items():
        console.print(f"{key}={value}")


def _embedding_provider() -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(
        settings.ollama_base_url,
        settings.embedding_model,
        settings.embedding_timeout,
    )


@index_app.command(name="build")
def index_build_command() -> None:
    """Materializa chunks, FTS e embeddings do snapshot jurídico ativo."""
    try:
        with SessionLocal() as session:
            result = build_search_index(
                session,
                _embedding_provider(),
                model_name=settings.embedding_model,
                batch_size=settings.embedding_batch_size,
            )
    except Exception as exc:
        console.print(f"[bold red]Falha na indexação:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"Resultado: [bold cyan]{result.outcome.value}[/bold cyan]")
    console.print(f"Chunks: {result.chunks}")
    console.print(f"Embeddings: {result.embeddings}")
    console.print(f"Dimensões: {result.dimensions}")
    console.print(
        f"Modelo: {result.provider_name}/{result.model_name}/{result.model_version}"
    )


@index_app.command(name="status")
def index_status_command() -> None:
    """Exibe contagens do índice jurídico persistido."""
    with SessionLocal() as session:
        chunks = int(session.scalar(select(func.count()).select_from(Chunk)) or 0)
        embeddings = int(
            session.scalar(select(func.count()).select_from(Embedding)) or 0
        )
        dimensions = session.scalar(select(Embedding.dimensions).limit(1))
    console.print(f"chunks={chunks}")
    console.print(f"embeddings={embeddings}")
    console.print(f"dimensions={dimensions or 0}")


@retrieval_app.command(name="search")
def retrieval_search_command(
    query: str,
    mode: str = typer.Option("hybrid", help="lexical, vector ou hybrid"),
    limit: int = typer.Option(10, min=1, max=100),
    act: str | None = typer.Option(None, help="CF/88 ou ADCT"),
    element_types: str | None = typer.Option(
        None, help="Tipos separados por vírgula, ex.: CAPUT,PARAGRAPH"
    ),
) -> None:
    """Executa retrieval diagnóstico sem criar EvidenceSet ou resposta jurídica."""
    selected_types = tuple(
        value.strip().upper()
        for value in (element_types or "").split(",")
        if value.strip()
    )
    filters = RetrievalFilters(act=act, element_types=selected_types)
    with SessionLocal() as session:
        if mode == "lexical":
            candidates = lexical_search(session, query, limit=limit, filters=filters)
        elif mode == "vector":
            candidates = vector_search(
                session,
                query,
                _embedding_provider(),
                model_name=settings.embedding_model,
                limit=limit,
                filters=filters,
            )
        elif mode == "hybrid":
            candidates = hybrid_search(
                session,
                query,
                _embedding_provider(),
                model_name=settings.embedding_model,
                limit=limit,
                filters=filters,
            )
        else:
            raise typer.BadParameter("mode deve ser lexical, vector ou hybrid")
    for position, item in enumerate(candidates, start=1):
        console.print(
            f"{position}. {item.legal_act} {item.element_type} "
            f"{item.number_label or ''} | chunk={item.chunk_id}"
        )
        console.print(
            f"   lexical_rank={item.lexical_rank} vector_rank={item.vector_rank} "
            f"rrf={item.rrf_score}"
        )
        console.print(f"   identity={item.identity_key}")
        console.print(f"   {item.chunk_text[:240]}")


@document_app.command(name="list")
def document_list() -> None:
    """Lista documentos jurídicos armazenados."""
    console.print("[cyan]Documentos armazenados:[/cyan] (Nenhum documento cadastrado)")


@document_app.command(name="show")
def document_show(doc_id: str) -> None:
    """Exibe o conteúdo e metadados de um documento."""
    console.print(f"[cyan]Exibindo documento:[/cyan] {doc_id}")


@app.command()
def search(query: str) -> None:
    """Executa busca na legislação normada."""
    console.print(f"[bold blue]Buscando por:[/bold blue] {query}")


@app.command()
def consult(
    question: str,
    limit: int = typer.Option(None, min=1, max=20, help="Quantidade de evidências."),
    act: str | None = typer.Option(None, help="Restringe a CF/88 ou ADCT."),
) -> None:
    """Executa consulta jurídica com respostas fundamentadas."""
    top_k = limit or settings.consultation_top_k
    provider = _embedding_provider()
    generator = OllamaLegalGenerator(
        settings.ollama_base_url,
        settings.ollama_model,
        settings.consultation_timeout,
        settings.consultation_max_tokens,
    )
    semantic_validator = OllamaSemanticSupportValidator(
        settings.ollama_base_url,
        settings.semantic_judge_model or settings.ollama_model,
        settings.consultation_timeout,
    )
    try:
        with SessionLocal() as session:
            result = run_consultation(
                session,
                question,
                retriever=lambda value: hybrid_search(
                    session,
                    value,
                    provider,
                    model_name=settings.embedding_model,
                    limit=top_k,
                    filters=RetrievalFilters(act=act),
                ),
                generator=generator,
                model_name=settings.ollama_model,
                max_generation_attempts=settings.consultation_max_attempts,
                evidence_limit=settings.consultation_evidence_limit,
                semantic_validator=semantic_validator,
            )
    except Exception as exc:
        console.print(f"[bold red]Falha na consulta:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"Resultado: [bold cyan]{result.outcome.value}[/bold cyan]")
    console.print(f"EvidenceSet: {result.evidence_set_id}")
    console.print(result.answer)
    if result.claims:
        console.print("[bold]Afirmações e citações validadas:[/bold]")
        for claim in result.claims:
            console.print(
                f"- {claim.claim_code}: {claim.text} "
                f"[{', '.join(claim.evidence_codes)}]"
            )
        console.print("[bold]Fontes oficiais:[/bold]")
        for citation in result.citations:
            console.print(
                f"- [{citation.evidence_code}] {citation.citation_label}\n"
                f"  {citation.source_url}"
            )
    if result.validation_errors:
        console.print("[yellow]A resposta gerada foi recusada pela validação.[/yellow]")


DEFAULT_EVALUATION_DATASET = Path("evaluation/datasets/mvp1_v1.json")


def _evaluation_search(session, provider, mode: str):
    def search(query: str, limit: int):
        filters = RetrievalFilters()
        if mode == "lexical":
            return lexical_search(session, query, limit=limit, filters=filters)
        if mode == "vector":
            return vector_search(
                session,
                query,
                provider,
                model_name=settings.embedding_model,
                limit=limit,
                filters=filters,
            )
        return hybrid_search(
            session,
            query,
            provider,
            model_name=settings.embedding_model,
            limit=limit,
            filters=filters,
        )

    return search


@eval_app.command(name="retrieval")
def eval_retrieval_command(
    dataset: Annotated[Path, typer.Option(exists=True)] = DEFAULT_EVALUATION_DATASET,
    case_limit: int | None = typer.Option(None, min=1),
    output: Annotated[
        Path | None, typer.Option(help="Relatório JSON opcional.")
    ] = None,
) -> None:
    """Compara lexical, vector e hybrid no dataset versionado."""
    version, cases = load_dataset(dataset)
    if case_limit is not None:
        cases = cases[:case_limit]
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_version": version,
        "provider": "ollama",
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": 768,
        "rrf_k": 60,
        "top_k": 10,
        "modes": {},
    }
    provider = _embedding_provider()
    with SessionLocal() as session:
        for mode in ("lexical", "vector", "hybrid"):
            started = time.perf_counter()
            metrics = evaluate_retrieval(
                mode,
                cases,
                _evaluation_search(session, provider, mode),
            )
            elapsed = time.perf_counter() - started
            mode_payload = metrics.as_dict()
            mode_payload["elapsed_seconds"] = elapsed
            payload["modes"][mode] = mode_payload
            console.print(
                f"{mode}: Hit@1={metrics.hit_at_1:.3f} "
                f"Hit@10={metrics.hit_at_10:.3f} MRR={metrics.mrr:.3f} "
                f"Recall@10={metrics.recall_at_10:.3f} ({elapsed:.2f}s)"
            )
    if output:
        write_json_report(output, payload)
        console.print(f"Relatório: {output}")


@eval_app.command(name="consultation")
def eval_consultation_command(
    dataset: Annotated[Path, typer.Option(exists=True)] = DEFAULT_EVALUATION_DATASET,
    case_limit: int = typer.Option(5, min=1, max=50),
    model: str | None = typer.Option(None),
    category: str | None = typer.Option(None),
    output: Annotated[
        Path | None, typer.Option(help="Relatório JSON opcional.")
    ] = None,
) -> None:
    """Executa amostra generativa; persiste sua cadeia de auditoria."""
    _version, cases = load_dataset(dataset)
    selected = tuple(
        case for case in cases if category is None or case.category == category
    )[:case_limit]
    provider = _embedding_provider()
    generator = OllamaLegalGenerator(
        settings.ollama_base_url,
        model or settings.ollama_model,
        settings.consultation_timeout,
        settings.consultation_max_tokens,
    )
    semantic_validator = OllamaSemanticSupportValidator(
        settings.ollama_base_url,
        settings.semantic_judge_model or model or settings.ollama_model,
        settings.consultation_timeout,
    )
    outcomes = []
    case_results = []
    with SessionLocal() as session:
        for case in selected:
            started = time.perf_counter()
            result = run_consultation(
                session,
                case.question,
                retriever=lambda query, act=case.expected_act: hybrid_search(
                    session,
                    query,
                    provider,
                    model_name=settings.embedding_model,
                    limit=settings.consultation_top_k,
                    filters=RetrievalFilters(act=act),
                ),
                generator=generator,
                model_name=model or settings.ollama_model,
                max_generation_attempts=settings.consultation_max_attempts,
                evidence_limit=settings.consultation_evidence_limit,
                semantic_validator=semantic_validator,
            )
            answered = result.outcome.value == "ANSWERED"
            outcomes.append((case, answered))
            case_results.append(
                {
                    "case_id": case.id,
                    "category": case.category,
                    "expected_answer": case.expect_answer,
                    "outcome": result.outcome.value,
                    "claims": len(result.claims),
                    "citations": len(result.citations),
                    "validation_errors": list(result.validation_errors),
                    "elapsed_seconds": time.perf_counter() - started,
                }
            )
            console.print(f"{case.id}: {result.outcome.value} {result.evidence_set_id}")
    metrics = aggregate_decisions(tuple(outcomes))
    console.print(
        f"decision_accuracy={metrics.correct_decision_rate:.3f} "
        f"unsafe_answers={metrics.expected_abstain_responded} "
        f"false_abstentions={metrics.expected_answer_abstained}"
    )
    if output:
        write_json_report(
            output,
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "dataset_version": _version,
                "provider": "ollama",
                "model": model or settings.ollama_model,
                "cases": case_results,
                "decision_metrics": {
                    "cases": metrics.cases,
                    "expected_answer_responded": metrics.expected_answer_responded,
                    "expected_answer_abstained": metrics.expected_answer_abstained,
                    "expected_abstain_responded": metrics.expected_abstain_responded,
                    "expected_abstain_abstained": metrics.expected_abstain_abstained,
                    "correct_decision_rate": metrics.correct_decision_rate,
                },
            },
        )
        console.print(f"Relatório: {output}")


@eval_app.command(name="quality")
def eval_quality_command(
    dataset: Annotated[Path, typer.Option(exists=True)] = DEFAULT_EVALUATION_DATASET,
    output: Annotated[
        Path | None, typer.Option(help="Relatório JSON opcional.")
    ] = None,
) -> None:
    """Avalia selection e sufficiency sem chamar o modelo generativo."""
    version, cases = load_dataset(dataset)
    provider = _embedding_provider()
    started = time.perf_counter()
    with SessionLocal() as session:
        metrics = evaluate_evidence_quality(
            cases,
            _evaluation_search(session, provider, "hybrid"),
            evidence_limit=settings.consultation_evidence_limit,
        )
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_version": version,
        "elapsed_seconds": time.perf_counter() - started,
        **metrics,
    }
    console.print(
        f"abstention={metrics['correct_abstention_rate']:.3f} "
        f"unsafe={metrics['unsafe_answer_rate']:.3f} "
        f"false_abstention={metrics['false_abstention_rate']:.3f}"
    )
    if output:
        write_json_report(output, payload)
        console.print(f"Relatório: {output}")


@eval_app.command(name="semantic-judge")
def eval_semantic_judge_command(
    dataset: Annotated[Path, typer.Option(exists=True)] = Path(
        "evaluation/datasets/semantic_support_v1.json"
    ),
    model: str | None = typer.Option(None),
    output: Annotated[
        Path | None, typer.Option(help="Relatório JSON opcional.")
    ] = None,
) -> None:
    """Avalia isoladamente o juiz semântico local."""
    version, cases = load_semantic_dataset(dataset)
    selected_model = model or settings.semantic_judge_model or settings.ollama_model
    validator = OllamaSemanticSupportValidator(
        settings.ollama_base_url, selected_model, settings.consultation_timeout
    )
    metrics = benchmark_semantic_judge(cases, validator)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_version": version,
        "model": selected_model,
        **metrics,
    }
    console.print(
        f"accuracy={metrics['accuracy']:.3f} "
        f"supported_recall={metrics['supported_recall']:.3f} "
        f"unsafe={metrics['unsafe_acceptance']}"
    )
    if output:
        write_json_report(output, payload)
        console.print(f"Relatório: {output}")


@eval_app.command(name="all")
def eval_all_command(
    dataset: Annotated[Path, typer.Option(exists=True)] = DEFAULT_EVALUATION_DATASET,
    consultation_limit: int = typer.Option(5, min=1, max=50),
) -> None:
    """Executa retrieval completo e amostra generativa configurada."""
    eval_retrieval_command(dataset=dataset, case_limit=None, output=None)
    eval_consultation_command(
        dataset=dataset,
        case_limit=consultation_limit,
        model=None,
        category=None,
        output=None,
    )


if __name__ == "__main__":
    app()
