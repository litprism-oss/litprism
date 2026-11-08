#!/usr/bin/env bash
# Operate the deployed LitPrism apps from GitHub Actions (see .github/workflows/azure-ops.yml).
#
#   ACTION=status   provisioning state, revisions and the NAMES of the env vars (never values)
#   ACTION=logs     last LINES console log lines, passed through redact.py
#   ACTION=restart  restart the latest revision (drops stale database connections)
#
# Needs a logged-in `az`. Output goes to a public log: nothing here prints secrets.
set -euo pipefail

ACTION="${ACTION:?ACTION is required (status|logs|restart)}"
APP="${APP:?APP is required (litprism-api|litprism-worker)}"
RG="${RESOURCE_GROUP:-litprism-rg}"
LINES="${LINES:-150}"
HERE="$(cd "$(dirname "$0")" && pwd)"

case "$APP" in
  litprism-api | litprism-worker) ;;
  *) echo "Unknown app: $APP" >&2; exit 2 ;;
esac
[[ "$LINES" =~ ^[0-9]+$ ]] || { echo "LINES must be a number" >&2; exit 2; }

az config set extension.use_dynamic_install=yes_without_prompt \
  extension.dynamic_install_allow_preview=true >/dev/null
az extension add --name containerapp --upgrade --yes >/dev/null 2>&1 || true

latest_revision() {
  az containerapp show -n "$APP" -g "$RG" --query properties.latestRevisionName -o tsv
}

case "$ACTION" in
  status)
    az containerapp show -n "$APP" -g "$RG" --query \
      "{state:properties.provisioningState, running:properties.runningStatus, revision:properties.latestRevisionName, minReplicas:properties.template.scale.minReplicas, maxReplicas:properties.template.scale.maxReplicas}" \
      -o table
    echo
    az containerapp revision list -n "$APP" -g "$RG" --query \
      "[].{revision:name, active:properties.active, replicas:properties.replicas, state:properties.runningState, created:properties.createdTime}" \
      -o table
    echo
    echo "Environment variable names set on the container:"
    az containerapp show -n "$APP" -g "$RG" \
      --query "properties.template.containers[0].env[].name" -o tsv | sort
    ;;
  logs)
    az containerapp logs show -n "$APP" -g "$RG" --type console --tail "$LINES" \
      --format text 2>&1 | python3 "$HERE/redact.py"
    ;;
  restart)
    REVISION="$(latest_revision)"
    echo "Restarting revision $REVISION of $APP"
    az containerapp revision restart -n "$APP" -g "$RG" --revision "$REVISION" -o none
    echo "Restart requested."
    ;;
  *)
    echo "Unknown action: $ACTION" >&2
    exit 2
    ;;
esac
