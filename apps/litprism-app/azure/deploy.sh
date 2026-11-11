#!/usr/bin/env bash
# Idempotent deploy of the LitPrism backend to Azure Container Apps.
#
#   deploy.sh infra   create/verify registry, environment and Redis
#   deploy.sh apps    create/update the API and worker apps (needs IMAGE in env)
#
# Normally driven by .github/workflows/deploy-azure.yml, but it only needs a
# logged-in `az` CLI, so it can also be run by hand (e.g. in Azure Cloud Shell).
#
# Layout (all in one resource group):
#   litprism-redis   Redis in a container, internal TCP only      (0.25 vCPU / 0.5 GiB)
#   litprism-api     FastAPI, public HTTPS + WebSockets           (0.5 vCPU / 1 GiB)
#   litprism-worker  Celery worker + embedded beat, no ingress    (0.5 vCPU / 1 GiB)
# API and worker are pinned to exactly one replica: WebSocket progress state is
# in-process and beat must never run twice.
set -euo pipefail

MODE="${1:-}"
RG="${RESOURCE_GROUP:-litprism-rg}"
LOCATION="${LOCATION:-westeurope}"
ENV_NAME="${ENV_NAME:-litprism-env}"
API_APP="${API_APP:-litprism-api}"
WORKER_APP="${WORKER_APP:-litprism-worker}"
REDIS_APP="${REDIS_APP:-litprism-redis}"
REDIS_URL="redis://${REDIS_APP}:6379/0"

az config set extension.use_dynamic_install=yes_without_prompt \
  extension.dynamic_install_allow_preview=true >/dev/null
az extension add --name containerapp --upgrade --yes >/dev/null 2>&1 || true

SUB_ID="$(az account show --query id -o tsv)"
SUFFIX="$(printf '%s' "$SUB_ID" | tr -d '-' | cut -c1-8)"
ACR_NAME="${ACR_NAME:-litprism${SUFFIX}}"   # globally unique, alphanumeric only

app_exists() { az containerapp show -n "$1" -g "$RG" -o none 2>/dev/null; }

export_var() {  # make a value available to later workflow steps, if running in Actions
  if [[ -n "${GITHUB_ENV:-}" ]]; then echo "$1=$2" >> "$GITHUB_ENV"; fi
}

infra() {
  # The resource group is created once by hand (see DEPLOY.md) because the
  # deploy identity is scoped to it and cannot create resource groups.
  az group show -n "$RG" -o none \
    || { echo "Resource group $RG not found. Create it first (DEPLOY.md, step 2)." >&2; exit 1; }

  if ! az acr show -n "$ACR_NAME" -g "$RG" -o none 2>/dev/null; then
    echo "Creating container registry $ACR_NAME"
    az acr create -n "$ACR_NAME" -g "$RG" -l "$LOCATION" --sku Basic --admin-enabled true -o none
  fi
  export_var ACR_NAME "$ACR_NAME"
  export_var ACR_SERVER "$(az acr show -n "$ACR_NAME" -g "$RG" --query loginServer -o tsv)"

  if ! az containerapp env show -n "$ENV_NAME" -g "$RG" -o none 2>/dev/null; then
    echo "Creating Container Apps environment $ENV_NAME"
    az containerapp env create -n "$ENV_NAME" -g "$RG" -l "$LOCATION" -o none
  fi

  if ! app_exists "$REDIS_APP"; then
    echo "Creating Redis app $REDIS_APP"
    az containerapp create -n "$REDIS_APP" -g "$RG" --environment "$ENV_NAME" \
      --image docker.io/library/redis:7-alpine \
      --ingress internal --transport tcp --target-port 6379 --exposed-port 6379 \
      --cpu 0.25 --memory 0.5Gi --min-replicas 1 --max-replicas 1 -o none
  fi
}

