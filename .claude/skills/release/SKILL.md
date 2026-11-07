---
name: release
description: Ship LitPrism changes — open and merge PRs into dev, promote dev to main, publish packages to PyPI by tag, and deploy the app (Fly.io backend, Supabase Postgres, Vercel frontend). Use this whenever the user says commit, push, open a PR, merge, ship, release, deploy, publish, cut a version, "promote to main", or "merge when ready", and whenever they ask what's needed to get a change live.
---

# Release LitPrism

Branches (spec §19): `feat/*` and `fix/*` → `dev` (integration) → `main` (protected,
always green, deployable). Git actions are outward-facing, so do each one only when
the user has asked for it in this session; an earlier "commit it" doesn't cover a
later push or merge.

## 1. Commit

- Stage specific files only (`git add <paths>`), never `-A` / `.`.
- Repo commit format, e.g. `fix(screening): …`, `feat(app-backend): Session 16 — …`,
  `test(app-backend): …`. One logical change per commit.
- No `Co-Authored-By` trailer.
- `CLAUDE.md`, `docs/*.md` and `.claude/*` (except `.claude/skills/`) are gitignored on
  purpose — don't force-add them.

## 2. Pull request into dev

```bash
git push -u origin <branch>
gh pr list --head <branch> --state all     # a branch can be reused after its PR merged
gh pr create --base dev --head <branch> --title "<commit-style title>" --body-file <file>
```

If an earlier PR from the same branch is already merged, the new PR contains only the
newer commits — write the description for those, not the whole branch history.

Description: what changed and why, grouped (backend / frontend / tests); any behaviour
change a reviewer could trip over; what is **not** covered by tests; a short manual test
plan. End with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

## 3. Merge when ready

"Ready" means every check is green and the PR is mergeable:

```bash
gh pr checks <n> --watch --interval 15     # wait for: 4 package jobs, backend tests, frontend build
gh pr view <n> --json mergeable -q .mergeable   # MERGEABLE
gh pr merge <n> --merge                    # repo uses merge commits; keep the branch
```

If a check fails, show the failing job's log (`gh run view --log-failed`) and fix on the
branch rather than merging.

## 4. Promote dev → main

```bash
gh pr create --base main --head dev --title "release: <summary>" --body "<merged PRs since last promotion>"
```

Same readiness rule, then `gh pr merge --merge`. Confirm with the user first — `main`
is the deployable branch.

## 5. Publish a package to PyPI

`.github/workflows/publish.yml` publishes on tags shaped `litprism-<pkg>/v<version>`
via trusted publishing (environment `pypi`). Steps:

1. Bump `version` in `packages/litprism-<pkg>/pyproject.toml` in a PR, merge it.
2. Sanity-build locally: `uv build --package litprism-<pkg> --out-dir <scratch>`.
3. Tag the merged commit and push the tag (confirm with the user — a PyPI version can
   never be re-uploaded):
   ```bash
   git tag litprism-<pkg>/v<version> <commit>
   git push origin litprism-<pkg>/v<version>
   ```
4. Watch it: `gh run list --workflow publish.yml --limit 1`.

## 6. Deploy the app

`apps/litprism-app/DEPLOY.md` is the source of truth; read it before deploying. The
layout:

| Piece | Where | Config |
|---|---|---|
| Frontend | Vercel (root dir `apps/litprism-app/frontend`) | `frontend/vercel.json` — `npm ci` + `npm run build` |
| Postgres | Supabase | `DATABASE_URL` secret (transaction pooler, port 6543) |
| API + Celery worker + beat | Fly.io, one image | `apps/litprism-app/fly.toml` (`web`/`worker`/`beat` process groups), `apps/litprism-app/Dockerfile` |
| Redis broker | Upstash via `fly redis create` | `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` secrets |

There is no deploy workflow: deploys are manual, and they touch shared infrastructure.
Confirm with the user before each one and say what will change. The order matters:

1. **Migrations first** if the release adds any. Use the Supabase *direct* connection
   (port 5432):
   `cd apps/litprism-app/backend && DATABASE_URL='<direct url>' uv run alembic upgrade head`.
   The API calls `create_all` on boot, so starting a new API before migrating can
   create tables outside Alembic.
2. **Backend**, from the repo root:
   `fly deploy . --config apps/litprism-app/fly.toml --dockerfile apps/litprism-app/Dockerfile`.
   Keep `beat` at exactly one machine (`fly scale count web=1 worker=1 beat=1`). Two
   beats double-fire the watchdog.
3. **Frontend**: Vercel builds on push. `VITE_API_URL` / `VITE_WS_URL` are baked in at
   build time, so changing them needs a redeploy. A new frontend domain must go into the
   backend's `CORS_ORIGINS` secret.

Check that `flyctl` is installed and logged in (`fly auth whoami`) before step 2. If it
isn't, hand the user the commands rather than working around it.

Known gap (from `DEPLOY.md`): the upload volume is mounted on `web` only, so worker
tasks that read uploaded PDFs can't see them in production. Mention it when a change
touches full-text or upload paths.
