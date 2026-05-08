import operator
import asyncio
import os
from typing import Annotated, List, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

# Импортируем твой реальный провайдер
from llm_service.LLM_provider import OpenAICompatLLMProvider


# --- 1. ОПРЕДЕЛЕНИЕ СОСТОЯНИЯ (State) ---

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    summary: str
    context: List[str]


# --- 2. ИНИЦИАЛИЗАЦИЯ ТВОЕЙ МОДЕЛИ ---

# Оставляем твою реальную модель
llm_provider = OpenAICompatLLMProvider(
    base_url=os.getenv("LLM_BASE_URL", "https://gatellm.ru/v1"),
    model=os.getenv("LLM_MODEL", "qwen/qwen3.5-9b")
)


# --- 3. УЗЛЫ ГРАФА (Nodes) ---

async def retrieve_node(state: AgentState):
    """ЗАГЛУШКА ретривера (чтобы не зависеть от БД)"""
    print(" [LOG] Ретривер: имитация поиска...")
    last_query = state["messages"][-1].content
    return {"context": [f"Техническая выжимка по запросу: {last_query}"]}


async def call_model_node(state: AgentState):
    """РЕАЛЬНЫЙ ВЫЗОВ твоей модели"""
    print(" [LOG] LLM: генерация ответа через твой провайдер...")

    # Готовим историю для твоего метода
    formatted_history = []
    for m in state["messages"]:
        role = "user" if isinstance(m, HumanMessage) else "assistant"
        formatted_history.append({"role": role, "content": m.content})

    # Формируем контекст (Саммари + Ретрив)
    full_context = f"Сводка истории: {state['summary']}\n\nКонтекст: " + "\n".join(state["context"])

    # Твой реальный метод generate
    answer = await llm_provider.generate(
        query=state["messages"][-1].content,  # последний вопрос
        context=full_context
    )

    return {"messages": [AIMessage(content=answer)]}


async def summarize_node(state: AgentState):
    """ЗАГЛУШКА суммаризатора (простая имитация)"""
    print(" [LOG] Суммаризатор: имитация сжатия памяти...")
    return {"summary": "В истории обсудили настройку ШИМ и ПЛК."}


# --- 4. ЛОГИКА ПЕРЕХОДОВ ---

def should_summarize(state: AgentState):
    # Если сообщений больше 2 (вопрос + ответ), идем в суммаризатор
    if len(state["messages"]) > 2:
        return "summarize"
    return "end"


# --- 5. СБОРКА ГРАФА ---

workflow = StateGraph(AgentState)

workflow.add_node("retriever", retrieve_node)
workflow.add_node("agent", call_model_node)
workflow.add_node("summarizer", summarize_node)

workflow.set_entry_point("retriever")
workflow.add_edge("retriever", "agent")

workflow.add_conditional_edges(
    "agent",
    should_summarize,
    {
        "summarize": "summarizer",
        "end": END
    }
)
workflow.add_edge("summarizer", END)

app = workflow.compile()


# --- 6. ЗАПУСК ---

async def main():
    print("--- СТАРТ СИСТЕМЫ (Ретрив/Суммари - заглушки, Модель - реальная) ---")

    inputs = {
        "messages": [HumanMessage(content="Как настроить ШИМ на STM32?")],
        "summary": "Пользователь — программист ПЛК.",
        "context": []
    }

    try:
        final_state = await app.ainvoke(inputs)
        print("\n--- ФИНАЛЬНЫЙ ОТВЕТ ТВОЕЙ МОДЕЛИ ---")
        print(final_state["messages"][-1].content)
        print(f"\n--- ТЕКУЩЕЕ САММАРИ ---")
        print(final_state["summary"])
    except Exception as e:
        print(f"\n [!] Ошибка при вызове твоей модели: {e}")


if __name__ == "__main__":
    asyncio.run(main())