apps() {
  : "${IMAGE:?IMAGE must be set to the pushed image reference}"
  : "${DATABASE_URL:?DATABASE_URL (Supabase transaction pooler string) is required}"
  : "${SECRET_KEY:?SECRET_KEY is required}"
  # Login is on by default. AUTH_DISABLED=true (GitHub variable) runs the API open: every
  # visitor shares one account. Only for a short-lived demo; never with real users' data.
  if [[ "${AUTH_DISABLED:-}" != "true" ]]; then
    : "${SUPABASE_URL:?SUPABASE_URL is required (the API refuses to start without it). Set it as a GitHub variable, or set AUTH_DISABLED=true for an open demo.}"
  fi

  local acr_server acr_user acr_pass
  acr_server="$(az acr show -n "$ACR_NAME" -g "$RG" --query loginServer -o tsv)"
  acr_user="$(az acr credential show -n "$ACR_NAME" -g "$RG" --query username -o tsv)"
  acr_pass="$(az acr credential show -n "$ACR_NAME" -g "$RG" --query 'passwords[0].value' -o tsv)"
  echo "::add-mask::${acr_pass}"

  # Provider: explicit LLM_PROVIDER wins; otherwise infer from whichever key is set.
  local provider="${LLM_PROVIDER:-}"
  if [[ -z "$provider" ]]; then
    if [[ -n "${OPENAI_API_KEY:-}" ]]; then provider=openai
    elif [[ -n "${GEMINI_API_KEY:-}" ]]; then provider=gemini
    else provider=openai; fi
  fi
  echo "LLM provider: ${provider}"

  # Secrets live in Container Apps secrets, referenced by name from env vars.
  local -a secrets=("database-url=${DATABASE_URL}" "secret-key=${SECRET_KEY}")
  local -a envvars=(
    "DATABASE_URL=secretref:database-url"
    "SECRET_KEY=secretref:secret-key"
    "LLM_PROVIDER=${provider}"
    "CORS_ORIGINS=${CORS_ORIGINS:-*}"
    "CELERY_BROKER_URL=${REDIS_URL}"
    "CELERY_RESULT_BACKEND=${REDIS_URL}"
    # Changes on every run so each deploy creates a new revision. Secrets are
    # app-scoped: without a new revision, a rotated secret is not picked up.
    "DEPLOY_ID=${GITHUB_RUN_ID:-local}.${GITHUB_RUN_ATTEMPT:-$(date +%s)}"
  )
  if [[ -n "${LLM_MODEL:-}" ]]; then envvars+=("LLM_MODEL=${LLM_MODEL}"); fi
  if [[ -n "${SUPABASE_URL:-}" ]]; then envvars+=("SUPABASE_URL=${SUPABASE_URL}"); fi
  if [[ "${AUTH_DISABLED:-}" == "true" ]]; then
    echo "WARNING: deploying with AUTH_DISABLED=true: the API is open to anyone with the link."
    envvars+=("AUTH_DISABLED=true")
  fi
  if [[ -n "${ADMIN_EMAILS:-}" ]]; then envvars+=("ADMIN_EMAILS=${ADMIN_EMAILS}"); fi
  if [[ -n "${BOOTSTRAP_OWNER_EMAIL:-}" ]]; then
    envvars+=("BOOTSTRAP_OWNER_EMAIL=${BOOTSTRAP_OWNER_EMAIL}")
  fi
  if [[ -n "${LLM_CONCURRENCY:-}" ]]; then envvars+=("LLM_CONCURRENCY=${LLM_CONCURRENCY}"); fi
  local pair name var
  for pair in openai-api-key:OPENAI_API_KEY gemini-api-key:GEMINI_API_KEY \
              pubmed-api-key:PUBMED_API_KEY \
              semantic-scholar-api-key:SEMANTIC_SCHOLAR_API_KEY unpaywall-email:UNPAYWALL_EMAIL \
              supabase-jwt-secret:SUPABASE_JWT_SECRET; do
    name="${pair%%:*}"; var="${pair##*:}"
    if [[ -n "${!var:-}" ]]; then
      secrets+=("${name}=${!var}")
      envvars+=("${var}=secretref:${name}")
    fi
  done

  upsert() {  # upsert <app-name> <role> [extra create flags...]
    local app="$1" role="$2"; shift 2
    if app_exists "$app"; then
      echo "Updating $app"
      az containerapp registry set -n "$app" -g "$RG" \
        --server "$acr_server" --username "$acr_user" --password "$acr_pass" -o none
      az containerapp secret set -n "$app" -g "$RG" --secrets "${secrets[@]}" -o none
      az containerapp update -n "$app" -g "$RG" --image "$IMAGE" \
        --set-env-vars "${envvars[@]}" "LITPRISM_ROLE=${role}" -o none
    else
      echo "Creating $app"
      az containerapp create -n "$app" -g "$RG" --environment "$ENV_NAME" --image "$IMAGE" \
        --registry-server "$acr_server" --registry-username "$acr_user" --registry-password "$acr_pass" \
        --cpu 0.5 --memory 1.0Gi --min-replicas 1 --max-replicas 1 \
        --secrets "${secrets[@]}" --env-vars "${envvars[@]}" "LITPRISM_ROLE=${role}" \
        "$@" -o none
    fi
  }

  upsert "$API_APP" api --ingress external --target-port 8000
  upsert "$WORKER_APP" worker

  local fqdn
  fqdn="$(az containerapp show -n "$API_APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)"
  echo
  echo "API:        https://${fqdn}"
  echo "API docs:   https://${fqdn}/docs"
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    {
      echo "### LitPrism backend deployed"
      echo
      echo "- API: https://${fqdn}  (docs: https://${fqdn}/docs)"
      echo "- Vercel \`VITE_API_URL\`: \`https://${fqdn}\`"
      echo "- Vercel \`VITE_WS_URL\`: \`wss://${fqdn}\`"
      echo "- Image: \`${IMAGE}\`"
    } >> "$GITHUB_STEP_SUMMARY"
  fi
}

case "$MODE" in
  infra) infra ;;
  apps)  apps ;;
  *) echo "usage: $0 {infra|apps}" >&2; exit 2 ;;
esac
