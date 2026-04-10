# rag_service/providers/LLM_provider.py
from __future__ import annotations


from typing import Protocol



SYSTEM_PROMPT = """Ты — профессиональный ассистент, специализирующийся на технической документации.
Твоя задача — извлечь ответ на заданный вопрос из предоставленного ниже контекста.

Правила:
1) Язык ответа: всегда отвечай по-русски.
2) Строгость: используй только информацию из контекста.
3) Если ответа нет: ответь только фразой: "В предоставленном контексте ответа нет."
4) Формат: выведи только текст ответа, без вступлений."""

USER_TEMPLATE = """КОНТЕКСТ:
---
{context}
---

ВОПРОС: {question}"""






class LLMProvider(Protocol):
    async def generate(self, *, query: str, context: str) -> str: ...


class GeminiLLMProvider:
    def __init__(self, *, api_key: str, model: str = "gemini-2.0-flash"):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(
            model_name=model,
            system_instruction="Отвечай только на основе переданного контекста. Если ответа нет — скажи об этом."
        )

    async def generate(self, *, query: str, context: str) -> str:
        if not context.strip():
            return "Релевантный контекст не найден."
        prompt = f"Контекст:\n{context}\n\nВопрос: {query}"
        response = await self._model.generate_content_async(prompt)
        return response.text or ""


class GroqLLMProvider:
    def __init__(self, *, api_key: str, model: str = "llama-3.3-70b-versatile"):
        from groq import AsyncGroq
        self._client = AsyncGroq(api_key=api_key)
        self._model = model

    async def generate(self, *, query: str, context: str) -> str:
        if not context.strip():
            return "Релевантный контекст не найден."

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(context=context, question=query)},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

