# LitPrism

Open-source search, screening, and audit layer for evidence synthesis.

LitPrism automates the multi-database search step that every existing systematic review tool
skips — then screens with an LLM and exports a clean, auditable set ready for any downstream
tool or journal submission.

```
Natural language / PICO / direct query
              ↓
   LitPrism: Search → Dedup → Screen
   + PRISMA-S compliant search record
              ↓
  .nbib / .ris / .csv / ASReview format
  → Rayyan · Covidence · ASReview · your pipeline
```

## Packages

| Package | PyPI | Description |
|---------|------|-------------|
| `litprism-pubmed` | — | PubMed / MEDLINE via NCBI E-utilities |
| `litprism-europepmc` | — | Europe PMC (preprints, patents, MEDLINE supplement) |
| `litprism-semanticscholar` | — | Semantic Scholar (cross-disciplinary, 200M+ papers) |
| `litprism-crossref` | — | Crossref metadata enrichment |
| `litprism-screen` | — | LLM screening with grounded per-criterion decisions |

## Running the app

**Prerequisites:** Python ≥ 3.12, Node.js ≥ 18, [uv](https://astral.sh/uv), Redis,
[Overmind](https://github.com/DarthSim/overmind) — `brew install redis overmind`

```bash
# 1. Install dependencies
uv sync --all-packages
cd apps/litprism-app/frontend && npm install && cd ../../..

# 2. Configure environment
cp apps/litprism-app/.env.example apps/litprism-app/.env
# Edit apps/litprism-app/.env with your API keys

# 3. Run database migrations
cd apps/litprism-app/backend && uv run alembic upgrade head && cd ../../..

# 4. Start all services
overmind start
```

This launches the API (`:8000`), Celery worker, and frontend (`:5173`) in one terminal
with colour-coded logs. Use `overmind connect web|worker|frontend` to attach to any process.

<details>
<summary>Manual startup (three terminals)</summary>

**Backend** — `http://localhost:8000`
```bash
cd apps/litprism-app/backend
uv run uvicorn main:app --reload --port 8000
```

**Celery worker** (required for screening)
```bash
cd apps/litprism-app/backend
PYTHONPATH=$(pwd) uv run celery -A tasks.screening worker --loglevel=info
```

**Frontend** — `http://localhost:5173`
```bash
cd apps/litprism-app/frontend
npm run dev
```

</details>

## Status

Pre-release.

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
