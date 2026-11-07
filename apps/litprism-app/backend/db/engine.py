import uuid
from collections.abc import AsyncIterator
from typing import Any

from config import settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _engine_kwargs(url: str) -> dict[str, Any]:
    """Postgres via a transaction pooler (Supabase :6543, PgBouncer) cannot reuse
    prepared statements across connections, so disable asyncpg's statement cache
    and give each prepared statement a unique name."""
    if not url.startswith("postgresql+asyncpg://"):
        return {}
    return {
        "pool_pre_ping": True,
        "connect_args": {
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
        },
    }


engine = create_async_engine(
    settings.database_url, echo=settings.debug, **_engine_kwargs(settings.database_url)
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
