"""Celery uygulaması: broker/result = Redis. Worker tasks'i, beat zamanlamayı yükler."""
from celery import Celery
from celery.schedules import crontab

from .config import settings

celery = Celery(
    "isler",
    broker=settings.APP_REDIS_URL,
    backend=settings.APP_REDIS_URL,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Istanbul",
    enable_utc=True,
    task_soft_time_limit=settings.JOB_SOFT_TIME_LIMIT,
    task_time_limit=settings.JOB_TIME_LIMIT,
    task_track_started=True,
)

# Beat zamanlaması:
# - Her gün 06:00'da incremental ingest (tüm kaynaklar)
# - Her dakika DB job zamanlamalarını (cron) kontrol eden dağıtıcı
celery.conf.beat_schedule = {
    "daily-ingest": {
        "task": "app.tasks.ingest_logo",
        "schedule": crontab(hour=6, minute=0),
        "kwargs": {"sources": None, "mode": "incremental", "triggered_by": "beat"},
    },
    "job-scheduler-tick": {
        "task": "app.tasks.tick_scheduler",
        "schedule": crontab(minute="*"),
    },
}

# Task tanımlarını yükle
celery.autodiscover_tasks(["app"])
from . import tasks  # noqa: E402,F401
