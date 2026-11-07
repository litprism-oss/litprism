---
name: implement
description: Implement a LitPrism build session, feature or fix end to end — read the session spec, branch from dev, write code that follows the app's fixed architecture, add tests, lint as you go, and leave a ready-to-commit change. Use this whenever the user says "start session N", "implement X", "build the next session", "fix this bug", "next" after a status check, or points at a docs/litprism-session*.md or docs/litprism-fix-*.md file, even if they don't say "implement".
---

# Implement a LitPrism change

LitPrism is built in numbered sessions. Each has a spec in `docs/` and a row in the
CLAUDE.md status tables. The spec says *what*; CLAUDE.md says *how* (architecture
rules that must not change). Your job is to turn the spec into a working, tested
change on its own branch.

## 1. Orient before writing code

1. Read the CLAUDE.md "Build status" tables to find the session (the `⏳ Next` row
   unless the user names one) and its spec + branch in "Session specs".
2. Read **only that session's** doc. Older session docs describe superseded states and
   will mislead you.
3. Check the spec's assumptions against the code. Specs are written ahead of time and
   sometimes claim "no changes needed" for things that were never built (e.g. Session
   15 assumed `GET /prisma-counts` existed; it didn't). Quick checks that catch this:
   - every URL the frontend calls in `src/lib/api.ts` has a backend route
     (`grep -rn '@router' apps/litprism-app/backend/api`)
   - every field in `src/lib/types.ts` you touch matches the Pydantic model in
     `api/schemas.py` exactly (drift here breaks `npm run build`)
4. Summarise the plan to the user in a few lines (files to touch, new endpoints,
   migrations, tests) before the first edit, and call out any spec gap you found.

## 2. Branch

```bash
git checkout dev && git pull origin dev
git checkout -b <branch from the spec table>   # feat/<name> or fix/<name>
```

## 3. Write the code

Follow the "Key architecture decisions" in CLAUDE.md — they are load-bearing:
async SQLAlchemy everywhere, all schemas in `api/schemas.py`, all models in
`db/models.py` (new columns via Alembic migration), UUID string PKs, Celery only for
long-running work, `ReviewType` from `enums.py`, frontend API calls only through
`src/lib/api.ts`, types only in `src/lib/types.ts`, one hook file per resource.

Backend habits that matter here:
- After **every** Python file edit: `uv run ruff check <file> && uv run ruff format <file>`
  (run from `apps/litprism-app/backend`). Fixing as you go is much cheaper than a
  batch of violations at the end.
- Celery tasks import inside the function body and open their own
  `AsyncSessionLocal()` — keep that pattern so tests can patch `db.engine.AsyncSessionLocal`.
- A task that can be re-dispatched (retries, resume, watchdog) must be idempotent:
  check for existing `ScreeningResult` rows before writing, and make sure every early
  `return` still lets the run reach `completed`.
- Schema change → `uv run alembic revision --autogenerate -m "<what>"`, then read the
  generated file; autogenerate misses renames and server defaults.
- New setting in `config.py` that production needs → also wire it into the Azure deploy
  (workflow `env:`, `azure/deploy.sh`, `DEPLOY.md`). The `release` skill lists the steps.
- Don't rely on in-process state shared across requests beyond what's there now
  (WebSocket `ConnectionManager`), or on local disk. Production runs one API replica
  and one worker, as separate containers with no shared volume. Anything the worker
  needs has to be in the DB or Redis.

Frontend habits:
- Work one file at a time and tell the user what changed (CLAUDE.md asks for this).
- Mirror backend schemas field-for-field in `types.ts`.
- Surface mutation errors (`toast.error(err.message)` via `sonner`) — `api.ts` already
  turns the backend `detail` into the error message.

## 4. Test it

Use the `test` skill. At minimum: unit tests for new services/routes, and if you
touched the screening pipeline, extend `tests/test_e2e_screening_flow.py`.

## 5. Finish

1. Run the full checks from the `build` skill (backend tests, ruff on changed files,
   `npm run build`).
2. Update the session's row in CLAUDE.md (`⏳ Next` → `✅ Complete — on <branch>, pending merge`)
   and the API surface list if you added routes. CLAUDE.md is gitignored, so this is a
   local note, not part of the commit.
3. Write a commit message in the repo's format (see CLAUDE.md "Commit format"), e.g.
   `feat(app-backend): Session 16 — <summary>`. No `Co-Authored-By` trailer.
4. Stage specific files only (never `git add -A` / `git add .`). Commit, push or merge
   only when the user has asked for it in this session — otherwise hand them the
   message and the file list. For opening the PR, use the `release` skill.
