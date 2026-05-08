from typing import List, Dict

import httpx
import os
from fastapi import HTTPException
from backend.utils.logger_config import setup_logger

logger = setup_logger("backend.llm_client")

# Указываем адрес именно LLM-сервиса
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://llm-service:8002")


async def get_llm_answer(question: str,history_massage:List[Dict],summary:str) -> dict:
    """
    Отправляет запрос в LLM-сервис.
    LLM-сервис сам сходит в RAG, сформирует контекст и вернет готовый ответ.
    """
    if not LLM_SERVICE_URL:
        logger.error("LLM_SERVICE_URL не настроен в переменных окружения")
        raise HTTPException(status_code=500, detail="Ошибка конфигурации сервиса LLM")

    # Формируем чистый URL к эндпоинту LLM
    url = f"{LLM_SERVICE_URL.rstrip('/')}/llm/answer"
    payload = {"query": question,"history_massage":history_massage,"summary":summary}

    # Используем AsyncClient с увеличенным таймаутом
    # (LLM + RAG запрос может занимать много времени)
    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=5.0)) as client:
        logger.info(f"Запрос к LLM сервису: {url}", extra={"query": question})

        try:
            response = await client.post(url, json=payload)

            # Если LLM-сервис вернул 4xx или 5xx, httpx выбросит исключение
            response.raise_for_status()

            data = response.json()

            # Возвращаем структуру, которую прислал LLM сервис
            return {
                "answer": data.get("answer", "Ответ не получен"),
                "sources": data.get("sources", [])
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM сервис вернул ошибку {e.response.status_code}",
                         extra={"body": e.response.text})
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Ошибка LLM сервиса: {e.response.text}"
            )

        except httpx.RequestError as e:
            logger.error(f"Ошибка сети при обращении к LLM: {str(e)}")
            raise HTTPException(
                status_code=502,
                detail="Сервис LLM временно недоступен"
            )