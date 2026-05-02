redis:    redis-server
web:      cd apps/litprism-app/backend && uv run uvicorn main:app --reload --port 8000
worker:   cd apps/litprism-app/backend && PYTHONPATH=$(pwd) uv run celery -A tasks worker --loglevel=info
beat:     cd apps/litprism-app/backend && PYTHONPATH=$(pwd) uv run celery -A tasks.celery_app beat --loglevel=info
frontend: cd apps/litprism-app/frontend && npm run dev
