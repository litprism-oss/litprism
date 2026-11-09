"""azure/ops.sh — custom-domain actions may only attach names under litprism.org to the API."""

import os
import stat
import subprocess
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[2] / "azure" / "ops.sh"


@pytest.fixture
def fake_az(tmp_path):
    """A fake `az` first on PATH that records every call."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "az.log"
    az = bin_dir / "az"
    az.write_text('#!/usr/bin/env bash\necho "$*" >> "$AZ_LOG"\nexit 0\n')
    az.chmod(az.stat().st_mode | stat.S_IEXEC)
    return bin_dir, log


def run_ops(fake_az, **env_vars):
    bin_dir, log = fake_az
    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "HOME": os.environ.get("HOME", "/tmp"),
        "AZ_LOG": str(log),
        "APP": "litprism-api",
        **env_vars,
    }
    result = subprocess.run(["bash", str(OPS)], env=env, capture_output=True, text=True, timeout=30)
    calls = log.read_text().splitlines() if log.exists() else []
    return result, calls


@pytest.mark.parametrize(
    "hostname",
    [
        "evil.com",
        "litprism.org.evil.com",
        "evillitprism.org",
        "litprism.org",  # the bare apex goes to Vercel, not here
        "",
        "-bad.litprism.org",
        "a..litprism.org",
        "API.litprism.org",
        "a b.litprism.org",
        "api.litprism.org; rm -rf /",
        "api.litprism.org\nevil.com",
        "$(whoami).litprism.org",
        "api.litprism.org.",
    ],
)
def test_bad_hostnames_are_rejected_before_azure_is_touched(fake_az, hostname):
    result, calls = run_ops(fake_az, ACTION="domain-bind", HOSTNAME_ARG=hostname)
    assert result.returncode == 2, result.stderr
    assert "litprism.org" in result.stderr
    assert calls == []  # not a single az call


@pytest.mark.parametrize(
    "hostname", ["api.litprism.org", "api-dev.litprism.org", "a.b.litprism.org"]
)
def test_good_hostnames_are_added_then_bound_with_a_managed_certificate(fake_az, hostname):
    result, calls = run_ops(fake_az, ACTION="domain-bind", HOSTNAME_ARG=hostname)
    assert result.returncode == 0, result.stderr
    add = next(c for c in calls if c.startswith("containerapp hostname add"))
    bind = next(c for c in calls if c.startswith("containerapp hostname bind"))
    assert calls.index(add) < calls.index(bind)
    assert f"--hostname {hostname}" in add and f"--hostname {hostname}" in bind
    assert "--validation-method CNAME" in bind
    assert "--environment litprism-env" in bind
    assert "-n litprism-api" in add and "-g litprism-rg" in add


@pytest.mark.parametrize("action", ["domain-info", "domain-bind", "domain-status"])
def test_domain_actions_are_not_available_for_the_worker(fake_az, action):
    result, calls = run_ops(
        fake_az, ACTION=action, APP="litprism-worker", HOSTNAME_ARG="api.litprism.org"
    )
    assert result.returncode == 2
    assert "only for litprism-api" in result.stderr
    assert calls == []


def test_domain_info_reads_the_cname_target_and_the_verification_id(fake_az):
    result, calls = run_ops(fake_az, ACTION="domain-info")
    assert result.returncode == 0, result.stderr
    shown = [c for c in calls if c.startswith("containerapp show")]
    assert any("ingress.fqdn" in c for c in shown)
    assert any("customDomainVerificationId" in c for c in shown)


def test_domain_status_only_lists(fake_az):
    result, calls = run_ops(fake_az, ACTION="domain-status")
    assert result.returncode == 0, result.stderr
    assert any(c.startswith("containerapp hostname list") for c in calls)
    assert not any("hostname add" in c or "hostname bind" in c for c in calls)


def test_the_other_actions_still_work(fake_az):
    result, calls = run_ops(fake_az, ACTION="restart")
    assert result.returncode == 0, result.stderr
    assert any(c.startswith("containerapp revision restart") for c in calls)


def test_an_unknown_action_is_rejected(fake_az):
    result, _ = run_ops(fake_az, ACTION="delete-everything")
    assert result.returncode == 2
