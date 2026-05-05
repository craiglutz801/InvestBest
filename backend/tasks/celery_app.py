"""
Celery app for background jobs. Use with: celery -A backend.tasks.celery_app worker -l info
"""
from celery import Celery
from config.settings import get_settings

settings = get_settings()
app = Celery(
    "investbest",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["backend.tasks.data_jobs", "backend.tasks.signal_jobs"],
)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
