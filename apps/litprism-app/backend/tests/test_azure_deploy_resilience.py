"""azure/deploy.sh — a flaky Azure management API must not make the deploy wreck the apps.

Two real incidents: `az containerapp show` failed with a misleading error, the script decided the
app did not exist, took the *create* path, and that reset the API's ingress, dropping its custom
domain (api.litprism.org then reset every TLS connection). The tests run the real script against a
scripted fake `az` that fails on demand.
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[2] / "azure" / "deploy.sh"

FAKE_AZ = r"""#!/usr/bin/env bash
echo "$*" >> "$AZ_LOG"
bump() {
  f="$AZ_STATE/$1"; n=0
  [[ -f $f ]] && n=$(cat "$f")
  n=$((n+1)); echo "$n" > "$f"; echo "$n"
}
case "$*" in
  "account show --query id -o tsv") echo 12345678-aaaa-bbbb ;;
  "config set"*|"extension add"*) ;;
  *"acr show"*loginServer*) echo reg.azurecr.io ;;
  *"acr credential show"*username*) echo acruser ;;
  *"acr credential show"*) echo acrpass ;;
  "containerapp list"*)
    n=$(bump list)
    if (( n <= ${FAIL_LIST:-0} )); then echo "ERROR: (InternalServerError) boom" >&2; exit 1; fi
    for app in ${APPS_PRESENT:-}; do echo "$app"; done ;;
  "containerapp secret set"*)
    n=$(bump secret)
    if (( n <= ${FAIL_SECRET:-0} )); then echo "ERROR: transient" >&2; exit 1; fi ;;
  "containerapp hostname list"*)
    for h in ${BOUND_HOSTS:-}; do echo "$h"; done ;;
  "containerapp show"*fqdn*) echo litprism-api.example.azurecontainerapps.io ;;
  "containerapp show"*) echo "ERROR: The containerapp does not exist" >&2; exit 1 ;;
esac
exit 0
"""


@pytest.fixture
def azbox(tmp_path):
    bin_dir, state = tmp_path / "bin", tmp_path / "state"
    bin_dir.mkdir()
    state.mkdir()
    az = bin_dir / "az"
    az.write_text(FAKE_AZ)
    az.chmod(az.stat().st_mode | stat.S_IEXEC)
    return bin_dir, state, tmp_path / "az.log"


def deploy(azbox, **env_vars):
    bin_dir, state, log = azbox
    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "HOME": os.environ.get("HOME", "/tmp"),
        "AZ_LOG": str(log),
        "AZ_STATE": str(state),
        "IMAGE": "reg.azurecr.io/litprism-backend:abc",
        "DATABASE_URL": "postgresql://x",
        "SECRET_KEY": "k",
        "AUTH_DISABLED": "true",
        "RETRY_DELAY": "0",
        **env_vars,
    }
    result = subprocess.run(
        ["bash", str(DEPLOY), "apps"], env=env, capture_output=True, text=True, timeout=60
    )
    calls = log.read_text().splitlines() if log.exists() else []
    return result, calls


def count(calls, prefix):
    return sum(1 for c in calls if c.startswith(prefix))


BOTH = "litprism-api litprism-worker"


def test_existing_apps_are_updated_even_though_show_is_broken(azbox):
    """`show` always fails in the fake; the old script would have taken the create path."""
    result, calls = deploy(azbox, APPS_PRESENT=BOTH)
    assert result.returncode == 0, result.stderr
    assert count(calls, "containerapp update") == 2
    assert count(calls, "containerapp create") == 0


def test_missing_apps_are_created(azbox):
    result, calls = deploy(azbox, APPS_PRESENT="")
    assert result.returncode == 0, result.stderr
    assert count(calls, "containerapp create") == 2
    assert count(calls, "containerapp update") == 0


def test_only_the_missing_app_is_created(azbox):
    result, calls = deploy(azbox, APPS_PRESENT="litprism-api")
    assert result.returncode == 0, result.stderr
    assert any(c.startswith("containerapp update -n litprism-api") for c in calls)
    assert any(c.startswith("containerapp create -n litprism-worker") for c in calls)


def test_a_transient_list_failure_is_retried_and_still_updates(azbox):
    result, calls = deploy(azbox, APPS_PRESENT=BOTH, FAIL_LIST="2")
    assert result.returncode == 0, result.stderr
    assert count(calls, "containerapp create") == 0
    assert count(calls, "containerapp update") == 2
    assert "retrying" in result.stderr


def test_an_unreadable_app_list_stops_the_deploy_instead_of_guessing(azbox):
    result, calls = deploy(azbox, APPS_PRESENT=BOTH, FAIL_LIST="99")
    assert result.returncode != 0
    assert "refusing to guess" in result.stderr
    for forbidden in ("containerapp create", "containerapp update", "containerapp secret set"):
        assert count(calls, forbidden) == 0


def test_a_transient_failure_while_updating_is_retried(azbox):
    result, calls = deploy(azbox, APPS_PRESENT=BOTH, FAIL_SECRET="1")
    assert result.returncode == 0, result.stderr
    assert count(calls, "containerapp update") == 2
    assert count(calls, "containerapp create") == 0


def test_a_persistent_failure_while_updating_fails_the_deploy_without_going_on(azbox):
    result, calls = deploy(azbox, APPS_PRESENT=BOTH, FAIL_SECRET="99")
    assert result.returncode != 0
    assert count(calls, "containerapp update") == 0  # never got past the failing step
    assert count(calls, "containerapp create") == 0  # and never fell back to create
    assert count(calls, "containerapp secret set") == 3  # exactly RETRY_ATTEMPTS tries


# --- custom domain ------------------------------------------------------------------------


def test_a_missing_custom_domain_is_bound_again(azbox):
    result, calls = deploy(
        azbox, APPS_PRESENT=BOTH, API_CUSTOM_DOMAIN="api.litprism.org", BOUND_HOSTS=""
    )
    assert result.returncode == 0, result.stderr
    add = next(c for c in calls if c.startswith("containerapp hostname add"))
    bind = next(c for c in calls if c.startswith("containerapp hostname bind"))
    assert calls.index(add) < calls.index(bind)
    assert "--hostname api.litprism.org" in add and "--validation-method CNAME" in bind
    # and only after the apps themselves were updated
    assert calls.index(add) > max(
        i for i, c in enumerate(calls) if c.startswith("containerapp update")
    )


def test_a_bound_custom_domain_is_left_alone(azbox):
    result, calls = deploy(
        azbox,
        APPS_PRESENT=BOTH,
        API_CUSTOM_DOMAIN="api.litprism.org",
        BOUND_HOSTS="api.litprism.org",
    )
    assert result.returncode == 0, result.stderr
    assert "is bound" in result.stdout
    assert count(calls, "containerapp hostname add") == 0
    assert count(calls, "containerapp hostname bind") == 0


def test_no_custom_domain_configured_means_no_hostname_calls(azbox):
    result, calls = deploy(azbox, APPS_PRESENT=BOTH)
    assert result.returncode == 0, result.stderr
    assert count(calls, "containerapp hostname") == 0


@pytest.mark.parametrize(
    "domain",
    ["evil.com", "litprism.org.evil.com", "litprism.org", "API.litprism.org", "a b.litprism.org"],
)
def test_a_custom_domain_outside_litprism_org_is_refused_before_azure_is_touched(azbox, domain):
    result, calls = deploy(azbox, APPS_PRESENT=BOTH, API_CUSTOM_DOMAIN=domain)
    assert result.returncode == 2
    assert "litprism.org" in result.stderr
    assert count(calls, "containerapp") == 0
