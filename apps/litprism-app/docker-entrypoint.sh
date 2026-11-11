#!/bin/sh
# One image, two roles. Container Apps sets LITPRISM_ROLE per app.
#   api    -> FastAPI via uvicorn (default)
#   worker -> Celery worker with the beat scheduler embedded (-B).
#             Run exactly one worker replica, or the scheduler fires twice.
set -e

case "${LITPRISM_ROLE:-api}" in
  api)
    exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  worker)
    exec celery -A tasks worker -B --loglevel=info --concurrency="${CELERY_CONCURRENCY:-2}"
    ;;
  *)
    echo "Unknown LITPRISM_ROLE: ${LITPRISM_ROLE}" >&2
    exit 1
    ;;
esac
