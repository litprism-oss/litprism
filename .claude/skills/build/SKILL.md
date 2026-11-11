---
name: build
description: Build, lint and run the LitPrism stack locally — frontend production build, Python package wheels, backend import/migration checks, and starting the full dev stack (API, Celery worker + beat, Redis, Vite) with overmind. Use this whenever the user asks to build, compile, lint, "check everything", run the CI checks locally, start/run the app or worker, apply migrations, or before opening a PR.
---

# Build and run LitPrism

## Pre-PR check (what CI runs, plus the frontend)

Run from the repo root unless noted; stop at the first failure and show the error.

```bash
# 1. Backend tests
(cd apps/litprism-app/backend && uv run pytest tests/ -q)

# 2. Ruff on files you changed (not the whole tree — see note below)
uv run ruff check <changed .py files> && uv run ruff format --check <changed .py files>

# 3. Packages you touched
uv run pytest packages/<pkg>/tests/ -q

# 4. Frontend type-check + production bundle
(cd apps/litprism-app/frontend && npm run build)
```

CI (`.github/workflows/ci.yml`) runs: ruff + pytest per package, backend pytest, and
the frontend build. It does **not** lint the backend, and the backend tree has old
ruff violations in Alembic migrations and a couple of test files, so `make lint` /
`ruff check apps/` fails on code you didn't touch. Lint the files you changed; don't
mass-reformat unrelated files in a feature PR.

The frontend build prints a ">500 kB chunk" warning — expected, not a failure.
`npx eslint .` currently reports pre-existing errors; check only the files you changed.

## Package builds

```bash
uv build --package litprism-<name> --out-dir <scratch dir>
```

Use a scratch `--out-dir` for a local sanity check so `dist/` doesn't fill up; the real
publish happens in CI (see `release`).

## Backend checks

```bash
cd apps/litprism-app/backend
uv run python -c "import main"        # app wires up (routers, settings)
uv run alembic upgrade head           # apply migrations to the dev DB
uv run alembic check                  # models vs migrations drift (needs a DB at head)
uv run alembic revision --autogenerate -m "<what changed>"   # then read the file
```

## Run the full stack

`Procfile` is the source of truth (the `Makefile`'s `dev-worker` target points at an
old module). With overmind installed:

```bash
overmind start            # redis, web :8000, worker, beat, frontend (Vite)
overmind restart worker   # after changing tasks/
overmind connect web      # attach to one process's logs
```

The API refuses to start unless `SUPABASE_URL` is set or `AUTH_DISABLED=true`. For local
work put `AUTH_DISABLED=true` in the repo-root `.env`: every request is then the dev user,
who also adopts projects created before login existed.

`beat` drives the screening watchdog every 3 minutes; without it, stuck runs are not
re-dispatched. Redis must be reachable at the broker URL in `apps/litprism-app/.env`
(`redis-cli ping` → `PONG`).

Locally, beat runs as its own process. In production on Azure, the worker embeds it
(`celery … worker -B`, see `apps/litprism-app/docker-entrypoint.sh`).

## Deploy artifacts

If you touched the Dockerfile, `docker-entrypoint.sh`, `azure/deploy.sh` or
`.github/workflows/deploy-azure.yml`, check them before the PR:

```bash
bash -n apps/litprism-app/azure/deploy.sh && sh -n apps/litprism-app/docker-entrypoint.sh
docker build -f apps/litprism-app/Dockerfile -t litprism-backend .     # from repo root; needs a Docker daemon
docker run --rm -e LITPRISM_ROLE=api -p 8000:8000 --env-file apps/litprism-app/.env litprism-backend
```

The image only builds from the repo root; `.dockerignore` keeps the frontend and
`.env` out of it. CI doesn't build the image. The first real check is the deploy
workflow (see `release`), so say so if you couldn't run `docker build`.

To exercise a change in the real app rather than in tests, the built-in `run` skill
can drive it once the stack is up.
