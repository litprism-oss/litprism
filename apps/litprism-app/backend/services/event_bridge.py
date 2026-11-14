"""API side of the progress-event bridge (see services/events.py for the worker side).

Subscribes to the Redis channel the workers publish to and forwards each event to the
WebSocket connections of its project. Runs for the lifetime of the API process and
reconnects on its own: if Redis is down the API keeps serving, only live progress pauses.
"""

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis
from ws import ConnectionManager

from services.events import CHANNEL

logger = logging.getLogger(__name__)

_RECONNECT_DELAYS_SECONDS = (1, 2, 5, 10, 30)


async def forward(raw: str | bytes, manager: ConnectionManager) -> None:
    """Deliver one published message to its project's sockets. Ignores anything malformed."""
    try:
        message = json.loads(raw)
        project_id, event = message["project_id"], message["event"]
    except (ValueError, KeyError, TypeError):
        logger.debug("Ignoring a malformed progress message")
        return
    if isinstance(project_id, str) and isinstance(event, dict):
        await manager.broadcast(project_id, event)


async def run_bridge(
    manager: ConnectionManager,
    redis_url: str,
    *,
    client_factory: Callable[[], Any] | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Forward events until cancelled, reconnecting with a growing pause after any failure."""
    make_client = client_factory or (lambda: aioredis.Redis.from_url(redis_url))
    failures = 0
    while True:
        client = None
        try:
            client = make_client()
            async with client.pubsub() as pubsub:
                await pubsub.subscribe(CHANNEL)
                failures = 0
                async for item in pubsub.listen():
                    if item.get("type") == "message":
                        await forward(item["data"], manager)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - keep the bridge alive whatever Redis does
            delay = _RECONNECT_DELAYS_SECONDS[min(failures, len(_RECONNECT_DELAYS_SECONDS) - 1)]
            failures += 1
            logger.warning(
                "Progress bridge lost Redis (%s); retrying in %ss", type(exc).__name__, delay
            )
            await sleep(delay)
        finally:
            if client is not None:
                with contextlib.suppress(Exception):  # closing is best effort
                    await client.aclose()
