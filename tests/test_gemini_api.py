import os
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))

from app.services.gemini_service import GeminiService


def test_gemini():
    response = GeminiService.generate_text("Объясни теорию относительности")
    assert isinstance(response, str), "Ответ должен быть строкой"
    print("Тест пройден! Ответ Gemini:")
    print(response)

if __name__ == "__main__":
    test_gemini()