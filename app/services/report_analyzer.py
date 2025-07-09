from app.services.gemini_service import GeminiService

class ReportAnalyzer:
    def __init__(self):
        self.gemini = GeminiService()

    def analyze_report(self, report_text: str) -> dict:
        prompt = f"""Проанализируй отчет и выдели:
        1. Ключевые показатели
        2. Проблемные места
        3. Рекомендации

        Отчет: {report_text}
        """
        
        analysis = self.gemini.generate_text(prompt)
        return {
            "analysis": analysis,
            "status": "success" if analysis else "error"
        }