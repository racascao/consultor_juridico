"""Interface pública CLI-first do MVP2."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from consultor_juridico import __version__
from consultor_juridico.application.retrieval import (
    evaluate_retrieval,
    load_retrieval_dataset,
    write_evaluation,
)
from consultor_juridico.cli.composition import candidate_retriever, index_builder
from consultor_juridico.cli.interactive.bootstrap import (
    corpus_builder,
    corpus_rematerializer,
    corpus_repository,
    run_bootstrap,
)
from consultor_juridico.domain import (
    Question,
    SourceSnapshotIntegrityError,
    SourceSnapshotNotFound,
)
from consultor_juridico.services import db_service

app = typer.Typer(
    name="consultor-juridico",
    help="Consulta local e rastreável à CF/88 e ao ADCT (MVP2).",
    add_completion=False,
)
db_app = typer.Typer(help="Migrations e diagnóstico do PostgreSQL.")
corpus_app = typer.Typer(help="Corpus constitucional contextual.")
index_app = typer.Typer(help="Embeddings persistentes das SearchUnits.")
retrieval_app = typer.Typer(help="Diagnóstico do retrieval híbrido.")
eval_app = typer.Typer(help="Avaliações funcionais versionadas.")
app.add_typer(db_app, name="db")
app.add_typer(corpus_app, name="corpus")
app.add_typer(index_app, name="indice")
app.add_typer(retrieval_app, name="retrieval")
app.add_typer(eval_app, name="eval")
console = Console()


@app.command()
def version() -> None:
    """Exibe a versão do pacote."""
    console.print(f"Consultor Jurídico [cyan]{__version__}[/cyan]")


@app.command(name="consultar")
def consult(
    question: Annotated[str, typer.Argument(help="Pergunta jurídica.")],
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Exibe diagnóstico técnico seguro."),
    ] = False,
) -> None:
    """Executa uma consulta pelo workflow real do MVP2."""
    from consultor_juridico.cli.interactive.app import run_question

    run_question(question, verbose=verbose)


@app.command()
def bootstrap() -> None:
    """Prepara migrations, corpus e embeddings de modo idempotente."""
    failed = False
    for event in run_bootstrap():
        color = "red" if event.state == "failed" else "green"
        console.print(f"[{color}]{event.step}: {event.message}[/{color}]")
        failed |= event.state == "failed"
    if failed:
        raise typer.Exit(code=1)


@db_app.command(name="migrate")
def db_migrate() -> None:
    """Aplica a baseline v0.2."""
    db_service.run_migrations()
    console.print("[green]Migrations aplicadas.[/green]")


@db_app.command(name="status")
def db_status() -> None:
    """Exibe conectividade e revision Alembic."""
    status = db_service.check_db_status()
    if not status.get("connected"):
        console.print(f"[red]PostgreSQL indisponível: {status.get('error')}[/red]")
        raise typer.Exit(code=1)
    console.print(f"Alembic: {status.get('alembic_version') or '-'}")
    console.print(f"Tabelas: {', '.join(status.get('tables', []))}")


@corpus_app.command(name="construir")
def corpus_build() -> None:
    """Captura e constrói a baseline contextual idempotente."""
    db_service.run_migrations()
    result = corpus_builder().execute()
    console.print(
        f"{result.outcome.value}: {result.provisions} provisions; "
        f"{result.search_units} SearchUnits"
    )


@corpus_app.command(name="status")
def corpus_status() -> None:
    """Exibe a prontidão do corpus contextual."""
    status = corpus_repository().status()
    console.print(f"Estado: {'READY' if status.ready else 'NOT_READY'}")
    console.print(f"Snapshot: {status.active_snapshot_sha256 or '-'}")
    for code, count in status.provisions_by_act:
        console.print(f"Provisions {code}: {count}")
    for unit_type, count in status.search_units_by_type:
        console.print(f"SearchUnits {unit_type}: {count}")


@corpus_app.command(name="rematerializar")
def corpus_rematerialize(
    snapshot_sha: Annotated[
        str,
        typer.Option(
            "--snapshot-sha",
            help=(
                "SHA-256 da captura já persistida. Valida os bytes e aplica a "
                "projeção atual sem acessar o Planalto."
            ),
        ),
    ],
) -> None:
    """Rematerializa uma captura imutável persistida, sem aquisição HTTP."""
    db_service.run_migrations()
    try:
        result = corpus_rematerializer().execute(snapshot_sha)
    except SourceSnapshotNotFound as exc:
        console.print(f"[red]SNAPSHOT_NOT_FOUND: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except SourceSnapshotIntegrityError as exc:
        console.print(f"[red]SOURCE_SNAPSHOT_INTEGRITY_ERROR: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(
        f"{result.outcome.value}: snapshot={result.snapshot_sha256}; "
        f"{result.provisions} provisions; {result.search_units} SearchUnits"
    )


@index_app.command(name="construir")
def index_build() -> None:
    """Cria somente embeddings ausentes ou obsoletas."""
    result = index_builder().execute()
    console.print(
        f"Embeddings atualizadas: {result.embedded}; "
        f"modelo={result.model}; dimensões={result.dimensions}"
    )


@retrieval_app.command(name="rastrear")
def retrieval_trace(
    question: str,
    limit: int = typer.Option(10, min=1, max=50),
) -> None:
    """Exibe ranks lexical, vetorial e fundido sem chamar chat LLM."""
    candidates = candidate_retriever().retrieve(Question(question), limit)
    table = Table("Rank", "Tipo", "Ato", "Referência", "Lex", "Vet", "Texto")
    for item in candidates:
        table.add_row(
            str(item.fused_rank),
            item.search_unit_type,
            item.legal_act_code,
            item.stable_reference,
            str(item.lexical_rank or "-"),
            str(item.vector_rank or "-"),
            item.text.replace("\n", " ")[:100],
        )
    console.print(table)


DEFAULT_DATASET = Path("evaluation/datasets/basic_direct_v1.json")


@eval_app.command(name="retrieval")
def eval_retrieval(
    dataset: Annotated[Path, typer.Option(exists=True)] = DEFAULT_DATASET,
    output: Annotated[Path, typer.Option()] = Path(
        "evaluation/results/mvp2_retrieval_baseline.json"
    ),
) -> None:
    """Avalia retrieval híbrido no dataset funcional congelado."""
    version_name, cases = load_retrieval_dataset(dataset)
    result = evaluate_retrieval(candidate_retriever(), cases)
    write_evaluation(output, version_name, result)
    console.print(
        f"cases={result.cases} Hit@1={result.hit_at_1:.3f} "
        f"Hit@3={result.hit_at_3:.3f} Hit@10={result.hit_at_10:.3f} "
        f"MRR={result.mrr:.3f}"
    )
    console.print(f"Relatório: {output}")


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """Abre a interface interativa quando nenhum comando foi informado."""
    if ctx.invoked_subcommand is None:
        from consultor_juridico.cli.interactive.app import run_interactive_cli

        run_interactive_cli()


if __name__ == "__main__":
    app()
