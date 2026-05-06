# tasks.py

import uuid
import asyncio

from rag_service.api.schemas import DocumentStatus
from rag_service.celery_app import celery_app
from rag_service.infrastructure import  get_worker_container


# один loop на весь воркер
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)


@celery_app.task(name="ingest_document", bind=True, max_retries=3)
def ingest_document_task(self, doc_id: uuid.UUID, s3key: str):
    # Получаем контейнер (создастся только один раз на процесс воркера)
    container = get_worker_container()

    async def _run():
        # Используем наш оркестратор/менеджер
        await container.ingestion_service.process_document(
            doc_id=doc_id,
            s3key=s3key,
        )

    try:
        _loop.run_until_complete(_run())
    except Exception as exc:
        # При ошибке обновляем статус через сервис из контейнера
        _loop.run_until_complete(
            container.document_service.update_document(
                doc_id=doc_id,
                status=DocumentStatus.ERROR,
            )
        )
        raise self.retry(exc=exc, countdown=60)


# import logging
# from celery import Celery
# from tenacity import retry, stop_after_attempt, wait_exponential
#
# # Настройка Celery (обычно через Redis или RabbitMQ)
# app = Celery('document_tasks', broker='redis://localhost:6379/0')
#
# logger = logging.getLogger(__name__)
#
#
# class DatabaseError(Exception): """Ошибка БД"""
#
#
# pass
#
#
# class S3Error(Exception): """Ошибка S3"""
#
#
# pass
#
#
# class VectorDBError(Exception): """Ошибка Vector DB"""
#
#
# pass
#
#
# @app.task(
#     bind=True,
#     autoretry_for=(DatabaseError, S3Error, VectorDBError),  # На какие ошибки реагировать
#     retry_backoff=True,  # Экспоненциальная задержка (1s, 2s, 4s, 8s...)
#     retry_backoff_max=600,  # Максимальная пауза (10 минут)
#     max_retries=5,  # Сколько раз пытаться перед тем как сдаться
#     name='tasks.delete_document_completely'
# )
# def delete_document_completely(self, doc_id, s3_key):
#     """
#     Фоновая задача для полной очистки документа из всех систем.
#     Использует механизм гарантированного выполнения Celery.
#     """
#
#     # 1. Очистка Vector DB
#     # Делаем это одним из первых, так как это часто самая нагруженная часть
#     try:
#         # Здесь логика удаления из Vector DB (например, Qdrant или Pinecone)
#         # print(f"Removing vectors for {doc_id}...")
#         pass
#     except Exception as e:
#         logger.error(f"Vector DB failed for {doc_id}: {e}")
#         raise VectorDBError(e)
#
#     # 2. Удаление файла из S3
#     try:
#         if s3_key:
#             # print(f"Deleting file {s3_key} from S3...")
#             # Важно: удаление из S3 обычно идемпотентно (если файла нет, ошибки нет)
#             pass
#     except Exception as e:
#         logger.error(f"S3 deletion failed for {s3_key}: {e}")
#         raise S3Error(e)
#
#     # 3. Удаление записи из SQL
#     try:
#         # print(f"Deleting record {doc_id} from SQL...")
#         # Выполняем в самом конце, чтобы не потерять ID задачи при сбоях выше
#         pass
#     except Exception as e:
#         logger.error(f"SQL deletion failed for {doc_id}: {e}")
#         raise DatabaseError(e)
#
#     return f"Document {doc_id} successfully deleted from all storages."