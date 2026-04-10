# LitPrism — Step-by-Step Development Guide

---

## Overview

This guide walks through everything from creating the GitHub repo to
deploying a live demo instance. Follow phases in order — each builds
on the previous.

```
Phase 0 — Accounts & domain         ~1 hour
Phase 1 — GitHub repo setup         ~1 hour
Phase 2 — Local dev environment     ~2 hours
Phase 3 — Monorepo scaffold         ~2 hours  (then hand to Claude Code)
Phase 4 — CI/CD pipelines           ~2 hours
Phase 5 — Package development       weeks (per-package, iterative)
Phase 6 — Hosting & demo instance   ~2 hours
Phase 7 — Project website           ~1 hour
```

---

## Phase 0 — Accounts & Domain

### 0.1 Register the domain

1. Go to cloudflare.com/products/registrar
2. Search `litprism.org` → register (~$9/year)
3. Keep nameservers at Cloudflare — you'll use them for DNS later
4. Enable WHOIS privacy (free on Cloudflare)

Skip `.io` for now. Register `.com` only if the project takes off.

### 0.2 Accounts you need

| Account | Purpose | Cost |
|---------|---------|------|
| GitHub | Code, CI/CD, issues | Free |
| PyPI | Publish Python packages | Free |
| TestPyPI | Test publishing before real PyPI | Free |
| Fly.io | Host demo app instance | Free tier sufficient |
| Cloudflare | Domain + CDN + DNS | Free (domain ~$9/yr) |

### 0.3 Set up GitHub organisation (optional but recommended)

If you want `github.com/litprism/litprism` instead of
`github.com/yourname/litprism`:

1. GitHub → Your profile → Your organisations → New organisation
2. Name: `litprism`
3. Plan: Free
4. This lets contributors fork under the org and looks more professional

---

## Phase 1 — GitHub Repository Setup

### 1.1 Create the repo

```bash
# On GitHub: New repository
# Name: litprism
# Visibility: Public
# Init: No (we'll push from local)
# License: MIT (add during scaffold)
```

### 1.2 Repo settings to configure

Go to Settings on the repo and configure:

**General:**
- Description: `Open-source search, screening, and audit layer for systematic literature reviews`
- Website: `https://litprism.org` (after you set up the site)
- Topics: `systematic-review`, `literature-review`, `pubmed`, `python`, `llm`, `nlp`, `research`

**Branches:**
- Default branch: `main`
- Branch protection on `main`:
  - Require pull request before merging
  - Require status checks to pass (CI must be green)
  - Do not allow force pushes

**Secrets (Settings → Secrets → Actions):**
Add these now — you'll use them in CI/CD:

```
PYPI_API_TOKEN          # from pypi.org → Account settings → API tokens
TEST_PYPI_API_TOKEN     # from test.pypi.org → same
```

**Actions permissions:**
- Allow all actions and reusable workflows

### 1.3 GitHub Projects board

1. Repo → Projects → New project → Board view
2. Columns: `Backlog` | `In Progress` | `In Review` | `Done`
3. Link to the repo

### 1.4 Issue templates

Create `.github/ISSUE_TEMPLATE/` with two files:

**bug_report.md:**
```markdown
---
name: Bug report
about: Something isn't working
labels: bug
---

**Package:** (e.g. litprism-pubmed)
**Version:**
**Python version:**

**What happened:**

**What you expected:**

**Minimal reproduction:**
```python
# code here
```
```

**feature_request.md:**
```markdown
---
name: Feature request
about: Suggest an idea
labels: enhancement
---

**Which package or component:**

**Problem it solves:**

**Proposed solution:**
```

### 1.5 Labels

Delete GitHub's default labels and create these:

```
bug          #d73a4a    Something isn't working
enhancement  #a2eeef    New feature or request
docs         #0075ca    Documentation
ci           #e4e669    CI/CD related
pubmed       #f9d0c4    litprism-pubmed package
europepmc    #f9d0c4    litprism-europepmc package
screen       #c5def5    litprism-screen package
app          #bfd4f2    litprism-app
good first issue #7057ff Easy for newcomers
```

---

## Phase 2 — Local Development Environment

### 2.1 Prerequisites

