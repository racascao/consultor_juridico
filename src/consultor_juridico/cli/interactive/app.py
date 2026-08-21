"""Interface interativa de terminal amigável para o Consultor Jurídico."""

import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from sqlalchemy import func, select

from consultor_juridico import __version__
from consultor_juridico.cli.interactive.bootstrap import run_bootstrap
from consultor_juridico.cli.interactive.readiness import (
    check_readiness,
)
from consultor_juridico.config import settings
from consultor_juridico.consultation import (
    OllamaLegalGenerator,
    OllamaSemanticSupportValidator,
    run_consultation,
)
from consultor_juridico.consultation.types import ConsultationOutcome
from consultor_juridico.db.session import SessionLocal
from consultor_juridico.models import Chunk, Embedding, LegalVersion
from consultor_juridico.parsing import materialization_status
from consultor_juridico.retrieval import (
    OllamaEmbeddingProvider,
    RetrievalFilters,
    hybrid_search,
)
from consultor_juridico.services import db_service

console = Console()


def _embedding_provider() -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(
        settings.ollama_base_url,
        settings.embedding_model,
        settings.embedding_timeout,
    )


def show_banner() -> None:
    """Renderiza o cabeçalho principal da aplicação."""
    console.print()
    banner = Panel(
        Text.assemble(
            ("CONSULTOR JURÍDICO\n", "bold green"),
            (
                (
                    f"Versão {__version__} | CF/88 & ADCT • Fontes Oficiais • "
                    "Execução Local"
                ),
                "cyan",
            ),
        ),
        subtitle="MVP1 — Apresentação e Rastreabilidade Jurídica",
        border_style="green",
        expand=False,
    )
    console.print(banner)


def handle_bootstrap() -> bool:
    """Gerencia o fluxo visual de preparação da base de dados e modelos."""
    readiness = check_readiness()
    if readiness.is_ready:
        return True

    console.print(
        "\n[bold yellow]Primeira execução ou ambiente incompleto detectado."
        "[/bold yellow]"
    )
    console.print(
        "Preparando a base jurídica local. Isso pode levar alguns minutos se novos "
        "modelos forem baixados.\n"
    )

    try:
        for event in run_bootstrap():
            if event.step == "all":
                if event.state == "success":
                    console.print(f"\n[bold green]✓ {event.message}[/bold green]")
                    return True
                else:
                    console.print(f"\n[bold red]✗ {event.message}[/bold red]")
                    return False

            if event.state == "running":
                console.print(f"  [yellow]⠋[/yellow] {event.message}")
            elif event.state == "success":
                console.print(f"  [green]✓[/green] {event.message}")
            elif event.state == "failed":
                console.print(f"  [red]✗[/red] {event.message}")

                # Apresenta erro de forma amigável
                error_panel = Panel(
                    Text.assemble(
                        ("Erro durante a inicialização:\n\n", "bold red"),
                        (event.message, "white"),
                    ),
                    title="Falha na Preparação",
                    border_style="red",
                )
                console.print(error_panel)
                return False
    except KeyboardInterrupt:
        console.print(
            "\n[bold red]✗ Inicialização interrompida pelo usuário (Ctrl+C).[/bold red]"
        )
        console.print(
            "[yellow]O ambiente está parcialmente preparado. Você pode rodar a "
            "aplicação novamente para continuar de onde parou.[/yellow]\n"
        )
        sys.exit(0)
    except Exception as exc:
        console.print(
            f"\n[bold red]✗ Ocorreu um erro inesperado no bootstrap: {exc}[/bold red]"
        )
        return False

    return True


