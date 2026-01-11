"""
Низкоуровневые функции работы с базой данных и вспомогательный JSON-файл.

Здесь:
- создаётся engine и фабрика сессий SQLAlchemy для MySQL;
- есть контекстный менеджер get_session();
- остаются функции load_last_messages/save_last_messages для хранения
  last_bot_message_id в небольшом JSON-файле.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .models import Base

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

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)

@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Context manager that yields a SQLAlchemy session."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    Optional helper to create tables from ORM models.

    В вашем случае таблицы создаются DDL-скриптом, поэтому обычно не нужен.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)