Install these on your Mac (you're on macOS with OrbStack):

```bash
# uv — Python package manager (replaces pip, venv, pyenv)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify
uv --version   # should be 0.5+

# Node (for frontend in Phase 5+)
# Use nvm or install via homebrew
brew install node   # or: nvm install --lts

# Redis (for Celery task queue in the app)
brew install redis
brew services start redis
```

### 2.2 Clone and initial setup

```bash
git clone git@github.com:litprism/litprism.git
cd litprism

# uv creates the workspace virtual env
uv sync

# Verify Python version
uv run python --version   # should be 3.11+
```

### 2.3 Environment variables

Create `.env` at repo root (never commit this):

```bash
# .env
# LLM provider — pick one to start
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini

# Or Azure:
# LLM_PROVIDER=azure
# AZURE_API_KEY=...
# AZURE_API_BASE=https://myresource.openai.azure.com
# AZURE_API_VERSION=2024-02-01
# AZURE_DEPLOYMENT_NAME=gpt-4o

# Or Ollama (no key needed, must have Ollama running locally):
# LLM_PROVIDER=ollama
# LLM_MODEL=llama3.1

# PubMed (optional — without it you get 3 req/s)
PUBMED_API_KEY=...

# Semantic Scholar (optional — without it rate limit is lower)
SEMANTIC_SCHOLAR_API_KEY=...

# App database (SQLite default, no config needed for local dev)
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost/litprism

# App storage
UPLOAD_DIR=~/.litprism/uploads

# Celery (Redis must be running)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

Add `.env` to `.gitignore`:
```bash
echo ".env" >> .gitignore
echo ".env.*" >> .gitignore
echo "!.env.example" >> .gitignore
```

Create `.env.example` (commit this — shows contributors what's needed):
```bash
cp .env .env.example
# Then remove actual values from .env.example, keep key names
```

### 2.4 Editor setup (VS Code or Cursor)

Install extensions:
- Python (Microsoft)
- Ruff (Astral Software)
- Pylance
- Even Better TOML

Add `.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.ruff": "explicit",
    "source.organizeImports.ruff": "explicit"
  },
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

Add `.vscode/extensions.json`:
```json
{
  "recommendations": [
    "ms-python.python",
    "charliermarsh.ruff",
    "ms-python.pylance",
    "tamasfe.even-better-toml"
  ]
}
```

### 2.5 Useful local dev commands

Add a `Makefile` at repo root:
```makefile
.PHONY: test lint format check install dev

# Install all packages in dev mode
install:
	uv sync --all-packages

# Run all tests
test:
	uv run pytest packages/ -v

# Run tests for a specific package
test-pubmed:
	uv run pytest packages/litprism-pubmed/tests/ -v

test-screen:
	uv run pytest packages/litprism-screen/tests/ -v

# Lint + format check
lint:
	uv run ruff check packages/ apps/
	uv run ruff format --check packages/ apps/

# Auto-fix formatting
format:
	uv run ruff check --fix packages/ apps/
	uv run ruff format packages/ apps/

# Full check (what CI runs)
check: lint test

# Run the FastAPI backend locally
dev-backend:
	cd apps/litprism-app/backend && \
	uv run uvicorn main:app --reload --port 8000

# Run Celery worker locally
dev-worker:
	cd apps/litprism-app/backend && \
	uv run celery -A services.pipeline worker --loglevel=info

# Run frontend locally
dev-frontend:
	cd apps/litprism-app/frontend && \
	npm run dev

# Run database migrations
migrate:
	cd apps/litprism-app/backend && \
	uv run alembic upgrade head

# Generate a new migration
migration msg="":
	cd apps/litprism-app/backend && \
	uv run alembic revision --autogenerate -m "$(msg)"
```

---

## Phase 3 — Monorepo Scaffold (hand to Claude Code)

At this point, open Claude Code in the repo root and paste the
instructions from Section 20 of litprism-spec-v4.md.

Claude Code will create:
- Root `pyproject.toml` with uv workspace
- All package directories with `pyproject.toml`, `src/`, `tests/`
- GitHub Actions workflow files
- `README.md` files per package

**After Claude Code finishes Phase 1 scaffold, verify:**
```bash
uv sync                            # should resolve without errors
uv run ruff check packages/        # should pass (nothing to check yet)
uv run pytest packages/            # should pass (no tests yet)
```

