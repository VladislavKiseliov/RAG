from __future__ import annotations

import asyncio
import os

from llm_service.LLM_provider import OpenAICompatLLMProvider
from llm_service.promt.promts import ANALIZE_NODE_PROMT


TEST_QUESTIONS = [
    "Как класифицируют документы в области ИБ",
    "Что содержит в себе оценка информационных рисков",
    "На что направленно проведение мониторинга деятельности ОИБ",
    "Как осуществляетСя анализ эффективности ОИБ",
    "Какие решения принимаются по результатам анализа",
    "Что включают в себя процедуры по обеспечению превентивных мер",
    "Где найти фининсовую деятельность по оИБ",
    "Что такое газ",
    "Привет мне нужна помощь",
    " Основанием для отказа к приему объекта",
]

TEST_SUMMARY = "пока пусто"


async def main() -> None:
    llm_provider = OpenAICompatLLMProvider(
        base_url=os.getenv("LLM_BASE_URL", "https://gatellm.ru/v1"),
        model=os.getenv("LLM_MODEL", "qwen/qwen3.5-9b"),
    )

    for index, question in enumerate(TEST_QUESTIONS, start=1):
        prompt = ANALIZE_NODE_PROMT.format(
            context=TEST_SUMMARY,
            query=question,
        )
        response = await llm_provider.generate_general(query=prompt, context="")

        print(f"[{index}] ВОПРОС: {question}")
        print(f"[{index}] ОТВЕТ: {response}")
        print("-" * 80)


if __name__ == "__main__":
    asyncio.run(main())
