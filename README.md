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

**Prerequisites:** Python ≥ 3.12, Node.js ≥ 18, [uv](https://astral.sh/uv), Redis

```bash
# 1. Install all dependencies
uv sync --all-packages

# 2. Copy and edit env
cp apps/litprism-app/.env.example apps/litprism-app/.env

# 3. Run database migrations
cd apps/litprism-app/backend
alembic upgrade head
cd ../../..
```

**Backend** (runs on http://localhost:8000):

```bash
cd apps/litprism-app/backend
uv run uvicorn main:app --reload --port 8000
```

**Celery worker** (required for screening):

```bash
cd apps/litprism-app/backend
uv run celery -A tasks.screening worker --loglevel=info
```

**Frontend** (runs on http://localhost:5173):

```bash
cd apps/litprism-app/frontend
cp .env.example .env.local   # or set VITE_API_URL and VITE_WS_URL manually
npm install
npm run dev
```

## Status

Pre-release. See [litprism-spec-v4.md](litprism-spec-v4.md) for the full specification.

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
