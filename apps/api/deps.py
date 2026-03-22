"""FastAPI dependency injection."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from libs.db.session import get_async_session, get_sync_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        yield session


def get_sync_db() -> Session:
    return get_sync_session()
