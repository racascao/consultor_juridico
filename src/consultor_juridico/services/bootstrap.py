"""Orquestração idempotente da preparação operacional do MVP2."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum


class BootstrapState(StrEnum):
    RUNNING = "RUNNING"
    READY = "READY"


@dataclass(frozen=True, slots=True)
class BootstrapReadiness:
    database: bool
    migrations: bool
    corpus: bool
    retrieval: bool
    ollama: bool
    model: bool

    @property
    def ready(self) -> bool:
        return all(
            (
                self.database,
                self.migrations,
                self.corpus,
                self.retrieval,
                self.ollama,
                self.model,
            )
        )


@dataclass(frozen=True, slots=True)
class BootstrapEvent:
    step: str
    state: BootstrapState
    message: str


class BootstrapFailure(RuntimeError):
    """Falha operacional que impede declarar o runtime como pronto."""


class BootstrapOrchestrator:
    """Coordena capacidades existentes sem incorporar regras de domínio."""

    def __init__(
        self,
        *,
        inspect: Callable[[], BootstrapReadiness],
        migrate: Callable[[], None],
        prepare_corpus: Callable[[], None],
        prepare_model: Callable[[], None],
    ) -> None:
        self._inspect = inspect
        self._migrate = migrate
        self._prepare_corpus = prepare_corpus
        self._prepare_model = prepare_model

    def run(self) -> Iterator[BootstrapEvent]:
        readiness = self._inspect()
        if readiness.ready:
            yield BootstrapEvent("system", BootstrapState.READY, "Já preparado")
            return
        if not readiness.database:
            raise BootstrapFailure("PostgreSQL indisponível")

        if not readiness.migrations:
            yield BootstrapEvent("migrations", BootstrapState.RUNNING, "Aplicando")
            try:
                self._migrate()
            except Exception as error:
                raise BootstrapFailure(f"Falha em migrations: {error}") from error
            readiness = self._inspect()
            if not readiness.migrations:
                raise BootstrapFailure("Migrations não ficaram prontas")
            yield BootstrapEvent("migrations", BootstrapState.READY, "Aplicadas")

        if not readiness.corpus or not readiness.retrieval:
            yield BootstrapEvent("corpus", BootstrapState.RUNNING, "Preparando")
            try:
                self._prepare_corpus()
            except Exception as error:
                raise BootstrapFailure(f"Falha ao preparar corpus: {error}") from error
            readiness = self._inspect()
            if not readiness.corpus or not readiness.retrieval:
                raise BootstrapFailure("Corpus materializado não passou na auditoria")
            yield BootstrapEvent("corpus", BootstrapState.READY, "Preparado")

        if not readiness.ollama:
            raise BootstrapFailure("Ollama indisponível")
        if not readiness.model:
            yield BootstrapEvent("model", BootstrapState.RUNNING, "Baixando")
            try:
                self._prepare_model()
            except Exception as error:
                raise BootstrapFailure(f"Falha ao preparar modelo: {error}") from error
            readiness = self._inspect()
            if not readiness.model:
                raise BootstrapFailure("Modelo congelado não ficou disponível")
            yield BootstrapEvent("model", BootstrapState.READY, "Disponível")

        yield BootstrapEvent("system", BootstrapState.RUNNING, "Validando")
        readiness = self._inspect()
        if not readiness.ready:
            raise BootstrapFailure("Runtime incompleto após bootstrap")
        yield BootstrapEvent("system", BootstrapState.READY, "Sistema pronto")
