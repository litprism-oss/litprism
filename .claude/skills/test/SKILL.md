---
name: test
description: Run, write and strengthen tests for the LitPrism monorepo — backend pytest (unit, API, in-process end-to-end Celery flow), package tests, real-API integration tests, and frontend type/lint checks. Use this whenever the user asks to test, verify, "make sure it works", add coverage, write an e2e or integration test, check a fix, or says they can't test manually right now, and before declaring any change done.
---

# Test LitPrism

Pick the lightest layer that proves the change, then go one layer up if the change
crosses a boundary (route → Celery task → DB).

## Layers and commands

| What | Where | Command |
|------|-------|---------|
| Backend unit + API | `apps/litprism-app/backend/tests/` | `cd apps/litprism-app/backend && uv run pytest tests/ -q` |
| One backend file | same | `uv run pytest tests/test_screening_run.py -q` |
| Screening flow end-to-end | `tests/test_e2e_screening_flow.py` | `uv run pytest tests/test_e2e_screening_flow.py -q` |
| A package | `packages/<pkg>/tests/` | `uv run pytest packages/<pkg>/tests/ -v` (from repo root) |
| Real-API integration | `tests/integration/` | `uv run pytest tests/integration -m integration -v` — needs network + keys in `apps/litprism-app/.env`; ask before running, it spends API quota |
| Frontend types | `apps/litprism-app/frontend` | `npm run build` (runs `tsc -b`) |
| Frontend lint | same | `npx eslint <file>` |

Two traps:
- `npx tsc --noEmit -p .` in the frontend checks **nothing** — the root tsconfig only has
  project references. Use `npm run build` (or `npx tsc -b`).
- `pytest` deselects `integration` by default (`addopts` in root `pyproject.toml`), so
  "N deselected" in the summary is expected.

## Backend test conventions

- In-memory SQLite (`sqlite+aiosqlite:///:memory:` + `StaticPool`); `conftest.py`
  provides `db`, `client`, `project_id`, `criteria_id`, `articles_with_decisions`, …
- Never hit real services in unit tests: `mock_coordinator` patches
  `screen_coordinator.delay`; patch `Screener.from_env` for LLM calls; source clients
  with `AsyncMock`.
- `asyncio_mode = "auto"` — plain `async def test_…`, no decorator.
- Lint test files like any other Python file (`ruff check` + `ruff format`).

## The end-to-end harness

`tests/test_e2e_screening_flow.py` runs the **real** routes and **real** Celery task
bodies in-process. Only the edges are faked:
- `FakeScreener` — decision from markers: title `INC`/`EXC`/`UNC` at abstract stage,
  `FT-INC`/`FT-EXC` in full text at full-text stage, `BLOCK` → content-policy error
- `.delay()` calls go into `Harness.queue`; `await h.step()` runs one, `await h.drain()` runs all
- `FakeLock` replaces the Redis coordinator lock

Reach for it when a change touches dispatch, resume/pause, completion, idempotency,
full-text eligibility or PRISMA counts. Use `h.step()` to stop mid-run (e.g. pause after
the first chunk) and simulate other workers by writing rows through `h.factory()`.

## Prove the test can fail

A test that passes on the first run hasn't shown it tests anything. For each fix, break
the fix on purpose, run the test, confirm it fails, then restore:

```bash
# edit the fixed line back to the buggy version, then
uv run pytest tests/test_e2e_screening_flow.py -q   # expect a FAILED line
git checkout -- <file>                              # restore (file must be committed or stashed first)
```

If the mutation survives, the test isn't reaching that code path — rewrite it, don't
add more assertions to the same path.

## Reporting

Report the exact pass/fail counts from the run you just did, what's faked vs real, and
what is **not** covered (real Celery worker/Redis/LLM, frontend UI behaviour). Don't
call something verified unless a command you ran checked it.
