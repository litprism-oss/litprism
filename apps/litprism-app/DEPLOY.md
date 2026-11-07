# Deploying LitPrism

| Piece | Where | Why |
|---|---|---|
| React frontend | Vercel | Static Vite build |
| Postgres | Supabase | Managed database |
| API + Celery worker + beat | Fly.io | Long-running processes and WebSockets don't fit Vercel functions |
| Redis (Celery broker) | Upstash via `fly redis create` | Required by the worker |

## 1. Supabase (database)

1. Create a project, then **Project Settings → Database → Connection string**.
2. Copy the **transaction pooler** string (port `6543`) for the running app and the
   **direct** or **session pooler** string (port `5432`) for migrations.
   Plain `postgresql://` URLs work as-is; the app rewrites them to `postgresql+asyncpg://`.
3. Run migrations once, **before the first API start** (the API also calls `create_all` on boot,
   which would otherwise create the tables outside Alembic):

   ```bash
   cd apps/litprism-app/backend
   DATABASE_URL='<direct connection string>' uv run alembic upgrade head
   ```

## 2. Backend on Fly.io

From the repository root:

```bash
fly apps create <your-app-name>          # then set `app = ...` in apps/litprism-app/fly.toml
fly volumes create litprism_data --size 1 --region fra -a <your-app-name>
fly redis create                          # note the redis:// URL it prints

fly secrets set -a <your-app-name> \
  DATABASE_URL='<transaction pooler string>' \
  CELERY_BROKER_URL='<redis url>' \
  CELERY_RESULT_BACKEND='<redis url>' \
  OPENAI_API_KEY='...' \
  SECRET_KEY="$(openssl rand -hex 32)" \
  CORS_ORIGINS='https://<your-vercel-domain>'

fly deploy . --config apps/litprism-app/fly.toml --dockerfile apps/litprism-app/Dockerfile
fly scale count web=1 worker=1 beat=1 -a <your-app-name>
```

Optional secrets: `PUBMED_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `UNPAYWALL_EMAIL`.

Known limitation: the upload volume is mounted on the `web` process only. Tasks on the
`worker` that read uploaded files (full-text PDFs) cannot see it. Move uploads to object
storage (Supabase Storage) before relying on that path in production.

## 3. Frontend on Vercel

1. **Add New → Project**, import the repository.
2. Set **Root Directory** to `apps/litprism-app/frontend` (build settings come from `vercel.json`).
3. Add environment variables:
   - `VITE_API_URL` = `https://<your-app-name>.fly.dev`
   - `VITE_WS_URL` = `wss://<your-app-name>.fly.dev`
4. Deploy, then put the resulting domain into the backend's `CORS_ORIGINS` secret.

The `VITE_*` values are baked in at build time; redeploy the frontend after changing them.
