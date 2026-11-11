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
- Auth: every route needs a user. The `client` fixture is signed in as the member
  `test-user`; `other_client` (a second member) and `guest_client` (anonymous) share the
  same app, switched by an `X-Test-User` header. Tests of real token checking use
  `raw_client` in `tests/test_auth.py` (HS256 test secret). A custom app fixture (like the
  e2e `harness`) must request `seed_test_users` and call it with its session.
- Never hit real services in unit tests: `mock_coordinator` patches
  `screen_coordinator.delay`; patch `Screener.from_env` for LLM calls; source clients
  with `AsyncMock`.
- `asyncio_mode = "auto"` — plain `async def test_…`, no decorator.
- Lint test files like any other Python file (`ruff check` + `ruff format`).

## What SQLite hides (production is Postgres)

Green tests have twice passed code that failed on Azure. Two rules came out of it:
- The test databases enforce foreign keys (`enforce_foreign_keys` in `tests/conftest.py`, and
  the same pragma in the e2e harness). Keep it on. Write parents before children; when several
  mapped objects reference each other in one flush, `await db.flush()` between them, because
  SQLAlchemy doesn't order inserts by foreign key unless a `relationship()` says so.
- Async engines are tied to the event loop that opened them. Celery tasks go through
  `tasks/_async.py::run_async`, never a bare `asyncio.run` (an `ast` test enforces it).

When a change touches the database layer, connections, bulk inserts or migrations, also run it
against real Postgres. Docker is available:
```bash
docker run -d --rm --name lp-pg -p 55432:5432 -e POSTGRES_PASSWORD=pw postgres:16-alpine
DATABASE_URL=postgresql://postgres:pw@localhost:55432/postgres uv run alembic upgrade head
```
Supabase's pooler does not support prepared statements in transaction mode, so to reproduce
pooler bugs put PgBouncer in front with `POOL_MODE=transaction MAX_PREPARED_STATEMENTS=0`
(image `edoburu/pgbouncer`, both containers on one `docker network`). PgBouncer's default
supports prepared statements and **hides** the bug.

Shell gotcha: don't name a zsh loop variable `path`; it is tied to `PATH`.

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
