"""Database session management."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from libs.core.config import get_settings


def get_async_engine():
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False, pool_size=5, max_overflow=10)


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_async_engine(), expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_async_session_factory()
    async with factory() as session:
        yield session


def get_sync_engine():
    settings = get_settings()
    return create_engine(settings.database_url_sync, echo=False, pool_size=5, max_overflow=10)


def get_sync_session_factory() -> sessionmaker[Session]:
    return sessionmaker(get_sync_engine(), expire_on_commit=False)


def get_sync_session() -> Session:
    factory = get_sync_session_factory()
    return factory()