def run_consultation_screen() -> None:
    """Tela interativa para realizar consultas jurídicas."""
    console.print("\n[bold green]=== Fazer Consulta Jurídica ===[/bold green]")
    console.print("Faça perguntas sobre a Constituição Federal de 1988 e o ADCT.\n")

    question = Prompt.ask("[bold]Sua pergunta[/bold]")
    if not question.strip():
        console.print("[yellow]Pergunta vazia. Retornando ao menu.[/yellow]")
        return

    # Orquestração do pipeline
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

    with console.status(
        "[yellow]Buscando dispositivos relevantes e validando resposta com LLM "
        "local...[/yellow]"
    ) as status:
        try:
            with SessionLocal() as session:
                # Busca as versões ativas
                active_versions = session.scalars(
                    select(LegalVersion).where(
                        LegalVersion.is_active_for_query.is_(True)
                    )
                ).all()
                if len(active_versions) != 2:
                    status.stop()
                    console.print(
                        "[bold red]Erro: O índice jurídico não possui versões ativas "
                        "configuradas corretamente.[/bold red]"
                    )
                    return

                result = run_consultation(
                    session,
                    question,
                    retriever=lambda query: hybrid_search(
                        session,
                        query,
                        provider,
                        model_name=settings.embedding_model,
                        limit=settings.consultation_top_k,
                        filters=RetrievalFilters(),
                    ),
                    generator=generator,
                    model_name=settings.ollama_model,
                    max_generation_attempts=settings.consultation_max_attempts,
                    evidence_limit=settings.consultation_evidence_limit,
                    semantic_validator=semantic_validator,
                )
        except Exception as exc:
            status.stop()
            error_panel = Panel(
                Text.assemble(
                    ("Erro técnico ao executar consulta:\n\n", "bold red"),
                    (str(exc), "white"),
                ),
                title="Falha Técnica",
                border_style="red",
            )
            console.print(error_panel)
            return

    if result.outcome == ConsultationOutcome.ABSTAINED:
        abstain_panel = Panel(
            Text(
                "Não há evidência constitucional oficial suficiente no corpus "
                "consultado\n"
                "para responder a esta pergunta com segurança.",
                style="yellow",
            ),
            title="Evidência Insuficiente",
            border_style="yellow",
        )
        console.print(abstain_panel)
        return

    # Exibe a resposta de forma organizada
    response_panel = Panel(
        Text(result.answer, style="white"),
        title="Resposta Fundamentada",
        border_style="green",
    )
    console.print(response_panel)

    # Exibe as claims/afirmações e citações validadas
    if result.claims:
        claims_table = Table(
            title="Afirmações e Citações Validadas", border_style="cyan"
        )
        claims_table.add_column("Código", style="bold cyan", width=8)
        claims_table.add_column("Cadeia de Evidência", style="white")
        claims_table.add_column("Fontes de Citação", style="dim")

        for claim in result.claims:
            claims_table.add_row(
                claim.claim_code, claim.text, ", ".join(claim.evidence_codes)
            )
        console.print(claims_table)

    if result.citations:
        citations_table = Table(
            title="Fontes Oficiais e Rastreabilidade", border_style="cyan"
        )
        citations_table.add_column("Evidência", style="bold cyan", width=10)
        citations_table.add_column("Dispositivo Constitucional", style="white")
        citations_table.add_column("Link Oficial Planalto", style="blue underline")

        for citation in result.citations:
            citations_table.add_row(
                citation.evidence_code, citation.citation_label, citation.source_url
            )
        console.print(citations_table)


def run_exploration_screen() -> None:
    """Tela interativa para explorar e pesquisar na Constituição."""
    console.print(
        "\n[bold green]=== Explorar / Pesquisar a Constituição ===[/bold green]"
    )
    console.print("Busca direta na CF/88 e ADCT usando o retrieval híbrido local.\n")

    query = Prompt.ask("[bold]Termo ou assunto para pesquisa[/bold]")
    if not query.strip():
        console.print("[yellow]Pesquisa vazia. Retornando ao menu.[/yellow]")
        return

    provider = _embedding_provider()
    with console.status("[yellow]Buscando dispositivos constitucionais...[/yellow]"):
        try:
            with SessionLocal() as session:
                candidates = hybrid_search(
                    session,
                    query,
                    provider,
                    model_name=settings.embedding_model,
                    limit=5,
                    filters=RetrievalFilters(),
                )
        except Exception as exc:
            console.print(f"[bold red]Erro na pesquisa:[/bold red] {exc}")
            return

    if not candidates:
        console.print(
            "[yellow]Nenhum dispositivo relevante encontrado para o termo "
            "solicitado.[/yellow]"
        )
        return

    console.print("\n[green]Principais dispositivos encontrados:[/green]\n")
    for idx, item in enumerate(candidates, start=1):
        act_label = "CF/88" if item.legal_act == "CF/88" else "ADCT"
        header = (
            f"[bold cyan]{idx}. {act_label} • {item.element_type} "
            f"{item.number_label or ''}[/bold cyan]"
        )

        # Limita o texto do chunk
        text_preview = item.chunk_text.strip()
        if len(text_preview) > 300:
            text_preview = text_preview[:297] + "..."

        panel = Panel(
            Text(text_preview, style="white"),
            title=header,
            border_style="cyan",
            expand=False,
        )
        console.print(panel)
        console.print()


