"""Run a coroutine from a synchronous Celery task.

Every `asyncio.run()` creates a new event loop and closes it afterwards, but the shared
SQLAlchemy engine keeps its pooled asyncpg connections, which belong to the loop that
opened them. The next task in the same worker process then reuses one of them and fails with
"RuntimeError: Event loop is closed" / "attached to a different loop". Disposing the pool
inside the loop, before it closes, means each task starts with fresh connections.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    async def _runner() -> T:
        from db import engine as db_engine  # looked up at call time so tests can patch it

        try:
            return await coro
        finally:
            await db_engine.engine.dispose()

    return asyncio.run(_runner())
