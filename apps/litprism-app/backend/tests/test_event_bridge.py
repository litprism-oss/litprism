"""services/event_bridge.py + ws.py — API-side delivery of worker progress to sockets."""

import asyncio
import json

import pytest
from services.event_bridge import forward, run_bridge
from services.events import CHANNEL
from ws import ConnectionManager


class FakeSocket:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    async def send_json(self, message):
        if self.fail:
            raise RuntimeError("socket closed")
        self.sent.append(message)


def message(project_id="p1", **event):
    return json.dumps({"project_id": project_id, "event": event or {"event": "screening_progress"}})


# --- ConnectionManager ---------------------------------------------------------------------


async def test_broadcast_reaches_only_that_projects_sockets():
    manager, mine, other = ConnectionManager(), FakeSocket(), FakeSocket()
    manager.register("p1", mine)
    manager.register("p2", other)
    await manager.broadcast("p1", {"event": "x"})
    assert mine.sent == [{"event": "x"}] and other.sent == []


async def test_a_dead_socket_is_dropped_and_the_others_still_get_the_message():
    manager, dead, alive = ConnectionManager(), FakeSocket(fail=True), FakeSocket()
    manager.register("p1", dead)
    manager.register("p1", alive)

    await manager.broadcast("p1", {"event": "x"})  # must not raise

    assert alive.sent == [{"event": "x"}]
    assert manager.has_connections("p1")
    await manager.broadcast("p1", {"event": "y"})
    assert alive.sent == [{"event": "x"}, {"event": "y"}]
    manager.disconnect("p1", alive)
    assert not manager.has_connections("p1")


async def test_broadcast_to_a_project_nobody_watches_is_a_no_op():
    await ConnectionManager().broadcast("nobody", {"event": "x"})


# --- forward -------------------------------------------------------------------------------


async def test_forward_delivers_the_event_to_its_project():
    manager, sock = ConnectionManager(), FakeSocket()
    manager.register("p1", sock)
    await forward(message("p1", event="screening_complete", included=3), manager)
    assert sock.sent == [{"event": "screening_complete", "included": 3}]


async def test_forward_accepts_bytes_as_redis_returns_them():
    manager, sock = ConnectionManager(), FakeSocket()
    manager.register("p1", sock)
    await forward(message("p1").encode(), manager)
    assert len(sock.sent) == 1


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "",
        "[]",
        "null",
        "{}",
        json.dumps({"project_id": "p1"}),
        json.dumps({"event": {"event": "x"}}),
        json.dumps({"project_id": 7, "event": {"event": "x"}}),
        json.dumps({"project_id": "p1", "event": "a string"}),
        json.dumps({"project_id": "p1", "event": ["list"]}),
    ],
)
async def test_forward_ignores_anything_malformed(raw):
    manager, sock = ConnectionManager(), FakeSocket()
    manager.register("p1", sock)
    await forward(raw, manager)  # must not raise
    assert sock.sent == []


# --- run_bridge ----------------------------------------------------------------------------


class FakePubSub:
    def __init__(self, items, then_hang=True, subscribe_error=None):
        self.items = items
        self.then_hang = then_hang
        self.subscribe_error = subscribe_error
        self.subscribed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def subscribe(self, channel):
        if self.subscribe_error:
            raise self.subscribe_error
        self.subscribed.append(channel)

    async def listen(self):
        for item in self.items:
            yield item
        if self.then_hang:
            await asyncio.Event().wait()


class FakeClient:
    def __init__(self, pubsub):
        self._pubsub = pubsub
        self.closed = False

    def pubsub(self):
        return self._pubsub

    async def aclose(self):
        self.closed = True


async def run_until(condition, bridge_task, timeout=2.0):
    for _ in range(int(timeout / 0.01)):
        if condition():
            break
        await asyncio.sleep(0.01)
    bridge_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await bridge_task


async def test_the_bridge_subscribes_and_forwards_only_real_messages():
    manager, sock = ConnectionManager(), FakeSocket()
    manager.register("p1", sock)
    pubsub = FakePubSub(
        [
            {"type": "subscribe", "data": 1},  # the confirmation Redis sends first
            {"type": "message", "data": message("p1", event="screening_progress", processed=1)},
            {"type": "pong", "data": None},
            {"type": "message", "data": message("p1", event="screening_complete")},
        ]
    )
    client = FakeClient(pubsub)
    task = asyncio.create_task(run_bridge(manager, "redis://x", client_factory=lambda: client))
    await run_until(lambda: len(sock.sent) == 2, task)

    assert pubsub.subscribed == [CHANNEL]
    assert [e["event"] for e in sock.sent] == ["screening_progress", "screening_complete"]
    assert client.closed  # cleaned up on cancellation


