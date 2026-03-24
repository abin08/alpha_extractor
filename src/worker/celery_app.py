import os

from celery import Celery

# Grab the Redis URL injected by our Kubernetes Secret
broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "alpha_extractor",
    broker=broker_url,
    backend=broker_url,
)

# Standard sensible defaults
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    enable_utc=True,
)


@celery_app.task
def health_check():
    return "Celery worker is alive and connected to Redis!"
