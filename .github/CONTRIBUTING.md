# Contributing to LitPrism

Thank you for your interest in contributing. LitPrism is in early development —
contributions are welcome once the core packages reach a stable state.

## Development setup

```bash
# Requires Python >=3.11 and uv
git clone https://github.com/litprism/litprism
cd litprism
uv sync --all-packages
```

## Running checks

```bash
make lint    # ruff check + format check
make test    # pytest across all packages
make check   # both
```

## Package structure

Each source package lives under `packages/litprism-<name>/` and is independently
installable from PyPI. The `apps/litprism-app/` directory contains the web application.

See [litprism-spec-v4.md](../litprism-spec-v4.md) for the full specification, including
the `Article` model contract all packages must satisfy.

## Conventions

- **Formatter / linter:** `ruff` (line-length 100, rules E/F/I/UP/B/SIM)
- **Tests:** `pytest` with `asyncio_mode = auto`
- **HTTP client:** `httpx` (async)
- **Data models:** `pydantic v2`
- **No cross-imports between packages** — each package copies the shared `Article` model

## Submitting changes

1. Fork the repo and create a branch from `main`
2. Add tests for any new behaviour
3. Run `make check` before opening a PR
4. Open a pull request with a clear description of what and why
