#!/usr/bin/env bash
# Operate the deployed LitPrism apps from GitHub Actions (see .github/workflows/azure-ops.yml).
#
#   ACTION=status   provisioning state, revisions and the NAMES of the env vars (never values)
#   ACTION=logs     last LINES console log lines, passed through redact.py
#   ACTION=restart  restart the latest revision (drops stale database connections)
#   ACTION=domain-info    the DNS records a custom domain needs (litprism-api only)
#   ACTION=domain-bind    bind HOSTNAME with a free managed certificate (litprism-api only)
#   ACTION=domain-status  hostnames bound to the app and their certificates
#
# Needs a logged-in `az`. Output goes to a public log: nothing here prints secrets.
set -euo pipefail

ACTION="${ACTION:?ACTION is required (status|logs|restart|domain-info|domain-bind|domain-status)}"
APP="${APP:?APP is required (litprism-api|litprism-worker)}"
RG="${RESOURCE_GROUP:-litprism-rg}"
LINES="${LINES:-150}"
ENV_NAME="${ENV_NAME:-litprism-env}"
HOSTNAME_ARG="${HOSTNAME_ARG:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"

case "$APP" in
  litprism-api | litprism-worker) ;;
  *) echo "Unknown app: $APP" >&2; exit 2 ;;
esac
[[ "$LINES" =~ ^[0-9]+$ ]] || { echo "LINES must be a number" >&2; exit 2; }

# Custom domains: only the API takes one, and only a name under litprism.org, so this
# workflow can't be used to attach someone else's domain.
case "$ACTION" in
  domain-info | domain-bind | domain-status)
    [[ "$APP" == "litprism-api" ]] || { echo "Domains are only for litprism-api" >&2; exit 2; }
    ;;
esac
if [[ "$ACTION" == "domain-bind" ]]; then
  [[ "$HOSTNAME_ARG" =~ ^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+litprism\.org$ ]] \
    || { echo "HOSTNAME must be a name under litprism.org (got: ${HOSTNAME_ARG:-empty})" >&2; exit 2; }
fi

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
  domain-info)
    # Both values are meant to be published in DNS, so printing them is fine.
    echo "CNAME target (the app's own address):"
    az containerapp show -n "$APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv
    echo
    echo "TXT record value for asuid.<name> (domain verification id):"
    az containerapp show -n "$APP" -g "$RG" --query properties.customDomainVerificationId -o tsv
    ;;
  domain-bind)
    echo "Binding $HOSTNAME_ARG to $APP (DNS must already be in place)"
    az containerapp hostname add -n "$APP" -g "$RG" --hostname "$HOSTNAME_ARG" -o none
    az containerapp hostname bind -n "$APP" -g "$RG" --hostname "$HOSTNAME_ARG" \
      --environment "$ENV_NAME" --validation-method CNAME -o none
    echo
    az containerapp hostname list -n "$APP" -g "$RG" --query \
      "[].{hostname:name, binding:bindingType, certificate:certificateId}" -o table
    ;;
  domain-status)
    az containerapp hostname list -n "$APP" -g "$RG" --query \
      "[].{hostname:name, binding:bindingType, certificate:certificateId}" -o table
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