**Then bring in your existing pubmed-py code:**
```bash
# Copy your existing code into packages/litprism-pubmed/src/litprism/pubmed/
# Then tell Claude Code: "Here is my existing PubMed client code.
# Refactor it to match the spec — models, entrez wrapper, parser, cache."
```

---

## Phase 4 — CI/CD Pipelines

### 4.1 CI workflow — runs on every PR

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        package:
          - litprism-pubmed
          - litprism-europepmc
          - litprism-semanticscholar
          - litprism-crossref
          - litprism-screen

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.11

      - name: Install package
        run: uv sync --package ${{ matrix.package }}

      - name: Lint
        run: |
          uv run --package ${{ matrix.package }} \
            ruff check packages/${{ matrix.package }}/

      - name: Format check
        run: |
          uv run --package ${{ matrix.package }} \
            ruff format --check packages/${{ matrix.package }}/

      - name: Test
        run: |
          uv run --package ${{ matrix.package }} \
            pytest packages/${{ matrix.package }}/tests/ -v \
            --tb=short
        env:
          # Use env secrets for tests that need API keys
          # Tests should mock by default — only integration tests need keys
          PUBMED_API_KEY: ${{ secrets.PUBMED_API_KEY }}
```

### 4.2 Publish workflow — triggered by tag

Create `.github/workflows/publish.yml`:

```yaml
name: Publish

on:
  push:
    tags:
      - "litprism-pubmed/v*"
      - "litprism-europepmc/v*"
      - "litprism-semanticscholar/v*"
      - "litprism-crossref/v*"
      - "litprism-screen/v*"

jobs:
  publish:
    runs-on: ubuntu-latest

    permissions:
      id-token: write   # for trusted publishing (no API token needed)

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Extract package name from tag
        id: pkg
        run: |
          TAG="${{ github.ref_name }}"
          PKG="${TAG%/v*}"
          echo "name=$PKG" >> $GITHUB_OUTPUT

      - name: Build package
        run: uv build --package ${{ steps.pkg.outputs.name }}

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        # Uses PyPI Trusted Publishing — no API token needed
        # Configure at: pypi.org → your package → Publishing → Add publisher
        # Set: owner=litprism, repo=litprism, workflow=publish.yml
```

**Trusted publishing setup (do this before your first publish):**
1. Go to pypi.org → Register account
2. Don't publish yet — first go to pypi.org/manage/account/publishing/
3. Add a "pending publisher" for each package:
   - Package name: `litprism-pubmed`
   - GitHub owner: `litprism` (or your username)
   - Repository: `litprism`
   - Workflow: `publish.yml`
4. Repeat for each package
5. Now CI can publish without storing API tokens as secrets

### 4.3 How to publish a new version

```bash
# 1. Bump version in packages/litprism-pubmed/pyproject.toml
#    version = "0.1.0" → "0.1.1"

# 2. Update CHANGELOG.md

# 3. Commit
git add packages/litprism-pubmed/
git commit -m "litprism-pubmed: bump to 0.1.1"

# 4. Tag — this triggers the publish workflow
git tag litprism-pubmed/v0.1.1
git push origin main --tags
```

### 4.4 Release notes automation (optional but nice)

Create `.github/workflows/release.yml`:

```yaml
name: Release notes

on:
  push:
    tags: ["*/v*"]

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
```

This auto-creates a GitHub Release with changelog from merged PRs.

---

## Phase 5 — Package Development Workflow

### Per-package development loop

```bash
# Work on litprism-pubmed
cd packages/litprism-pubmed

# Run tests in watch mode
uv run pytest tests/ -v --tb=short -x

# Or with coverage
uv run pytest tests/ --cov=src/litprism/pubmed --cov-report=term-missing
```

### Adding a new dependency to a package

```bash
# Add to a specific package's pyproject.toml
uv add httpx --package litprism-pubmed

# Add dev dependency
uv add pytest-asyncio --dev --package litprism-pubmed
```

### Testing against real APIs (integration tests)

Keep unit tests (mocked) and integration tests separate:

```
packages/litprism-pubmed/tests/
├── test_parser.py          # unit — uses fixture XML, no network
├── test_client.py          # unit — httpx mock
└── integration/
    └── test_live_api.py    # integration — needs real API, skipped in CI
