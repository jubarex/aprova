"""Engine SQLite: WAL, foreign_keys=ON em cada conexão, busy_timeout=5000 (v2 §4.3)."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings
from . import flow_models  # noqa: F401  (registra as tabelas)
from .models import Base


def make_engine(settings: Settings) -> Engine:
    if settings.database_url.startswith("sqlite:///"):
        Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    settings.attachment_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        settings.database_url, connect_args={"check_same_thread": False}, future=True
    )

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _):
        # isolation_level=None desliga o BEGIN implícito do driver; a transação é do SQLAlchemy
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    return engine


def init_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False, future=True)


@contextmanager
def tx(factory: sessionmaker[Session]):
    """Transação curta explícita: commit no sucesso, rollback na exceção."""
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
