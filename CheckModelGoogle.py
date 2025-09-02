import google.generativeai as genai
import os

# Используем API-ключ, который ты уже вставил
API_KEY = "AIzaSyBnZJIbKU_EBreWAtpdFlRbBNlKs-s0bCw"
genai.configure(api_key=API_KEY)

print("Доступные модели:")
for m in genai.list_models():
    # Проверим, можно ли использовать модель для генерации контента
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)