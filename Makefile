.PHONY: test lint format check install dev

# Install all packages in dev mode
install:
	uv sync --all-packages

# Run all tests
test:
	uv run pytest packages/ -v

# Run tests for a specific package
test-pubmed:
	uv run pytest packages/litprism-pubmed/tests/ -v

test-screen:
	uv run pytest packages/litprism-screen/tests/ -v

# Lint + format check
lint:
	uv run ruff check packages/ apps/
	uv run ruff format --check packages/ apps/

# Auto-fix formatting
format:
	uv run ruff check --fix packages/ apps/
	uv run ruff format packages/ apps/

# Full check (what CI runs)
check: lint test

# Run the FastAPI backend locally
dev-backend:
	cd apps/litprism-app/backend && \
	uv run uvicorn main:app --reload --port 8000

# Run Celery worker locally
dev-worker:
	cd apps/litprism-app/backend && \
	uv run celery -A services.pipeline worker --loglevel=info

# Run frontend locally
dev-frontend:
	cd apps/litprism-app/frontend && \
	npm run dev

# Run database migrations
migrate:
	cd apps/litprism-app/backend && \
	uv run alembic upgrade head

# Generate a new migration
migration msg="":
	cd apps/litprism-app/backend && \
	uv run alembic revision --autogenerate -m "$(msg)"
