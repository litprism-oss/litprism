"""Progress events from Celery workers to the browsers watching a project.

WebSocket connections live in the API process, but screening runs in a worker: a different
process, possibly on another machine. So the worker publishes to a Redis pub/sub channel and
the API forwards each event to that project's sockets (services/event_bridge.py).

Publishing is best effort. Progress is a nicety: the run itself, and the polled status the UI
falls back on, never depend on it, so a Redis problem must not fail or slow a screening run.
"""

import json
import logging
import time
from typing import Any

import redis
from config import settings

logger = logging.getLogger(__name__)

CHANNEL = "litprism:events"

# After a failed publish, stop trying for a while instead of paying a connect timeout per event.
_PAUSE_AFTER_FAILURE_SECONDS = 30.0
_SOCKET_TIMEOUT_SECONDS = 1.0

_client: redis.Redis | None = None
_paused_until = 0.0


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            settings.celery_broker_url,
            socket_timeout=_SOCKET_TIMEOUT_SECONDS,
            socket_connect_timeout=_SOCKET_TIMEOUT_SECONDS,
        )
    return _client


def publish_events(project_id: str, events: list[dict[str, Any]]) -> None:
    """Publish events for one project in a single round trip. Never raises."""
    global _paused_until
    if not events or time.monotonic() < _paused_until:
        return
    try:
        pipe = _get_client().pipeline(transaction=False)
        for event in events:
            pipe.publish(CHANNEL, json.dumps({"project_id": project_id, "event": event}))
        pipe.execute()
    except Exception as exc:  # noqa: BLE001 - progress reporting must never break a run
        _paused_until = time.monotonic() + _PAUSE_AFTER_FAILURE_SECONDS
        logger.warning(
            "Could not publish progress events (%s); pausing for %.0fs",
            type(exc).__name__,
            _PAUSE_AFTER_FAILURE_SECONDS,
        )


def progress_events(
    *,
    processed_before: int,
    total: int,
    decisions: list[tuple[str, str, float]],
    errors: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Events for one finished chunk, in the shapes the frontend already understands
    (see ScreeningProgressEvent in frontend/src/lib/types.ts).

    `decisions` is (article_id, decision, confidence) and `errors` is (article_id, reason).
    Every article advances `processed`, errors included, because the run's own counter counts
    them too; an error also gets a `screening_error` event so the page can refresh.
    The reason is a short error class name: provider messages are not sent to browsers.
    """
    events: list[dict[str, Any]] = []
    processed = processed_before
    for article_id, decision, confidence in decisions:
        processed += 1
        events.append(
            {
                "event": "screening_progress",
                "article_id": article_id,
                "decision": decision,
                "confidence": confidence,
                "processed": processed,
                "total": total,
            }
        )
    for article_id, reason in errors:
        processed += 1
        events.append(
            {
                "event": "screening_progress",
                "article_id": article_id,
                "decision": "error",
                "confidence": 0.0,
                "processed": processed,
                "total": total,
            }
        )
        events.append(
            {
                "event": "screening_error",
                "article_id": article_id,
                "message": f"Screening failed ({reason})",
            }
        )
    return events


def complete_event(*, total_processed: int, counts: dict[str, int]) -> dict[str, Any]:
    return {
        "event": "screening_complete",
        "total_processed": total_processed,
        "included": counts.get("include", 0),
        "excluded": counts.get("exclude", 0),
        "uncertain": counts.get("uncertain", 0),
    }
