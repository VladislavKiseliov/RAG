import os
import google.generativeai as genai

# Не забываем про прокси, если ты в РФ
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:12334'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:12334'

# Твой ключ
api_key = "AIzaSyBrRGLpcfEL0QC9SiQFI0_axfi4T7BRQC0"
genai.configure(api_key=api_key)

print("Список доступных моделей:")
print("-" * 30)

try:
    for m in genai.list_models():
        # Фильтруем только те, что умеют генерировать текст (generateContent)
        if 'generateContent' in m.supported_generation_methods:
            print(f"Имя: {m.name}")
            print(f"Версия: {m.version}")
            print(f"Описание: {m.description}")
            print("-" * 30)
except Exception as e:
    print(f"Ошибка при получении списка: {e}")