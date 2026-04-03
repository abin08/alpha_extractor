from celery import Celery

from src.core.config import settings

# 1. Initialize the Celery application
celery_app = Celery(
    "alpha_extractor",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# 2. Enterprise-grade Configuration
celery_app.conf.update(
    # Strict JSON serialization for security (never use pickle!)
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone settings (Aligning with NSE market hours)
    timezone="Asia/Kolkata",
    enable_utc=True,
    # Resilience & Resource Tuning
    task_acks_late=True,  # Acknowledge task ONLY after successful completion
    task_reject_on_worker_lost=True,  # Re-queue tasks if a worker container crashes
    worker_prefetch_multiplier=1,  # Stop fast workers from hoarding long I/O tasks
    task_track_started=True,
    # Task module registration (we will uncomment these in AE22 and AE23)
    imports=[
        "src.tasks.workers.ingest_tasks",
        # "src.tasks.workers.ai_tasks",
    ],
)


@celery_app.task
def health_check():
    return "Celery worker is alive and connected to Redis!"


if __name__ == "__main__":
    celery_app.start()