def show_base_status_screen() -> None:
    """Tela amigável mostrando o estado geral da base jurídica local."""
    console.print("\n[bold green]=== Estado da Base Jurídica ===[/bold green]")

    with SessionLocal() as session:
        try:
            status = materialization_status(session)
            active_versions = session.scalars(
                select(LegalVersion).where(LegalVersion.is_active_for_query.is_(True))
            ).all()
            active_version_ids = [v.id for v in active_versions]

            chunks_count = int(
                session.scalar(
                    select(func.count())
                    .select_from(Chunk)
                    .where(Chunk.legal_version_id.in_(active_version_ids))
                )
                or 0
            )
            embeddings_count = int(
                session.scalar(
                    select(func.count())
                    .select_from(Embedding)
                    .join(Chunk, Embedding.chunk_id == Chunk.id)
                    .where(
                        Chunk.legal_version_id.in_(active_version_ids),
                        Embedding.model_name == settings.embedding_model,
                    )
                )
                or 0
            )
        except Exception as exc:
            console.print(
                f"[bold red]Erro ao recuperar informações do banco:[/bold red] {exc}"
            )
            return

    table = Table(show_header=False, box=None)
    table.add_column("Item", style="bold cyan")
    table.add_column("Status", style="white")

    # Verifica se CF e ADCT estão prontas
    cf_status = (
        "[green]✓ Processada e materializada[/green]"
        if len(active_versions) == 2
        else "[yellow]Aguardando materialização[/yellow]"
    )

    table.add_row("Legislação Oficial", "Constituição Federal de 1988 e ADCT")
    table.add_row("Estado da CF/88 & ADCT", cf_status)
    table.add_row(
        "Dispositivos Mapeados",
        f"{status.get('legal_elements', 0)} elementos jurídicos",
    )
    table.add_row(
        "Parágrafos/Artigos (Provisões)",
        f"{status.get('legal_provisions', 0)} provisões",
    )
    table.add_row("Chunks de Busca (FTS)", f"{chunks_count} chunks de texto")
    table.add_row("Embeddings Vetoriais", f"{embeddings_count} vetores indexados")
    table.add_row(
        "Disponibilidade de Consulta",
        "[green]Sim[/green]"
        if len(active_versions) == 2 and chunks_count > 0
        else "[yellow]Não (Requer bootstrap)[/yellow]",
    )

    console.print(Panel(table, title="Resumo da Base Jurídica", border_style="green"))


def show_diagnostics_screen() -> None:
    """Exibe o diagnóstico detalhado e técnico dos componentes do sistema."""
    console.print("\n[bold green]=== Diagnóstico Técnico do Sistema ===[/bold green]")

    with console.status("[yellow]Rodando diagnósticos de infraestrutura...[/yellow]"):
        readiness = check_readiness()
        db_status = db_service.check_db_status()

    table = Table(title="Diagnóstico Geral", border_style="cyan")
    table.add_column("Componente", style="bold white")
    table.add_column("Indicador", style="bold")
    table.add_column("Descrição/Detalhes", style="dim")

    # Banco de dados
    db_indicator = (
        "[green]✓ Conectado[/green]"
        if readiness.database_connected
        else "[red]✗ Desconectado[/red]"
    )
    table.add_row(
        "PostgreSQL (pgvector)", db_indicator, f"URL: {db_status.get('database_url')}"
    )

    # Schema e migrations
    schema_indicator = (
        "[green]✓ Atualizado[/green]"
        if readiness.schema_ready
        else "[yellow]✗ Pendente[/yellow]"
    )
    table.add_row(
        "Schema Alembic",
        schema_indicator,
        f"Versão: {db_status.get('alembic_version') or 'Nenhuma'}",
    )

    # Ollama
    ollama_indicator = (
        "[green]✓ Online[/green]"
        if readiness.ollama_connected
        else "[red]✗ Offline[/red]"
    )
    table.add_row(
        "Ollama LLM Runtime",
        ollama_indicator,
        f"Conexão em: {settings.ollama_base_url}",
    )

    # Modelos
    llm_indicator = (
        "[green]✓ Pronto[/green]"
        if readiness.llm_model_ready
        else "[yellow]✗ Não instalado[/yellow]"
    )
    table.add_row(
        "Modelo de Chat (LLM)", llm_indicator, f"Nome: {settings.ollama_model}"
    )

    emb_indicator = (
        "[green]✓ Pronto[/green]"
        if readiness.embedding_model_ready
        else "[yellow]✗ Não instalado[/yellow]"
    )
    table.add_row(
        "Modelo de Embeddings", emb_indicator, f"Nome: {settings.embedding_model}"
    )

    # Base Jurídica
    ing_indicator = (
        "[green]✓ Sim[/green]"
        if readiness.source_ready
        else "[yellow]✗ Ausente[/yellow]"
    )
    table.add_row("Captura do Planalto", ing_indicator, "SourceDocument persistido")

    parse_indicator = (
        "[green]✓ Sim[/green]"
        if readiness.parsing_ready
        else "[yellow]✗ Ausente[/yellow]"
    )
    table.add_row("Materialização CF/ADCT", parse_indicator, "LegalVersions ativas")

    idx_indicator = (
        "[green]✓ Sim[/green]"
        if readiness.index_ready
        else "[yellow]✗ Incompleto[/yellow]"
    )
    table.add_row("Índice Gerado", idx_indicator, "Chunks alinhados a embeddings")

    console.print(table)


