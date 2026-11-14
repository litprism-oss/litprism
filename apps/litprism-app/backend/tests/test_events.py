"""services/events.py — worker-side progress events. Best effort, never raises."""

import json

import pytest
from services import events
from services.events import (
    CHANNEL,
    complete_event,
)
from services.events import progress_events as build_progress_events
from services.events import (
    publish_events as real_publish_events,  # conftest patches the module attr
)


class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.queued = []

    def publish(self, channel, payload):
        self.queued.append((channel, payload))

    def execute(self):
        if self.client.fail:
            raise ConnectionError("redis is down")
        self.client.published.extend(self.queued)
        self.client.executions += 1


class FakeRedis:
    def __init__(self, fail=False):
        self.fail = fail
        self.published = []
        self.executions = 0
        self.pipelines = 0

    def pipeline(self, transaction=True):
        self.pipelines += 1
        assert transaction is False  # nothing here needs a transaction
        return FakePipeline(self)


@pytest.fixture
def redis_client(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(events, "_get_client", lambda: client)
    monkeypatch.setattr(events, "_paused_until", 0.0)
    return client


# --- building events -----------------------------------------------------------------------


def test_progress_events_number_articles_from_where_the_run_was():
    out = build_progress_events(
        processed_before=10,
        total=50,
        decisions=[("a1", "include", 0.9), ("a2", "exclude", 0.8)],
        errors=[],
    )
    assert out == [
        {
            "event": "screening_progress",
            "article_id": "a1",
            "decision": "include",
            "confidence": 0.9,
            "processed": 11,
            "total": 50,
        },
        {
            "event": "screening_progress",
            "article_id": "a2",
            "decision": "exclude",
            "confidence": 0.8,
            "processed": 12,
            "total": 50,
        },
    ]


def test_errors_advance_the_count_and_get_their_own_event():
    out = build_progress_events(
        processed_before=0,
        total=3,
        decisions=[("a1", "include", 1.0)],
        errors=[("a2", "RateLimitError")],
    )
    assert [e["event"] for e in out] == [
        "screening_progress",
        "screening_progress",
        "screening_error",
    ]
    assert out[1]["decision"] == "error" and out[1]["processed"] == 2
    assert out[2] == {
        "event": "screening_error",
        "article_id": "a2",
        "message": "Screening failed (RateLimitError)",
    }


def test_progress_events_for_nothing_is_empty():
    assert build_progress_events(processed_before=0, total=0, decisions=[], errors=[]) == []


def test_complete_event_counts_only_known_decisions():
    done = complete_event(
        total_processed=7, counts={"include": 3, "exclude": 2, "uncertain": 1, "error": 1}
    )
    assert done == {
        "event": "screening_complete",
        "total_processed": 7,
        "included": 3,
        "excluded": 2,
        "uncertain": 1,
    }
    assert complete_event(total_processed=0, counts={})["included"] == 0


# --- publishing ----------------------------------------------------------------------------


def test_events_go_to_the_shared_channel_with_their_project_in_one_round_trip(redis_client):
    batch = [{"event": "screening_progress", "processed": 1}, {"event": "screening_complete"}]
    real_publish_events("proj-1", batch)

    assert redis_client.executions == 1  # one pipeline, however many events
    assert [channel for channel, _ in redis_client.published] == [CHANNEL, CHANNEL]
    decoded = [json.loads(payload) for _, payload in redis_client.published]
    assert decoded == [{"project_id": "proj-1", "event": e} for e in batch]


def test_nothing_to_publish_does_not_touch_redis(redis_client):
    real_publish_events("proj-1", [])
    assert redis_client.pipelines == 0


def test_a_redis_failure_never_reaches_the_caller(redis_client):
    redis_client.fail = True
    real_publish_events("proj-1", [{"event": "screening_progress"}])  # must not raise


def test_after_a_failure_publishing_pauses_instead_of_retrying_every_event(
    redis_client, monkeypatch
):
    now = [1000.0]
    monkeypatch.setattr(events.time, "monotonic", lambda: now[0])
    redis_client.fail = True
    real_publish_events("p", [{"event": "x"}])
    assert redis_client.pipelines == 1

    real_publish_events("p", [{"event": "x"}])  # still paused: no connection attempt
    now[0] += 10
    real_publish_events("p", [{"event": "x"}])
    assert redis_client.pipelines == 1


def test_publishing_resumes_after_the_pause(redis_client, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(events.time, "monotonic", lambda: now[0])
    redis_client.fail = True
    real_publish_events("p", [{"event": "x"}])
    redis_client.fail = False
    now[0] += events._PAUSE_AFTER_FAILURE_SECONDS + 1

    real_publish_events("p", [{"event": "x"}])
    assert redis_client.executions == 1
