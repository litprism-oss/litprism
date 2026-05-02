from celery import Celery
from config import settings

celery_app = Celery(
    "litprism",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.beat_schedule = {
    "watchdog-every-3-minutes": {
        "task": "tasks.watchdog.watchdog",
        "schedule": 180.0,
    },
}
