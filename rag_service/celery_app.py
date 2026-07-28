from celery import Celery
from rag_service.settings import settings

celery_app = Celery(
    "rag_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
# `include=["rag_service.workers.task"]` не задаём здесь: этот модуль импортируется и
# rag-service (API, лёгкий образ без Docling/torch), и rag-worker - если бы include
# был в конфиге, простой импорт celery_app тянул бы rag_service.workers.task, а тот -
# rag_service.worker_container (Docling). Продюсер (rag-service) ставит задачи по
# имени через send_task() и модуль воркера не импортирует вообще (см.
# TaskDispatcherService). Сам rag-worker получает модуль явным `--include=` в команде
# запуска (docker-compose.full.yml, сервис rag-worker) - это единственный процесс,
# которому нужно реально ИСПОЛНЯТЬ задачи, а не просто их ставить в очередь.

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