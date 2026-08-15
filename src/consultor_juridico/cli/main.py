"""Entrypoint da CLI do Consultor Jurídico (Typer + Rich)."""

import typer
from rich.console import Console

from consultor_juridico import __version__
from consultor_juridico.ingestion import get_ingestion_status, run_planalto_ingestion
from consultor_juridico.services import db_service

app = typer.Typer(
    name="consultor-juridico",
    help="Mecanismo CLI-first de consulta jurídica da CF/88 e ADCT.",
    add_completion=False,
)

db_app = typer.Typer(help="Gerenciamento de banco de dados e migrations.")
ingest_app = typer.Typer(help="Comandos de ingestão de documentos oficiais.")
document_app = typer.Typer(help="Visualização de documentos jurídicos.")

app.add_typer(db_app, name="db")
app.add_typer(ingest_app, name="ingest")
app.add_typer(document_app, name="document")

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
def consult(question: str) -> None:
    """Executa consulta jurídica com respostas fundamentadas."""
    console.print(f"[bold green]Consultando:[/bold green] {question}")


@app.command()
def embedding() -> None:
    """Gerencia ou gera embeddings para a legislação."""
    console.print("[cyan]Comando de embeddings.[/cyan]")


@app.command()
def evaluate() -> None:
    """Executa a suite de avaliação do RAG e evidências."""
    console.print("[cyan]Executando avaliação...[/cyan]")


if __name__ == "__main__":
    app()
