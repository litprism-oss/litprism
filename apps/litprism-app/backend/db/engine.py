import uuid
from collections.abc import AsyncIterator
from typing import Any

from config import settings
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _engine_kwargs(url: str) -> dict[str, Any]:
    """Postgres via a transaction pooler (Supabase :6543, PgBouncer) cannot reuse
    prepared statements across connections. Two separate caches must be switched off:
    asyncpg's own (statement_cache_size) and SQLAlchemy's asyncpg dialect's
    (prepared_statement_cache_size, default 100). With only the first off, a statement
    prepared on one pooled connection is replayed on another and Postgres answers
    'prepared statement ... does not exist' (a 500 on roughly 40% of requests under load).
    Each statement also gets a unique name so concurrent ones can't collide."""
    if not url.startswith("postgresql+asyncpg://"):
        return {}
    return {
        "pool_pre_ping": True,
        "connect_args": {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
        },
    }


engine = create_async_engine(
    settings.database_url, echo=settings.debug, **_engine_kwargs(settings.database_url)
)
if settings.database_url.startswith("sqlite"):
    # SQLite ignores foreign keys (and so ON DELETE CASCADE) unless asked; Postgres always
    # enforces them. Keeps local dev behaving like production.
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_fk_pragma(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
