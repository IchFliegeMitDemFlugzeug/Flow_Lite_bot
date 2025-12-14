"""
Низкоуровневые функции работы с базой данных и вспомогательный JSON-файл.

Здесь:
- создаётся engine и фабрика сессий SQLAlchemy для MySQL;
- есть контекстный менеджер get_session();
- остаются функции load_last_messages/save_last_messages для хранения
  last_bot_message_id в небольшом JSON-файле.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

import os

# ----------------------------------------------------------------------
# Настройки подключения к MySQL
# ----------------------------------------------------------------------

# Замените строку подключения на свою (логин/пароль/хост/порт/БД):

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

# Опциональная проверка, но очень полезна для отладки формата:
try:
    make_url(DATABASE_URL)
except Exception as exc:
    raise RuntimeError(f"Invalid DATABASE_URL value: {DATABASE_URL!r}") from exc

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


@contextmanager
def get_session() -> Iterator[Session]:
    """Context manager that yields a SQLAlchemy session."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """
    Optional helper to create tables from ORM models.

    В вашем случае таблицы создаются DDL-скриптом, поэтому обычно не нужен.
    """
    Base.metadata.create_all(bind=engine)