```

Mark integration tests:
```python
# tests/integration/test_live_api.py
import pytest

@pytest.mark.integration
def test_real_pubmed_search():
    ...
```

```ini
# pyproject.toml
[tool.pytest.ini_options]
markers = ["integration: requires network and API keys"]
addopts = "-m 'not integration'"  # skip by default
```

Run integration tests manually when needed:
```bash
uv run pytest tests/ -m integration -v
```

---

## Phase 6 — Hosting & Demo Instance

The app is designed to be **self-hostable** — users run it themselves.
But you should also have a **public demo instance** so people can try it
without installing anything. Fly.io is the best fit: free tier, global,
Docker-based, easy PostgreSQL.

### 6.1 Dockerise the app

Create `apps/litprism-app/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace files
COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY apps/litprism-app/ apps/litprism-app/

# Install app and dependencies
RUN uv sync --package litprism-app --no-dev

# Run
CMD ["uv", "run", "uvicorn", "apps.litprism-app.backend.main:app",
     "--host", "0.0.0.0", "--port", "8080"]
```

Create `apps/litprism-app/docker-compose.yml` for local full-stack dev:

```yaml
version: "3.9"

services:
  backend:
    build: .
    ports:
      - "8000:8080"
    environment:
      DATABASE_URL: postgresql+asyncpg://litprism:litprism@db/litprism
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
    env_file: .env
    depends_on:
      - db
      - redis
    volumes:
      - uploads:/app/.litprism/uploads

  worker:
    build: .
    command: uv run celery -A services.pipeline worker --loglevel=info
    environment:
      DATABASE_URL: postgresql+asyncpg://litprism:litprism@db/litprism
      CELERY_BROKER_URL: redis://redis:6379/0
    env_file: .env
    depends_on:
      - db
      - redis

  frontend:
    build:
      context: apps/litprism-app/frontend
    ports:
      - "3000:3000"

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: litprism
      POSTGRES_PASSWORD: litprism
      POSTGRES_DB: litprism
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

volumes:
  pgdata:
  uploads:
```

Run locally:
```bash
docker compose up
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# API docs: http://localhost:8000/docs
```

### 6.2 Deploy demo to Fly.io

```bash
# Install flyctl
brew install flyctl

# Login
fly auth login

# From apps/litprism-app/
fly launch
# → App name: litprism-demo
# → Region: ams (Amsterdam — close to Lausanne)
# → PostgreSQL: Yes, development plan (free)
# → Redis: Yes, free tier
# → Deploy now: No (configure first)
```

Create `apps/litprism-app/fly.toml`:
```toml
app = "litprism-demo"
primary_region = "ams"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8080"
  LLM_PROVIDER = "openai"   # users bring their own key via UI

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    handlers = ["http"]
    port = 80
    force_https = true

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

[mounts]
  source = "uploads"
  destination = "/app/.litprism/uploads"
```

Set secrets (sensitive env vars):
```bash
fly secrets set OPENAI_API_KEY=sk-...  # or leave out — users provide their own
fly secrets set SECRET_KEY=<random-32-chars>
```

Deploy:
```bash
fly deploy
```

Run database migrations on first deploy:
```bash
fly ssh console -C "uv run alembic upgrade head"
```

**Custom domain on Fly.io:**
```bash
fly certs add litprism.org
fly certs add www.litprism.org
# Then add DNS records shown in output to Cloudflare
```

### 6.3 Continuous deployment to Fly.io

Add to `.github/workflows/deploy.yml`:

```yaml
name: Deploy demo

on:
  push:
    branches: [main]
    paths:
      - "apps/litprism-app/**"
      - "packages/**"

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: superfly/flyctl-actions/setup-flyctl@master

      - name: Deploy
        run: flyctl deploy --remote-only
        working-directory: apps/litprism-app
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

Get the API token:
```bash
fly tokens create deploy -x 999999h
# Copy output → GitHub → Secrets → FLY_API_TOKEN
```

### 6.4 Self-hosting docs for users

