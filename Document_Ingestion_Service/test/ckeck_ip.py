import requests

proxy_port = "12334"
proxies = {
    'http': f'http://127.0.0.1:{proxy_port}',
    'https': f'http://127.0.0.1:{proxy_port}',
}

try:
    # Важно: используем https, так как Gemini работает через него
    response = requests.get('https://ifconfig.me', proxies=proxies, timeout=10)
    print(f"ПОБЕДА! Твой внешний IP: {response.text}")
except Exception as e:
    print(f"Всё еще не выходит. Ошибка: {e}")

import os
from langchain_google_genai import ChatGoogleGenerativeAI

# --- НАСТРОЙКИ ---
# Указываем прокси, который мы нашли (Mixed Port v2rayN)
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:12334'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:12334'

LLM_MODEL_NAME = "models/gemini-2.5-flash-lite"
_llm_client = None


def _get_llm_client() -> ChatGoogleGenerativeAI:
    global _llm_client
    if _llm_client is not None:
        return _llm_client

    # Твой ключ (лучше потом вынести в .env)
    api_key = "AIzaSyBrRGLpcfEL0QC9SiQFI0_axfi4T7BRQC0"

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    # Инициализируем клиент
    _llm_client = ChatGoogleGenerativeAI(
        model=LLM_MODEL_NAME,
        google_api_key=api_key,
        temperature=0.7  # добавим немного креативности
    )
    return _llm_client


def main():
    print("=== Gemini CLI Chat Started ===")
    print("(Напиши 'exit' или 'quit' для выхода)\n")

    llm = _get_llm_client()

    while True:
        try:
            # Получаем ввод от пользователя
            user_input = input("Я: ")

            if user_input.lower() in ['exit', 'quit', 'выход']:
                print("Пока!")
                break

            if not user_input.strip():
                continue

            # Отправляем запрос модели
            # В LangChain это делается через метод .invoke()
            print("Gemini думает...", end="\r")
            response = llm.invoke(user_input)

            # Выводим ответ
            print(f"Gemini: {response.content}\n")

        except KeyboardInterrupt:
            print("\nПрервано пользователем.")
            break
        except Exception as e:
            print(f"\nОшибка: {e}")

main()
