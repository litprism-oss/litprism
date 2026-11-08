# Deploying LitPrism

| Piece | Where | Notes |
|---|---|---|
| React frontend | Vercel | Static Vite build |
| Postgres | Supabase | Managed database |
| API + Celery worker + Redis | Azure Container Apps | Deployed by `.github/workflows/deploy-azure.yml` |

The backend is one Docker image (`apps/litprism-app/Dockerfile`) run in two roles via
`LITPRISM_ROLE`: `api` (FastAPI) and `worker` (Celery with the beat scheduler embedded).
Both are pinned to exactly one replica: WebSocket progress state lives in the API process,
and a second worker would run the beat schedule twice. Redis runs as a small container in
the same Container Apps environment (internal only, no persistence).

Everything is in one resource group, `litprism-rg`, in `westeurope`.

## 1. Supabase (database)

1. Create a project and save the database password.
2. **Connect** shows several connection strings. Copy two:
   - **Transaction pooler** (port 6543) for the running app → secret `DATABASE_URL_POOLER`
   - **Session pooler** (port 5432 on the pooler host) for migrations → secret `DATABASE_URL_DIRECT`

   Use the *session pooler*, not the "direct connection": the direct host is IPv6-only and
   GitHub runners are IPv4.
3. Plain `postgresql://` strings work as-is; the app rewrites them to `postgresql+asyncpg://`.
   If the password contains `@ # / ?` characters, reset it to letters and numbers.

## 2. Azure (one-time, in Cloud Shell)

Open Azure Cloud Shell (Bash) from the portal, then:

```bash
az group create -n litprism-rg -l westeurope

for p in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry; do
  az provider register -n "$p"
done

SUB=$(az account show --query id -o tsv)
az ad sp create-for-rbac --name litprism-deploy --role contributor \
  --scopes "/subscriptions/$SUB/resourceGroups/litprism-rg" -o json \
  | jq --arg s "$SUB" '{clientId:.appId, clientSecret:.password, tenantId:.tenant, subscriptionId:$s}'
```

The last command prints a JSON object. Copy all of it into the GitHub secret
`AZURE_CREDENTIALS`. It contains a password: don't paste it anywhere else.

Provider registration takes a few minutes. `az provider show -n Microsoft.App --query registrationState`
should say `Registered` before you run the workflow.

The identity is scoped to `litprism-rg` only. Check that the subscription's spending limit is
on (Cost Management) so the monthly credit can't turn into a card charge.

## 3. GitHub secrets and variables

Repo → **Settings → Secrets and variables → Actions**.

Secrets:

| Name | Value |
|---|---|
| `AZURE_CREDENTIALS` | JSON from step 2 |
| `DATABASE_URL_POOLER` | Supabase transaction pooler string (6543) |
| `DATABASE_URL_DIRECT` | Supabase session pooler string (5432) |
| `SECRET_KEY` | any random string, 40+ characters |
| `OPENAI_API_KEY` | your OpenAI key |

Optional secrets: `PUBMED_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `UNPAYWALL_EMAIL`.

Variables (Variables tab, not Secrets):

| Name | Required | Value |
|---|---|---|
| `SUPABASE_URL` | **yes** | `https://<project-ref>.supabase.co` (Project Settings → API). The API refuses to start without it, and the deploy stops with an error if it is missing |
| `BOOTSTRAP_OWNER_EMAIL` | first deploy | your Google/GitHub email. The first time you sign in with it, you take ownership of the projects that existed before login was added |
| `ADMIN_EMAILS` | optional | comma-separated emails with unlimited credits (used from Session 16.3) |
| `CORS_ORIGINS` | optional | default `*` |
| `LLM_MODEL` | optional | |

Optional secret `SUPABASE_JWT_SECRET`: only for an older Supabase project that still signs
tokens with a shared secret (Project Settings → API → JWT Secret). Leave it unset on a
current project: the API then verifies tokens with Supabase's public signing keys.

## Login

Every API route needs a Supabase access token (`Authorization: Bearer …`), and every project
belongs to one user. Other people's projects answer 404. Guests (anonymous Supabase sessions)
can create projects, upload, search and export but not run screening or full-text retrieval.

**Do not deploy the backend publicly until the login UI (Session 16.2) is merged**: the current
frontend sends no token, so every request would be rejected.

For local development set `AUTH_DISABLED=true` in `.env` (see `.env.example`). Every request is
then the fixed dev user, who also adopts projects that predate login. Never set it in
production. The API logs a warning at startup when it is on.

## 4. Deploy the backend

**Actions → Deploy to Azure → Run workflow** (branch `dev`). It provisions the registry,
environment and Redis, builds and pushes the image, runs `alembic upgrade head`, and
creates or updates the API and worker. Re-running it is safe and is how you redeploy.

The run summary prints the API URL. Open `<url>/docs` to check it is up.

If the workflow misbehaves you can run the same script in Cloud Shell:
`bash apps/litprism-app/azure/deploy.sh infra`, push an image to the registry, then set
`IMAGE`, `DATABASE_URL`, `SECRET_KEY` and run `bash apps/litprism-app/azure/deploy.sh apps`.

## 5. Vercel (frontend)

1. Import the repo, set **Root Directory** to `apps/litprism-app/frontend` and
   **Production Branch** to `dev`.
2. Environment variables (Production and Preview):
   - `VITE_API_URL` = `https://<api-fqdn>`
   - `VITE_WS_URL` = `wss://<api-fqdn>`
3. Deploy. The `VITE_*` values are baked in at build time: redeploy after changing them.
4. Set the GitHub variable `CORS_ORIGINS` to your Vercel URL (e.g. `https://litprism.vercel.app`)
   and re-run the workflow.

## Cost and shutting down

Three always-on containers (about 1.25 vCPU / 2.5 GiB in total) plus a Basic container
registry. Watch **Cost Management → Cost analysis** after the first days. To stop all charges:

```bash
az group delete -n litprism-rg --yes --no-wait
```

The Supabase database and Vercel site are unaffected. Moving to another host later means
re-using the same Dockerfile: set `LITPRISM_ROLE=api` and `LITPRISM_ROLE=worker` on two
services, plus a Redis instance and the same environment variables.