async def test_the_bridge_reconnects_with_a_growing_pause_after_failures():
    manager, sock = ConnectionManager(), FakeSocket()
    manager.register("p1", sock)
    attempts, pauses = [], []

    def factory():
        attempts.append(1)
        if len(attempts) <= 3:
            return FakeClient(FakePubSub([], subscribe_error=ConnectionError("down")))
        return FakeClient(FakePubSub([{"type": "message", "data": message("p1")}]))

    async def fake_sleep(seconds):
        pauses.append(seconds)

    task = asyncio.create_task(
        run_bridge(manager, "redis://x", client_factory=factory, sleep=fake_sleep)
    )
    await run_until(lambda: len(sock.sent) == 1, task)

    assert len(attempts) == 4
    assert pauses == [1, 2, 5]  # grows, and the message still arrives once Redis is back


async def test_the_pause_is_capped_and_resets_after_a_good_connection():
    manager = ConnectionManager()
    calls, pauses = [], []

    def factory():
        calls.append(1)
        # fail 8 times, connect once (then drop at once), fail again
        if len(calls) == 9:
            return FakeClient(FakePubSub([], then_hang=False))
        return FakeClient(FakePubSub([], subscribe_error=ConnectionError("down")))

    async def fake_sleep(seconds):
        pauses.append(seconds)
        if len(pauses) >= 11:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await run_bridge(manager, "redis://x", client_factory=factory, sleep=fake_sleep)

    assert max(pauses) == 30  # never longer than half a minute
    assert pauses[:8] == [1, 2, 5, 10, 30, 30, 30, 30]
    assert pauses[8] == 1  # a successful subscribe starts the schedule over


async def test_a_failure_while_forwarding_does_not_kill_the_bridge():
    manager = ConnectionManager()
    sock = FakeSocket(fail=True)
    manager.register("p1", sock)  # broadcast swallows this, but the loop must survive anyway
    pubsub = FakePubSub([{"type": "message", "data": message("p1")}] * 3)
    task = asyncio.create_task(
        run_bridge(manager, "redis://x", client_factory=lambda: FakeClient(pubsub))
    )
    await run_until(lambda: not manager.has_connections("p1"), task)


# --- the app starts and stops the bridge ---------------------------------------------------


class FakeEngine:
    def __init__(self):
        self.disposed = False

    def begin(self):
        engine = self

        class _Conn:
            async def __aenter__(self):
                return engine

            async def __aexit__(self, *exc):
                return False

        return _Conn()

    async def run_sync(self, fn):
        return None

    async def dispose(self):
        self.disposed = True


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def test_the_app_runs_the_bridge_for_its_whole_lifetime(monkeypatch):
    import main

    state = {"started": False, "cancelled": False, "args": None}

    async def fake_bridge(manager, url, **kwargs):
        state["started"], state["args"] = True, (manager, url)
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            state["cancelled"] = True
            raise

    async def no_seed(db):
        return None

    engine = FakeEngine()
    monkeypatch.setattr(main, "run_bridge", fake_bridge)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "AsyncSessionLocal", FakeSession)
    monkeypatch.setattr(main, "seed_datasets", no_seed)
    monkeypatch.setattr(main, "check_auth_config", lambda: None)

    async with main.lifespan(main.app):
        await asyncio.sleep(0.01)
        assert state["started"] and not state["cancelled"]  # running while the app serves
        assert state["args"] == (main.ws_manager, main.settings.celery_broker_url)

    assert state["cancelled"]  # stopped at shutdown, not left running
    assert engine.disposed


async def test_a_failing_startup_check_never_leaves_a_bridge_behind(monkeypatch):
    import main

    started = []

    async def fake_bridge(manager, url, **kwargs):
        started.append(1)
        await asyncio.Event().wait()

    def refuse():
        raise RuntimeError("auth not configured")

    monkeypatch.setattr(main, "run_bridge", fake_bridge)
    monkeypatch.setattr(main, "check_auth_config", refuse)

    with pytest.raises(RuntimeError, match="auth not configured"):
        async with main.lifespan(main.app):
            pass
    assert started == []
