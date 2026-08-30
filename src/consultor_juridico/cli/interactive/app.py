"""Interface interativa enxuta sobre o workflow real do MVP2."""

from uuid import uuid4

from langgraph.types import Command
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from consultor_juridico import __version__
from consultor_juridico.application.workflow import initial_state
from consultor_juridico.application.workflow.diagnostics import WorkflowDiagnostics
from consultor_juridico.cli.composition import (
    consultation_graph,
    workflow_context,
)
from consultor_juridico.domain import ConsultationOutcome, Question

console = Console()


def run_interactive_cli() -> None:
    """Executa consultas até o usuário optar por sair."""
    console.print(
        Panel(
            f"Consultor Jurídico {__version__}\nCF/88 e ADCT — fontes oficiais",
            title="MVP2",
            border_style="green",
        )
    )
    while True:
        choice = Prompt.ask(
            "[bold]Escolha[/bold]",
            choices=("1", "2"),
            default="1",
            show_choices=False,
        )
        if choice == "2":
            console.print("Até logo.")
            return
        question = Prompt.ask("Pergunta jurídica").strip()
        if question:
            _run_question(question)


def run_question(text: str, *, verbose: bool = False) -> None:
    graph = consultation_graph()
    context = workflow_context()
    config = {"configurable": {"thread_id": str(uuid4())}}
    try:
        result = graph.invoke(
            initial_state(Question(text)), context=context, config=config
        )
        while result.get("__interrupt__"):
            payload = result["__interrupt__"][0].value
            console.print("[yellow]Preciso esclarecer sua pergunta.[/yellow]")
            console.print(payload["question"])
            for index, option in enumerate(payload.get("options", ()), start=1):
                console.print(f"{index}. {option}")
            answer = Prompt.ask("Esclarecimento")
            result = graph.invoke(
                Command(resume=answer), context=context, config=config
            )
    except Exception as exc:
        console.print(f"[red]Falha técnica na consulta: {exc}[/red]")
        if verbose:
            _show_diagnostics(context.diagnostics, text)
        return
    final = result["final_result"]
    style = "green" if final.outcome is ConsultationOutcome.ANSWERED else "yellow"
    console.print(
        Panel(final.answer, title="Resposta Fundamentada", border_style=style)
    )
    if final.outcome is ConsultationOutcome.ANSWERED:
        _show_evidence(final.evidence)
    if verbose:
        _show_diagnostics(context.diagnostics, text)


def _run_question(text: str) -> None:
    run_question(text)


def _show_evidence(evidence) -> None:
    table = Table("ID", "Referência", "Dispositivo", "Fonte oficial")
    for item in evidence:
        citation = (
            "; ".join(part.citation_text for part in item.citation_items) or item.text
        )
        table.add_row(
            item.candidate_id,
            item.stable_reference,
            citation[:280],
            item.source_url,
        )
    console.print(table)


def _show_diagnostics(diagnostics: WorkflowDiagnostics, question: str) -> None:
    console.print("\n[bold cyan]Workflow diagnóstico[/bold cyan]")
    console.print(f"Pergunta: {question}")
    console.print(f"Rota: {' → '.join(diagnostics.route)}")

    timings = Table("Nó", "Tentativa", "Duração", "Erro")
    for item in diagnostics.node_timings:
        timings.add_row(
            item.node,
            str(item.attempt),
            f"{item.duration_ms:.1f} ms",
            item.error or "-",
        )
    console.print(timings)

    for node, entries in diagnostics.details.items():
        for entry in entries:
            console.print(f"[bold]{node}[/bold]: {_safe_detail(entry)}")

    calls = Table("Operação", "Papel", "Modelo", "Duração", "Chars", "Output", "Erro")
    for call in diagnostics.provider_calls:
        calls.add_row(
            call.operation,
            call.role,
            call.model or "N/A",
            f"{call.duration_ms:.1f} ms",
            str(call.request_chars),
            call.output_validation,
            call.error_kind or "-",
        )
    console.print(calls)
    for call in diagnostics.provider_calls:
        if call.operation != "chat":
            continue
        console.print(
            f"Ollama native [{call.role}; model={call.model or 'N/A'}]: "
            f"total={_milliseconds(call.total_duration_ms)}; "
            f"load={_milliseconds(call.load_duration_ms)}; "
            f"prompt_eval_count={_value(call.prompt_eval_count)}; "
            f"prompt_eval={_milliseconds(call.prompt_eval_duration_ms)}; "
            f"eval_count={_value(call.eval_count)}; "
            f"eval={_milliseconds(call.eval_duration_ms)}; "
            f"prompt_tok/s={_rate(call.prompt_tokens_per_second)}; "
            f"generation_tok/s={_rate(call.generation_tokens_per_second)}"
        )
        if call.error_kind:
            console.print(
                f"Provider error [{call.role}; model={call.model or 'N/A'}]: "
                f"category={call.provider_error_category or 'N/A'}; "
                f"status={call.provider_http_status or 'N/A'}; "
                f"message={call.provider_message or 'N/A'}"
            )
    console.print(f"Execuções por nó: {diagnostics.node_execution_counts}")
    console.print(
        f"Chamadas Ollama: embedding={diagnostics.embedding_calls}; "
        f"chat={diagnostics.chat_calls}"
    )
    if diagnostics.abstention_cause is not None:
        console.print(f"Causa da abstention: {diagnostics.abstention_cause.value}")
    console.print(f"Tempo total dos nós: {diagnostics.workflow_total_ms:.1f} ms")


def _safe_detail(detail: dict[str, object]) -> str:
    """Renderiza somente contrato estruturado e metadados, nunca prompts."""
    return "; ".join(f"{key}={value}" for key, value in detail.items())


def _milliseconds(value: float | None) -> str:
    return f"{value:.1f} ms" if value is not None else "N/A"


def _rate(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "N/A"


def _value(value: object | None) -> str:
    return str(value) if value is not None else "N/A"
