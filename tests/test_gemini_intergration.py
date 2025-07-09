import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(str(Path(__file__).parent.parent))

from app.services.gemini_service import GeminiService

def test_gemini_integration():
    service = GeminiService()
    test_prompt = "Объясни квантовую физику простыми словами"
    
    response = service.generate_text(test_prompt)
    assert response and len(response) > 10, "Должен вернуться осмысленный ответ"
    print("Тест пройден. Ответ:", response[:100] + "...")

if __name__ == "__main__":
    test_gemini_integration()