from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from agent.db import models as _models  # noqa: F401
from agent.settings import AppSettings, get_settings


def database_path(settings: AppSettings | None = None) -> str:
    return (settings or get_settings()).database_path


def database_url(settings: AppSettings | None = None) -> str:
    path = database_path(settings)
    if path == ":memory:":
        return "sqlite://"
    resolved_path = str(Path(path).expanduser())
    Path(resolved_path).parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{resolved_path}"


@lru_cache(maxsize=16)
def _engine_for_url(url: str) -> Engine:
    connect_args = {"check_same_thread": False}
    engine_kwargs: dict[str, Any] = {"connect_args": connect_args}
    if url == "sqlite://":
        engine_kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **engine_kwargs)

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection: object, _connection_record: object) -> None:
        cursor = cast(Any, dbapi_connection).cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        if url != "sqlite://":
            cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    return engine


def get_engine(settings: AppSettings | None = None) -> Engine:
    return _engine_for_url(database_url(settings))


@contextmanager
def db_session(settings: AppSettings | None = None) -> Iterator[Session]:
    with Session(get_engine(settings), expire_on_commit=False) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
