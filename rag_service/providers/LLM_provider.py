from typing import Protocol
import google.generativeai as genai

class LLMProvider(Protocol):
    """Abstraction over answer generation from question + retrieved context."""

    async def generate(self, *, query: str, context: str) -> str:
        """Generate answer text for query based on provided context."""
        ...


class GeminiLLMProvider:
    def __init__(self, *, api_key: str, model: str = "gemini-2.0-flash"):
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