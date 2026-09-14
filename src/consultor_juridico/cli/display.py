"""Helpers Rich exclusivos da camada de apresentação."""

from collections.abc import Callable

from rich.console import Console

from consultor_juridico.domain.rag import QueryMode
from consultor_juridico.evaluation.selected_answerer import SELECTED_MODEL


def active_model_label() -> str:
    """Nome amigável derivado da identidade canônica do answerer."""
    name, separator, tag = SELECTED_MODEL.partition(":")
    return f"{name.capitalize()}{separator}{tag}"


def run_with_query_feedback[T](
    console: Console,
    mode: QueryMode,
    operation: Callable[[], T],
) -> T:
    """Mostra atividade somente em LEGAL_RULE com terminal interativo."""
    if mode is not QueryMode.LEGAL_RULE or not console.is_terminal:
        return operation()
    with console.status(
        "[bold cyan]Consultando a legislação e validando a resposta...[/bold cyan]",
        spinner="dots",
    ):
        result = operation()
    console.print("[green]✓ Resposta preparada[/green]")
    return result
