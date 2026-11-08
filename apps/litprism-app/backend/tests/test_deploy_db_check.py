"""azure/check_db_urls.py — the deploy preflight that catches an unreachable database URL."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "azure" / "check_db_urls.py"
spec = importlib.util.spec_from_file_location("check_db_urls", SCRIPT)
check_db_urls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_db_urls)

DIRECT = "postgresql://postgres:s3cret@db.abcdefghijkl.supabase.co:5432/postgres"
SESSION = (
    "postgresql://postgres.abcdefghijkl:s3cret@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"
)
TRANSACTION = SESSION.replace(":5432/", ":6543/")


@pytest.fixture
def network(monkeypatch):
    """Pretend DNS and TCP work, so tests never touch the real network."""
    monkeypatch.setattr(check_db_urls, "addresses", lambda host, port, family: ["203.0.113.7"])
    monkeypatch.setattr(check_db_urls, "tcp_reachable_ipv4", lambda address, port: True)


@pytest.mark.parametrize(
    ("host", "kind"),
    [
        ("db.abcdefghijkl.supabase.co", "direct"),
        ("DB.abcdefghijkl.supabase.co", "direct"),
        ("aws-0-eu-central-1.pooler.supabase.com", "pooler"),
        ("aws-1-us-east-2.pooler.supabase.com", "pooler"),
        ("localhost", "other"),
        ("my-db.example.com", "other"),
    ],
)
def test_classify(host, kind):
    assert check_db_urls.classify(host) == kind


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+asyncpg"])
def test_parse_accepts_every_scheme_the_app_uses(scheme):
    url = f"{scheme}://postgres.abc:pw@aws-0-eu.pooler.supabase.com:6543/postgres"
    assert check_db_urls.parse(url) == ("aws-0-eu.pooler.supabase.com", 6543, "postgres.abc")


def test_parse_with_an_encoded_at_sign_in_the_password():
    url = "postgresql://postgres.abc:p%40ss@aws-0-eu.pooler.supabase.com:5432/postgres"
    assert check_db_urls.parse(url)[0] == "aws-0-eu.pooler.supabase.com"


def test_parse_without_a_host():
    assert check_db_urls.parse("not a url")[0] is None


def test_the_direct_host_is_rejected_with_a_fix_even_if_it_resolves(network):
    info, errors = check_db_urls.check("DATABASE_URL_DIRECT", DIRECT)
    assert len(errors) == 1
    assert "Session pooler" in errors[0]
    assert "IPv6-only" in errors[0]


def test_a_session_pooler_url_passes(network):
    assert check_db_urls.check("DATABASE_URL_DIRECT", SESSION)[1] == []


def test_a_transaction_pooler_url_passes(network):
    assert check_db_urls.check("DATABASE_URL_POOLER", TRANSACTION)[1] == []


def test_pooler_url_with_a_plain_postgres_user_is_flagged(network):
    url = SESSION.replace("postgres.abcdefghijkl:", "postgres:")
    errors = check_db_urls.check("DATABASE_URL_POOLER", url)[1]
    assert len(errors) == 1
    assert "postgres.<project-ref>" in errors[0]


def test_a_host_with_no_ipv4_address_is_rejected(monkeypatch):
    monkeypatch.setattr(check_db_urls, "addresses", lambda host, port, family: [])
    errors = check_db_urls.check("DATABASE_URL_POOLER", "postgresql://u:p@db.example.org/x")[1]
    assert "no IPv4 address" in errors[0]


def test_an_unreachable_port_is_rejected(monkeypatch):
    monkeypatch.setattr(check_db_urls, "addresses", lambda host, port, family: ["203.0.113.7"])
    monkeypatch.setattr(check_db_urls, "tcp_reachable_ipv4", lambda address, port: False)
    errors = check_db_urls.check("DATABASE_URL_POOLER", SESSION)[1]
    assert "not reachable over IPv4" in errors[0]


@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_missing_secret_is_reported(value):
    errors = check_db_urls.check("DATABASE_URL_DIRECT", value)[1]
    assert "empty or not set" in errors[0]


def test_garbage_is_reported_as_an_invalid_connection_string():
    errors = check_db_urls.check("DATABASE_URL_DIRECT", "hello world")[1]
    assert "not a valid connection string" in errors[0]


def test_main_passes_with_two_good_urls(network, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL_DIRECT", SESSION)
    monkeypatch.setenv("DATABASE_URL_POOLER", TRANSACTION)
    assert check_db_urls.main() == 0
    assert "::error" not in capsys.readouterr().out


def test_main_fails_when_one_url_is_the_direct_host(network, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL_DIRECT", DIRECT)
    monkeypatch.setenv("DATABASE_URL_POOLER", TRANSACTION)
    assert check_db_urls.main() == 1
    out = capsys.readouterr().out
    assert "::error title=DATABASE_URL_DIRECT::" in out
    assert "DATABASE_URL_POOLER::" not in out


def test_output_never_contains_hosts_or_passwords(network, monkeypatch, capsys):
    """Actions logs of a public repo are public."""
    monkeypatch.setenv("DATABASE_URL_DIRECT", DIRECT)
    monkeypatch.setenv("DATABASE_URL_POOLER", SESSION)
    check_db_urls.main()
    out = capsys.readouterr().out
    real_values = (
        "abcdefghijkl",  # the project ref
        "s3cret",  # the password
        "db.abcdefghijkl.supabase.co",
        "aws-0-eu-central-1.pooler.supabase.com",
    )
    for value in real_values:
        assert value not in out


def test_main_writes_a_step_summary(network, monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("DATABASE_URL_DIRECT", DIRECT)
    monkeypatch.setenv("DATABASE_URL_POOLER", TRANSACTION)
    check_db_urls.main()
    text = summary.read_text()
    assert "| `DATABASE_URL_DIRECT` | FAIL |" in text
    assert "| `DATABASE_URL_POOLER` | ok |" in text
    assert "abcdefghijkl" not in text
