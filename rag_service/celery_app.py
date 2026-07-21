from celery import Celery
from rag_service.settings import settings

celery_app = Celery(
    "rag_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["rag_service.workers.task"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_pool="solo",  # ← для Windows
    # Без этих двух Flower не видит ни одной задачи вообще — по умолчанию Celery не шлёт
    # событий: воркер не репортит started/succeeded/failed, а продюсер (.delay()) не шлёт
    # sent-событие, из-за чего задачи не видны даже в очереди до того, как их подхватит воркер.
    worker_send_task_events=True,
    task_send_sent_event=True,
)