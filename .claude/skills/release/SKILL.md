---
name: release
description: Ship LitPrism changes — open and merge PRs into dev, promote dev to main, publish packages to PyPI by tag, and deploy the app (Azure Container Apps backend via the "Deploy to Azure" workflow, Supabase Postgres, Vercel frontend). Use this whenever the user says commit, push, open a PR, merge, ship, release, deploy, publish, cut a version, "promote to main", or "merge when ready", and whenever they ask what's needed to get a change live.
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
| Frontend | Vercel (root dir `apps/litprism-app/frontend`, production branch `dev`) | `frontend/vercel.json` — `npm ci` + `npm run build` |
| Postgres | Supabase | `DATABASE_URL_POOLER` (transaction pooler, 6543) for the app, `DATABASE_URL_DIRECT` (*session* pooler, 5432) for migrations |
| API (`litprism-api`) + worker (`litprism-worker`, Celery with beat embedded via `-B`) | Azure Container Apps, resource group `litprism-rg`, `westeurope` | one image: `apps/litprism-app/Dockerfile` + `docker-entrypoint.sh`, role from `LITPRISM_ROLE=api\|worker` |
| Redis broker (`litprism-redis`) | Container App, internal TCP, no persistence | `redis://litprism-redis:6379/0`, set by `azure/deploy.sh` |

### Deploying the backend

The backend deploys through the manual workflow `.github/workflows/deploy-azure.yml`
("Deploy to Azure"). It's the only supported path. It provisions infra if missing,
builds and pushes the image to ACR, runs `alembic upgrade head`, then creates or
updates both apps through `apps/litprism-app/azure/deploy.sh`. A re-run is safe, and
that's how you redeploy.

A deploy changes the live app and spends the Azure credit, so confirm with the user
first and say which commit goes out. Then:

```bash
gh workflow run deploy-azure.yml --ref dev
gh run list --workflow deploy-azure.yml --limit 1     # get the run id
gh run watch <run-id> --exit-status
gh run view <run-id> --log-failed                     # if it fails
```

The run summary prints the API URL and the `VITE_API_URL` / `VITE_WS_URL` values for
Vercel. Check `https://<fqdn>/docs` afterwards.

Auth settings: `SUPABASE_URL` is a **required** GitHub variable (the API won't boot
without it, and `deploy.sh` stops early). `BOOTSTRAP_OWNER_EMAIL` and `ADMIN_EMAILS` are
variables. `SUPABASE_JWT_SECRET` is a secret needed only for legacy HS256 projects. Don't
deploy the backend publicly before the login UI has shipped: a frontend that sends no
token gets 401 on everything.

Rules that keep it working:
- **API and worker stay at exactly one replica** (`--min-replicas 1 --max-replicas 1`).
  WebSocket progress state is in the API process, and a second worker would run beat
  (the screening watchdog) twice. Never scale them up as a "fix".
- **Migrations run inside the workflow, before the apps update.** The API calls
  `create_all` on boot, so never point a new API at an unmigrated DB. Migrations use
  the session pooler: the Supabase direct host is IPv6-only, and GitHub runners are IPv4.
- **New env var or secret:** add it in four places: `config.py`, the workflow step's
  `env:`, the `secrets`/`envvars` arrays in `azure/deploy.sh`, and the tables in
  `DEPLOY.md`. Then add the GitHub secret, or a variable for non-secret values.
- **Changing only a secret's value:** Container Apps secrets are app-scoped and don't
  restart containers on their own. `deploy.sh` sets a per-run `DEPLOY_ID` env var, so
  every workflow run creates a new revision that reads the current secrets. A re-run
  is enough; keep that line if you edit the script.
- **Frontend:** Vercel builds on push to `dev`. `VITE_*` values are baked in at build
  time, so changing them needs a redeploy. A new frontend domain goes into the GitHub
  variable `CORS_ORIGINS`, then re-run the deploy workflow.

Local `az` commands need `az login` to the user's Visual Studio subscription. If `az`
isn't installed or logged in, hand the user the commands; Cloud Shell works too.
Never run `az group delete -n litprism-rg` (it tears down the whole backend) unless the
user asks for it in so many words.

The API requires a Supabase login (Session 16). Guests are anonymous sessions: they can
create projects, upload, search and preview screening, but not run screening or
full-text retrieval. Per-user cost limits arrive in Session 16.3. Until then a signed-in
user can still spend the OpenAI key, so mention that whenever a deploy makes the API
reachable, and suggest an OpenAI spend limit.
