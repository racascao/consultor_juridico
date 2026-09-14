"""Apresentação interativa do MVP2, construída somente com Rich."""

from collections.abc import Callable

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from consultor_juridico import __version__
from consultor_juridico.cli.display import active_model_label, run_with_query_feedback
from consultor_juridico.domain.rag import QueryMode
from consultor_juridico.services.bootstrap import BootstrapReadiness

TUTORIAL = """
# Como usar

O corpus atual contém a **Lei nº 9.784/1999**. Escolha **regra jurídica** para
perguntas gerais, como “qual é o prazo para recurso administrativo?”.

Escolha **situação concreta** quando houver fatos pessoais. No MVP2 esse modo
solicita esclarecimentos e não aplica automaticamente a lei ao caso. As fontes
exibidas são citações validadas do snapshot oficial local.
"""


def show_banner(console: Console) -> None:
    console.print(
        Panel.fit(
            "[bold]CONSULTOR JURÍDICO[/bold]\n"
            f"MVP2 · Lei 9.784/1999 · {active_model_label()} · RAG local\n"
            f"versão {__version__}",
            border_style="cyan",
        )
    )


def show_status(console: Console, readiness: BootstrapReadiness) -> None:
    table = Table(title="Status do sistema", show_header=False)
    for label, value in (
        ("PostgreSQL", readiness.database),
        ("Migrations", readiness.migrations),
        ("Corpus", readiness.corpus),
        ("Retrieval FTS", readiness.retrieval),
        ("Ollama", readiness.ollama),
        (active_model_label(), readiness.model),
    ):
        table.add_row(label, "[green]OK[/green]" if value else "[red]PENDENTE[/red]")
    table.add_row(
        "Sistema",
        "[bold green]READY[/bold green]"
        if readiness.ready
        else "[bold red]NOT READY[/bold red]",
    )
    console.print(table)


def run_interactive_cli(
    *,
    console: Console,
    readiness: Callable[[], BootstrapReadiness],
    consult: Callable[[str, QueryMode], None],
) -> None:
    show_banner(console)
    show_status(console, readiness())
    while True:
        console.print(
            "\n[bold]1.[/bold] Consultar uma regra jurídica\n"
            "[bold]2.[/bold] Perguntar sobre uma situação concreta\n"
            "[bold]3.[/bold] Status do sistema\n"
            "[bold]4.[/bold] Tutorial\n"
            "[bold]5.[/bold] Ajuda\n"
            "[bold]6.[/bold] Sobre\n"
            "[bold]7.[/bold] Sair"
        )
        try:
            choice = Prompt.ask("Opção", choices=[str(i) for i in range(1, 8)])
            if choice in {"1", "2"}:
                question = Prompt.ask("Pergunta").strip()
                if question:
                    mode = (
                        QueryMode.LEGAL_RULE
                        if choice == "1"
                        else QueryMode.CASE_APPLICATION
                    )
                    run_with_query_feedback(
                        console,
                        mode,
                        lambda question=question, mode=mode: consult(question, mode),
                    )
            elif choice == "3":
                show_status(console, readiness())
            elif choice == "4":
                console.print(Markdown(TUTORIAL))
            elif choice == "5":
                console.print(
                    "Use as opções numeradas. Para automação, execute "
                    "[bold]consultor_juridico --help[/bold]."
                )
            elif choice == "6":
                console.print(
                    Panel(
                        "Consulta experimental baseada em fonte oficial. "
                        "Não substitui orientação jurídica profissional.",
                        title="Sobre",
                    )
                )
            else:
                console.print("[green]Até logo.[/green]")
                return
        except (EOFError, KeyboardInterrupt):
            console.print("\n[green]Até logo.[/green]")
            return
