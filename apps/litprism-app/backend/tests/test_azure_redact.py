"""azure/redact.py — logs printed into public GitHub Actions output must not leak secrets."""

import importlib.util
import io
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "azure" / "redact.py"
spec = importlib.util.spec_from_file_location("redact", SCRIPT)
redact_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(redact_module)
redact = redact_module.redact

GEMINI_KEY = "AIzaSyD-abcdefghijklmnopqrstuvwxyz012345"
OPENAI_KEY = "sk-proj-abcdefghijklmnop0123456789"
JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
    "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJVadQssw5c"
)


@pytest.mark.parametrize(
    ("line", "must_not_contain"),
    [
        (
            "sqlalchemy.exc.OperationalError: connect to postgresql+asyncpg://postgres.abcdefghijkl:"
            "hunter2@aws-0-eu-central-1.pooler.supabase.com:6543/postgres failed",
            ["hunter2", "abcdefghijkl", "pooler.supabase.com", "postgresql+asyncpg://"],
        ),
        ("broker redis://:s3cr3tpass@litprism-redis:6379/0 down", ["s3cr3tpass"]),
        ("connecting to db.abcdefghijkl.supabase.co:5432", ["abcdefghijkl", "supabase.co"]),
        (
            "GET https://litprism-api.happybay-e820cb65.westeurope.azurecontainerapps.io/x",
            ["happybay", "azurecontainerapps"],
        ),
        ("user postgres.abcdefghijklmnopqrst rejected", ["abcdefghijklmnopqrst"]),
        (f"litellm: bad key {GEMINI_KEY}", [GEMINI_KEY]),
        (f"openai key {OPENAI_KEY}", [OPENAI_KEY]),
        (f"url?key={GEMINI_KEY}&alt=sse", [GEMINI_KEY]),
        (f"Authorization: Bearer {JWT}", [JWT, "eyJhbGci"]),
        ("api_key=plainsecretvalue123", ["plainsecretvalue123"]),
        ("password: correct-horse-battery", ["correct-horse-battery"]),
        ("token=abcdefghijklmnop", ["abcdefghijklmnop"]),
        (
            "hash 0123456789abcdef0123456789abcdef0123456789abcdef",
            ["0123456789abcdef0123456789abcdef"],
        ),
    ],
)
def test_secrets_and_hosts_are_removed(line, must_not_contain):
    out = redact(line)
    for secret in must_not_contain:
        assert secret not in out, f"{secret!r} leaked in {out!r}"


def test_useful_error_text_survives():
    line = (
        "asyncpg.exceptions.TooManyConnectionsError: MaxClientsInSessionMode: max clients reached"
    )
    assert redact(line) == line


def test_traceback_file_paths_are_not_blanked():
    """A long path of safe characters must stay readable: that's what tracebacks are for."""
    line = (
        '  File "/app/.venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/'
        'asyncpg.py", line 590, in executemany'
    )
    assert redact(line) == line


def test_http_status_lines_survive():
    line = '127.0.0.1:54321 - "GET /projects HTTP/1.1" 500 Internal Server Error'
    assert redact(line) == line


def test_long_lines_are_truncated():
    out = redact("x " * 1000)
    assert len(out) <= redact_module.MAX_LINE + 2
    assert out.endswith("…")


def test_main_streams_stdin_to_stdout(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(f"ok line\nsecret {GEMINI_KEY}\nlast line\n"))
    redact_module.main()
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "ok line"
    assert GEMINI_KEY not in out[1]
    assert out[2] == "last line"
