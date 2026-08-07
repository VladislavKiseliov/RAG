"""Диагностика prompt caching у текущего LLM-шлюза (LLM_BASE_URL/LLM_PROVIDER в .env).

Запускать руками (не часть pytest-сюиты, тратит реальные токены/деньги, копейки) -
особенно полезно после смены модели/провайдера в ai_config.toml или .env, чтобы
заново проверить, действительно ли повторяющийся системный промпт кэшируется.

Шлёт 3 запроса с ИДЕНТИЧНЫМ длинным system-префиксом (>1500 токенов) и разными
последними user-репликами, плюс контрольный запрос с ДРУГИМ префиксом. Печатает
сырой usage каждого ответа - если у шлюза есть кэширование в духе OpenAI
(prompt_tokens_details.cached_tokens), должно быть видно по разнице между
холодным и тёплым вызовом. На 2026-08-07 (gatellm.ru, openai/gpt-oss-120b)
проверено вживую: поле есть, но кэш-хиты (~65 токенов) не зависят от того,
совпадает ли префикс реально - реальной экономии не даёт, см. память сессии.

Запуск из корня репозитория: python -m llm_service.manual_tests.prompt_cache_check_manual
"""
from __future__ import annotations

import asyncio
import sys

from llm_service.ai_config import get_live_config
from llm_service.settings import settings

# Синтетический повторяющийся текст - нужен только чтобы стабильный префикс
# гарантированно перевалил за типовой порог кэширования (обычно ~1024 токена).
_FILLER_PARAGRAPH = (
    "Это тестовый синтетический текст для диагностики кэширования промптов у "
    "внешнего LLM-шлюза. Он специально длинный, повторяющийся и не несёт "
    "смысловой нагрузки - нужен только для того, чтобы стабильный префикс "
    "запроса гарантированно превысил минимальный порог кэширования, который "
    "у большинства провайдеров составляет около тысячи токенов. "
)
_LONG_SYSTEM_PROMPT = "Ты технический ассистент. " + (_FILLER_PARAGRAPH * 40)


async def _call(client, model: str, label: str, system_prompt: str, user_msg: str) -> dict | None:
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=5,
        temperature=0,
    )
    usage = response.usage.model_dump() if response.usage else None
    print(f"--- {label} ---")
    print("usage:", usage)
    print()
    return usage


async def main() -> None:
    from openai import AsyncOpenAI

    config = get_live_config()
    model = config.llm.model_name
    client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL, timeout=60.0)

    print(f"MODEL={model}")
    print(f"BASE_URL={settings.LLM_BASE_URL}")
    print()

    u1 = await _call(client, model, "Запрос 1 (холодный, длинный system-префикс)",
                      _LONG_SYSTEM_PROMPT, "Ответь одним словом: привет")
    u2 = await _call(client, model, "Запрос 2 (тот же system-префикс, другой вопрос)",
                      _LONG_SYSTEM_PROMPT, "Ответь одним словом: пока")
    u3 = await _call(client, model, "Запрос 3 (другой system-префикс, контроль)",
                      _LONG_SYSTEM_PROMPT[::-1], "Ответь одним словом: тест")

    await client.close()

    print("=== Сводка cached_tokens (prompt_tokens_details) ===")
    for label, u in [("1 холодный", u1), ("2 тёплый (тот же префикс)", u2), ("3 контроль (другой префикс)", u3)]:
        cached = (u or {}).get("prompt_tokens_details", {}).get("cached_tokens")
        print(f"{label}: cached_tokens={cached}, prompt_tokens={(u or {}).get('prompt_tokens')}")

    print()
    print("Если cached_tokens во 2-м запросе заметно больше, чем в 1-м и 3-м -")
    print("кэш реально ловит совпадающий префикс. Если 2 и 3 близки друг к другу -")
    print("как было с gatellm.ru 2026-08-07 - кэш не зависит от контента, реальной")
    print("экономии не даёт.")


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