def show_about_screen() -> None:
    """Exibe informações sobre o projeto, escopo e isenção de responsabilidade."""
    console.print("\n[bold green]=== Sobre o Projeto ===[/bold green]")
    about_text = (
        "O [bold green]Consultor Jurídico[/bold green] é uma ferramenta "
        "experimental open-source voltada para consultas jurídicas fundamentadas "
        "na Constituição Federal de 1988 (CF/88) e no ADCT.\n\n"
        "[bold]Principais características:[/bold]\n"
        "- [cyan]Cadeia de Rastreabilidade:[/cyan] Todas as respostas geradas são "
        "ancoradas em evidências extraídas diretamente de fontes primárias "
        "oficiais (Planalto).\n"
        "- [cyan]Privacidade Local:[/cyan] O LLM e a geração de embeddings são "
        "processados localmente pelo Ollama + PostgreSQL.\n"
        "- [cyan]Validação Rígida:[/cyan] As claims geradas passam por validação "
        "de citação estrutural e suporte semântico.\n\n"
        "[bold yellow]AVISO IMPORTANTE E ISENÇÃO DE RESPONSABILIDADE:[/bold yellow]\n"
        "Esta aplicação possui fins estritamente informativos e didáticos. O "
        "sistema [underline]não substitui[/underline] o aconselhamento, parecer "
        "ou representação profissional de um advogado habilitado. As informações "
        "jurídicas fornecidas não constituem aconselhamento legal formal.\n"
    )
    console.print(Panel(about_text, border_style="cyan"))


def run_interactive_cli() -> None:
    """Ponto de entrada do loop da aplicação interativa."""
    show_banner()

    # Executa verificação e bootstrap se necessário
    if not handle_bootstrap():
        console.print(
            "\n[bold red]Não foi possível iniciar o Consultor Jurídico devido a "
            "falhas pendentes de inicialização.[/bold red]\n"
        )
        sys.exit(1)

    while True:
        console.print("\n[bold green]Menu Principal[/bold green]")
        console.print("  [bold cyan]1.[/bold cyan] Fazer consulta jurídica")
        console.print("  [bold cyan]2.[/bold cyan] Explorar / pesquisar a Constituição")
        console.print("  [bold cyan]3.[/bold cyan] Estado da base jurídica")
        console.print("  [bold cyan]4.[/bold cyan] Diagnóstico do sistema")
        console.print("  [bold cyan]5.[/bold cyan] Sobre o projeto")
        console.print("  [bold cyan]0.[/bold cyan] Sair")
        console.print()

        try:
            choice = Prompt.ask(
                "[bold]Escolha uma opção[/bold]",
                choices=["1", "2", "3", "4", "5", "0"],
                default="1",
            )

            if choice == "1":
                run_consultation_screen()
            elif choice == "2":
                run_exploration_screen()
            elif choice == "3":
                show_base_status_screen()
            elif choice == "4":
                show_diagnostics_screen()
            elif choice == "5":
                show_about_screen()
            elif choice == "0":
                console.print(
                    "\n[bold green]Saindo... Obrigado por usar o Consultor "
                    "Jurídico![/bold green]\n"
                )
                break

            if choice != "0":
                Prompt.ask(
                    "\n[dim]Pressione [Enter] para voltar ao menu[/dim]", default=""
                )

        except (KeyboardInterrupt, EOFError):
            console.print(
                "\n\n[bold green]Saindo... Obrigado por usar o Consultor "
                "Jurídico![/bold green]\n"
            )
            break
