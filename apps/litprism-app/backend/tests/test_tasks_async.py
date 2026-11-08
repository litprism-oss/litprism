"""tasks/_async.py — Celery tasks must not leak pooled connections across event loops."""

import ast
import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from tasks._async import run_async

TASKS_DIR = Path(__file__).resolve().parents[1] / "tasks"


class FakeEngine:
    def __init__(self) -> None:
        self.disposed_in_loops: list[asyncio.AbstractEventLoop] = []

    async def dispose(self) -> None:
        self.disposed_in_loops.append(asyncio.get_running_loop())


@pytest.fixture
def fake_engine():
    engine = FakeEngine()
    with patch("db.engine.engine", engine):
        yield engine


def test_returns_the_coroutines_result(fake_engine):
    async def work():
        return 42

    assert run_async(work()) == 42


def test_disposes_the_pool_after_success(fake_engine):
    async def work():
        return None

    run_async(work())
    assert len(fake_engine.disposed_in_loops) == 1


def test_disposes_the_pool_even_when_the_task_fails(fake_engine):
    async def work():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        run_async(work())
    assert len(fake_engine.disposed_in_loops) == 1


def test_disposes_inside_the_same_loop_the_task_ran_in(fake_engine):
    """Disposing after the loop closes would be too late: that is the bug."""
    seen = []

    async def work():
        seen.append(asyncio.get_running_loop())

    run_async(work())
    assert fake_engine.disposed_in_loops == seen


def test_every_task_gets_its_own_loop_and_its_own_dispose(fake_engine):
    async def work():
        return asyncio.get_running_loop()

    loops = [run_async(work()) for _ in range(3)]
    assert len({id(loop) for loop in loops}) == 3
    assert len(fake_engine.disposed_in_loops) == 3


def test_celery_task_bodies_dispose_the_pool(fake_engine):
    """The real tasks, not just the helper: one dispose per task call."""
    from tasks import screening

    async def fake_coordinator(screening_run_id: str) -> None:
        return None

    with patch.object(screening, "_run_coordinator", fake_coordinator):
        screening.screen_coordinator("run-1")
        screening.screen_coordinator("run-2")
    assert len(fake_engine.disposed_in_loops) == 2


def _asyncio_run_calls(path: Path) -> list[int]:
    tree = ast.parse(path.read_text())
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "asyncio"
    ]


def test_no_task_module_calls_asyncio_run_directly():
    """A bare asyncio.run() leaves pooled connections tied to a closed loop."""
    offenders = {
        path.name: lines
        for path in TASKS_DIR.glob("*.py")
        if path.name != "_async.py" and (lines := _asyncio_run_calls(path))
    }
    assert not offenders, f"use tasks._async.run_async instead: {offenders}"
