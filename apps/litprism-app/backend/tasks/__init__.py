import tasks.enrichment  # noqa: F401
import tasks.fulltext  # noqa: F401
import tasks.screening  # noqa: F401
from tasks.celery_app import celery_app

__all__ = ["celery_app"]
