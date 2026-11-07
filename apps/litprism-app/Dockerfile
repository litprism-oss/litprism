# Backend image. The same image runs the API and the Celery worker; the role is
# picked with the LITPRISM_ROLE env var (see docker-entrypoint.sh).
# Build from the repository root:
#   docker build -f apps/litprism-app/Dockerfile -t litprism-backend .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Workspace manifests first so dependency layers cache across code changes.
COPY pyproject.toml uv.lock .python-version ./
COPY packages ./packages
COPY apps/litprism-app ./apps/litprism-app

RUN uv sync --frozen --no-dev --package litprism-app \
    && chmod +x /app/apps/litprism-app/docker-entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/apps/litprism-app/backend"

WORKDIR /app/apps/litprism-app/backend

EXPOSE 8000
ENTRYPOINT ["/app/apps/litprism-app/docker-entrypoint.sh"]
