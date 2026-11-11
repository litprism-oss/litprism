"""Redact secrets and infrastructure details from log text (stdin -> stdout).

The Azure ops workflow prints container logs into GitHub Actions, and the logs of a public
repository are public. This removes database URLs, host names, API keys and tokens, and
shortens very long lines. It is a safety net, not a guarantee: don't log secrets.
"""

import re
import sys

MAX_LINE = 400

PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^\s'\"]+", re.I), "<db-url>"),
    (re.compile(r"redis(?:s)?://[^\s'\"]+", re.I), "<redis-url>"),
    (
        re.compile(
            r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:supabase\.(?:co|com)|azurecontainerapps\.io|azurecr\.io)",
            re.I,
        ),
        "<host>",
    ),
    (re.compile(r"postgres\.[a-z0-9]{12,}", re.I), "postgres.<ref>"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{20,}"), "<google-key>"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), "<api-key>"),
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._\-=+/]{8,}"), r"\1 <token>"),
    (
        re.compile(r"(?i)([?&](?:key|api_key|apikey|token|password|secret)=)[^&\s'\"]+"),
        r"\1<redacted>",
    ),
    (
        re.compile(
            r"(?i)\b((?:api[_-]?key|secret|password|passwd|token|authorization)\s*[:=]\s*)\S+"
        ),
        r"\1<redacted>",
    ),
    (re.compile(r"\b[A-Za-z0-9_\-]{40,}"), "<redacted>"),
]


def redact(line: str) -> str:
    for pattern, replacement in PATTERNS:
        line = pattern.sub(replacement, line)
    if len(line) > MAX_LINE:
        line = line[:MAX_LINE] + " …"
    return line


def main() -> None:
    for line in sys.stdin:
        print(redact(line.rstrip("\n")))


if __name__ == "__main__":
    main()
