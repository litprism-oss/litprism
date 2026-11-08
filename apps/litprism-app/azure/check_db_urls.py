"""Preflight for the Azure deploy: can a GitHub runner reach the database?

GitHub-hosted runners only have IPv4. Supabase's *direct* host (db.<ref>.supabase.co)
is IPv6-only, so using it fails with "Network is unreachable" only after the registry,
Redis and the image have been built (about 20 minutes in). This check fails in seconds
instead and says which secret is wrong.

Stdlib only. Never prints a host name or credentials: Actions logs of a public repo are
public. Run by .github/workflows/deploy-azure.yml; reads the secrets from the environment.
"""

import os
import socket
import sys
from urllib.parse import urlsplit

CHECKS = {
    "DATABASE_URL_DIRECT": "migrations (Supabase session pooler, port 5432)",
    "DATABASE_URL_POOLER": "the running app (Supabase transaction pooler, port 6543)",
}
TCP_TIMEOUT_SECONDS = 10


def classify(host: str) -> str:
    """'direct' (IPv6-only db.<ref>.supabase.co), 'pooler', or 'other'."""
    host = host.lower()
    if host.startswith("db.") and host.endswith(".supabase.co"):
        return "direct"
    if host.endswith(".pooler.supabase.com"):
        return "pooler"
    return "other"


def parse(url: str) -> tuple[str | None, int | None, str | None]:
    """(host, port, user). Handles postgres://, postgresql:// and postgresql+asyncpg://."""
    parts = urlsplit(url.strip())
    try:
        port = parts.port
    except ValueError:
        port = None
    return parts.hostname, port, parts.username


def addresses(host: str, port: int, family: int) -> list[str]:
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(host, port, family)})
    except socket.gaierror:
        return []


def tcp_reachable_ipv4(address: str, port: int) -> bool:
    try:
        with socket.create_connection((address, port), timeout=TCP_TIMEOUT_SECONDS):
            return True
    except OSError:
        return False


def check(name: str, url: str | None) -> tuple[list[str], list[str]]:
    """Returns (info lines, errors)."""
    if not url or not url.strip():
        return [], [f"{name} is empty or not set."]
    host, port, user = parse(url)
    if not host:
        return [], [
            f"{name} is not a valid connection string (no host found). If the password contains "
            "@ # / or ?, reset it to letters and numbers."
        ]
    port = port or 5432
    kind = classify(host)
    v4, v6 = addresses(host, port, socket.AF_INET), addresses(host, port, socket.AF_INET6)
    info = [f"{name}: host type {kind}, port {port}, IPv4 addresses {len(v4)}, IPv6 {len(v6)}"]
    errors: list[str] = []

    if kind == "direct":
        errors.append(
            f"{name} uses the Supabase direct host (db.<ref>.supabase.co). It is IPv6-only and "
            "GitHub runners are IPv4-only. In Supabase open Connect and copy the *Session pooler* "
            "string (host aws-...pooler.supabase.com, user postgres.<project-ref>)."
        )
    elif not v4:
        errors.append(
            f"{name} has no IPv4 address, so a GitHub runner cannot reach it. Use a Supabase "
            "pooler connection string."
        )
    elif not tcp_reachable_ipv4(v4[0], port):
        errors.append(
            f"{name}: the host resolves but port {port} is not reachable over IPv4 from here. "
            "Check the port (session pooler 5432, transaction pooler 6543) and that the "
            "Supabase project is not paused."
        )
    if kind == "pooler" and user and "." not in user:
        errors.append(
            f"{name}: pooler connections need the user postgres.<project-ref>, not plain postgres."
        )
    return info, errors


def main() -> int:
    summary: list[str] = []
    failed = False
    for name, purpose in CHECKS.items():
        info, errors = check(name, os.environ.get(name))
        print(f"--- {name} for {purpose}")
        for line in info:
            print(line)
        status = "FAIL" if errors else "ok"
        for message in errors:
            print(f"::error title={name}::{message}")
            failed = True
        summary.append(f"| `{name}` | {status} | {' '.join(errors) or 'reachable over IPv4'} |")

    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a") as fh:
            fh.write(
                "### Database connection check\n\n| Secret | Result | Detail |\n|---|---|---|\n"
            )
            fh.write("\n".join(summary) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
