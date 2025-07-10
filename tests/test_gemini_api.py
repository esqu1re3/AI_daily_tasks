# test_gemini.py
# import google.generativeai as genai

# def test_gemini():
#     genai.configure(api_key="ВАШ_API_КЛЮЧ")  # Лучше вынести в .env
#     model = genai.GenerativeModel('gemini-pro')
#     response = model.generate_content("Привет! Как дела?")
#     print(response.text)

# if __name__ == "__main__":
#     test_gemini()

# # test_gemini.py
# from app.services.gemini_service import GeminiService

# def test_gemini():
#     service = GeminiService()
#     response = service.generate_text("Объясни теорию относительности")
#     print(response)

# if __name__ == "__main__":
#     test_gemini()

import os
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))

from app.services.gemini_service import GeminiService

def test_gemini():
    service = GeminiService()
    response = service.generate_text("Объясни теорию относительности")
    assert isinstance(response, str), "Ответ должен быть строкой"
    print("Тест пройден! Ответ Gemini:")
    print(response)

if __name__ == "__main__":
    test_gemini()
