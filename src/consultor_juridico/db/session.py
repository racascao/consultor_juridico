"""Gerenciamento de conexões e sessões do SQLAlchemy."""

import socket
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from consultor_juridico.config import settings


def get_database_url() -> str:
    """Retorna a URL formatada para conexão com o banco de dados.

    Ajusta a porta para 5433 se a aplicação estiver rodando fora do container Docker
    e o host 'db' não for resolvível localmente.
    """
    url = settings.database_url
    if "db:5432" in url:
        try:
            socket.gethostbyname("db")
        except socket.gaierror:
            url = url.replace("db:5432", "localhost:5433")
    return url


engine = create_engine(get_database_url(), echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def set_verbose(verbose: bool) -> None:
    """Habilita/desabilita echo SQL apenas em modo verbose."""
    engine.echo = verbose


def get_db() -> Generator[Session]:
    """Gerador de sessão do SQLAlchemy para ser utilizado como dependência."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