Create `apps/litprism-app/SELF_HOSTING.md`:
```markdown
## Self-hosting LitPrism

### Quickstart (Docker Compose)
git clone https://github.com/litprism/litprism
cd litprism/apps/litprism-app
cp .env.example .env
# Edit .env with your LLM API key
docker compose up

# First run only — apply DB migrations:
docker compose exec backend uv run alembic upgrade head

# Access at http://localhost:3000
```

---

## Phase 7 — Project Website

A simple static site at `litprism.org` — not a marketing site,
just a professional landing page that points to GitHub and docs.

### 7.1 Use GitHub Pages with a simple HTML page

Create `docs/index.html` in the repo — GitHub will serve it at
`litprism.org` after DNS config.

Or use **MkDocs** for proper documentation:

```bash
uv add mkdocs mkdocs-material --dev

# Create docs/
mkdir -p docs
cat > mkdocs.yml << 'EOF'
site_name: LitPrism
site_url: https://litprism.org
repo_url: https://github.com/litprism/litprism
theme:
  name: material
  palette:
    primary: teal
nav:
  - Home: index.md
  - Getting Started: getting-started.md
  - Packages:
    - litprism-pubmed: packages/pubmed.md
    - litprism-screen: packages/screen.md
  - Self-hosting: self-hosting.md
  - Contributing: contributing.md
EOF
```

Build and deploy docs to GitHub Pages:

Add to `.github/workflows/docs.yml`:
```yaml
name: Deploy docs

on:
  push:
    branches: [main]
    paths: ["docs/**", "mkdocs.yml"]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --dev
      - run: uv run mkdocs gh-deploy --force
```

### 7.2 Point litprism.org to GitHub Pages

In Cloudflare DNS:
```
Type    Name    Content                 Proxy
CNAME   @       litprism.github.io      DNS only (not proxied)
CNAME   www     litprism.github.io      DNS only
```

In GitHub repo → Settings → Pages:
- Source: GitHub Actions
- Custom domain: `litprism.org`
- Enforce HTTPS: ✅

---

## Phase 8 — Contributing Guide

Create `CONTRIBUTING.md` at repo root:

```markdown
# Contributing to LitPrism

## Setup
git clone https://github.com/litprism/litprism
cd litprism
uv sync

## Running tests
make test              # all packages
make test-pubmed       # specific package

## Before opening a PR
make check             # lint + test must pass

## Package structure
Each package lives in packages/litprism-{name}/
with its own pyproject.toml and tests/.

## Commit style
feat: add Europe PMC cursor pagination
fix: handle missing abstract in PubMed parser
docs: update screening prompt documentation
test: add fixture for malformed XML response
ci: add litprism-crossref to test matrix

## Releasing a new version
Only maintainers can release. Tag format:
  git tag litprism-pubmed/v0.2.0 && git push --tags
```

---

## Summary: What you'll have after all phases

```
litprism/                          GitHub repo
├── packages/                      5 PyPI packages
│   ├── litprism-pubmed/
│   ├── litprism-europepmc/
│   ├── litprism-semanticscholar/
│   ├── litprism-crossref/
│   └── litprism-screen/
├── apps/
│   └── litprism-app/              Self-hostable web app (Docker)
├── docs/                          MkDocs site → litprism.org
└── .github/workflows/
    ├── ci.yml                     Test on every PR
    ├── publish.yml                Publish to PyPI on tag
    ├── deploy.yml                 Deploy demo to Fly.io on main
    └── docs.yml                   Deploy docs to GitHub Pages

Hosted at:
  litprism.org                     Docs + landing page (GitHub Pages, free)
  demo.litprism.org                Live demo instance (Fly.io, ~free tier)
  pypi.org/project/litprism-*      Python packages (PyPI, free)
```

---

## Recommended order to start

```
Week 1   Phase 0 + 1 + 2    Accounts, repo, local dev env
Week 1   Phase 3             Scaffold monorepo (Claude Code)
Week 1   Phase 4             CI/CD pipelines
Week 2+  Phase 5             litprism-pubmed (refactor existing)
Week 3+  Phase 5             litprism-europepmc + semanticscholar
Week 4+  Phase 5             litprism-screen (abstract)
Week 5+  Phase 6             Docker + Fly.io deploy
Week 5+  Phase 7             Docs site
Ongoing  Phase 5             Full-text screening, app backend, frontend
```
