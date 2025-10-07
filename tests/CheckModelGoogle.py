# import google.generativeai as genai
# import os
#
# # Используем API-ключ, который ты уже вставил
# API_KEY = "AIzaSyBnZJIbKU_EBreWAtpdFlRbBNlKs-s0bCw"
# genai.configure(api_key=API_KEY)
#
# print("Доступные модели:")
# for m in genai.list_models():
#     # Проверим, можно ли использовать модель для генерации контента
#     if 'generateContent' in m.supported_generation_methods:
#         print(m.name)


import google.generativeai as genai
import os

# Используем API-ключ, который ты уже вставил
API_KEY = "AIzaSyBrRGLpcfEL0QC9SiQFI0_axfi4T7BRQC0"
genai.configure(api_key=API_KEY)

print("Доступные модели:")
try:
    for m in genai.list_models():
        # Проверим, можно ли использовать модель для генерации контента
        if hasattr(m, 'supported_generation_methods') and 'generateContent' in m.supported_generation_methods:
            print(m.name)
except TypeError as e:
    print(f"Ошибка совместимости библиотеки: {e}")
    print("Попробуем использовать стандартные модели:")
    # Перечислим известные рабочие модели
    known_models = [
        "gemini-1.0-pro",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-pro",
        "gemini-pro-vision"
    ]
    for model in known_models:
        print(f"- {model}")