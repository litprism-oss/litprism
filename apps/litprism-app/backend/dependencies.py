from collections.abc import AsyncIterator

from config import Settings, settings
from db.engine import get_db as _get_db
from sqlalchemy.ext.asyncio import AsyncSession
from ws import ConnectionManager, ws_manager


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in _get_db():
        yield session


def get_settings() -> Settings:
    return settings


def get_ws_manager() -> ConnectionManager:
    return ws_manager
