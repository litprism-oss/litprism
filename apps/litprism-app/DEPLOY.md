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

GitHub logs in to Azure with OIDC through a user-assigned managed identity, so there is no
password to store and no Entra app registration is needed (many tenants block those).

Open Azure Cloud Shell (Bash) from the portal, then:

```bash
az group create -n litprism-rg -l westeurope
for p in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry; do
  az provider register -n "$p"
done

SUB=$(az account show --query id -o tsv)
TENANT=$(az account show --query tenantId -o tsv)
az identity create -n litprism-deploy -g litprism-rg -l westeurope
CLIENT=$(az identity show -n litprism-deploy -g litprism-rg --query clientId -o tsv)
PRINC=$(az identity show -n litprism-deploy -g litprism-rg --query principalId -o tsv)

az role assignment create --assignee-object-id "$PRINC" --assignee-principal-type ServicePrincipal \
  --role Contributor --scope "/subscriptions/$SUB/resourceGroups/litprism-rg"

az identity federated-credential create --name github-dev \
  --identity-name litprism-deploy -g litprism-rg \
  --issuer https://token.actions.githubusercontent.com \
  --subject repo:litprism-oss/litprism:ref:refs/heads/dev \
  --audiences api://AzureADTokenExchange

echo "AZURE_CLIENT_ID=$CLIENT"
echo "AZURE_TENANT_ID=$TENANT"
echo "AZURE_SUBSCRIPTION_ID=$SUB"
```

The three printed IDs go into GitHub secrets (step 3). They are identifiers, not passwords.
The federated credential only trusts workflow runs on the `dev` branch of this repository.

Provider registration takes a few minutes. `az provider show -n Microsoft.App --query registrationState`
should say `Registered` before you run the workflow.

The identity is scoped to `litprism-rg` only. Check that the subscription's spending limit is
on (Cost Management) so the monthly credit can't turn into a card charge.

## 3. GitHub secrets and variables

Repo → **Settings → Secrets and variables → Actions**.

Secrets:

| Name | Value |
|---|---|
| `AZURE_CLIENT_ID` | printed in step 2 |
| `AZURE_TENANT_ID` | printed in step 2 |
| `AZURE_SUBSCRIPTION_ID` | printed in step 2 |
| `DATABASE_URL_POOLER` | Supabase transaction pooler string (6543) |
| `DATABASE_URL_DIRECT` | Supabase session pooler string (5432) |
| `SECRET_KEY` | any random string, 40+ characters |
| `OPENAI_API_KEY` | your OpenAI key |

Optional secrets: `PUBMED_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `UNPAYWALL_EMAIL`.

Variables (Variables tab, not Secrets), optional: `CORS_ORIGINS` (default `*`) and `LLM_MODEL`.

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
