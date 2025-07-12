import aiohttp
import logging
import traceback
import asyncio
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    """Сервис для работы с Google Gemini API.
    
    Обеспечивает генерацию текстов, анализ качества ответов и постобработку.
    Поддерживает ретраи и асинхронные вызовы для надежности.
    
    Attributes:
        api_url: URL эндпоинта Gemini API с моделью и ключом.
    
    Examples:
        >>> gemini = GeminiService()
        >>> response = gemini.generate_text("Hello")
    """
    def __init__(self):
        """Инициализирует сервис Gemini.
        
        Выполняет следующие действия:
        1. Формирует URL для обращения к Gemini API с учетом модели и ключа
        2. Логирует инициализацию
        
        Args:
            Нет
        
        Returns:
            None
        
        Examples:
            >>> service = GeminiService()
        """
        logger.debug(f"Initializing GeminiService with model: {settings.GEMINI_MODEL}")
        self.api_url = f"https://generativelanguage.googleapis.com/v1/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"

    def _post_process_text(self, text: str) -> str:
        """Постобрабатывает текст, полученный от Gemini API.
        
        Выполняет следующие действия:
        1. Проверяет, что текст не пустой
        2. Удаляет все символы '*' (звездочки, используемые для markdown)
        3. Возвращает очищенный текст
        
        Args:
            text (str): Исходный текст от Gemini
        
        Returns:
            str: Очищенный текст без звездочек
        
        Examples:
            >>> _post_process_text('**Hello**')
            'Hello'
        """
        if not text:
            return text
        cleaned_text = text.replace('*', '')
        return cleaned_text

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_text_async(self, prompt: str) -> Optional[str]:
        """Асинхронно отправляет промпт в Gemini и возвращает сгенерированный текст.
        
        Выполняет следующие действия:
        1. Формирует payload и заголовки
        2. Отправляет POST-запрос к Gemini API
        3. Обрабатывает ответ, извлекает текст
        4. Применяет постобработку
        5. Возвращает результат или None при ошибке
        
        Args:
            prompt (str): Текст запроса для генерации
        
        Returns:
            Optional[str]: Сгенерированный текст или None при ошибке
        
        Raises:
            Может выбросить исключение при сетевых ошибках (обрабатывается retry)
        
        Examples:
            >>> await service.generate_text_async('Привет!')
            'Здравствуйте! Чем могу помочь?'
        """
        logger.debug(f"Sending to Gemini: {prompt[:50]}...")
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    data = await response.json()
                    logger.debug(f"Gemini raw response: {str(data)[:200]}")
                    if "candidates" in data and data["candidates"]:
                        text = data['candidates'][0]['content']['parts'][0]['text']
                        cleaned_text = self._post_process_text(text)
                        logger.debug(f"Gemini response text (cleaned): {cleaned_text[:100]}...")
                        return cleaned_text
                    logger.warning(f"Unexpected Gemini response: {data}")
                    return None
        except Exception as e:
            logger.error(f"Gemini API error: {e}\n{traceback.format_exc()}")
            return None

    async def analyze_response_quality_async(self, response_text: str) -> dict:
        """Анализирует качество ответа пользователя через Gemini AI.
        
        Выполняет следующие действия:
        1. Формирует промпт для анализа качества
        2. Отправляет промпт в Gemini
        3. Парсит результат и возвращает структуру с оценкой
        4. При ошибке или невозможности анализа — принимает ответ
        
        Args:
            response_text (str): Текст ответа пользователя для анализа
        
        Returns:
            dict: {
                "is_acceptable": bool,  # Принимается ли ответ
                "feedback": str,        # Обратная связь для пользователя
                "reason": str           # Причина отклонения (если отклонен)
            }
        
        Examples:
            >>> await service.analyze_response_quality_async('Работаю')
            {'is_acceptable': False, 'feedback': 'Ответ слишком общий...', 'reason': 'too_vague'}
        """
        if not response_text or len(response_text.strip()) < 5:
            return {
                "is_acceptable": False,
                "feedback": "🤔 Ваш ответ слишком краткий. Пожалуйста, опишите более подробно, над какими конкретными задачами вы планируете работать.",
                "reason": "too_short"
            }
        prompt = f"""
Проанализируй качество ответа сотрудника на вопрос о рабочих планах на день.

Ответ сотрудника: "{response_text}"

Критерии качественного ответа:
- Конкретность (указаны конкретные задачи, проекты, действия)
- Информативность (понятно, чем будет заниматься)
- Достаточная детализация (не односложные ответы)

ТРЕБУЕТСЯ ТОЧНЫЙ ФОРМАТ ОТВЕТА:
ACCEPTABLE: да/нет
FEEDBACK: [краткая обратная связь для пользователя]
REASON: [причина, если неприемлемо: too_short/too_vague/not_specific/off_topic]

Примеры:

Хороший ответ: "Доделываю модуль авторизации, тестирую API платежей, встреча с дизайнером по новому интерфейсу"
ACCEPTABLE: да
FEEDBACK: Отличный план! Все задачи конкретны и понятны.
REASON: -

Плохой ответ: "Работаю"
ACCEPTABLE: нет  
FEEDBACK: Ответ слишком общий. Укажите конкретные задачи или проекты.
REASON: too_vague

Плохой ответ: "да"
ACCEPTABLE: нет
FEEDBACK: Слишком краткий ответ. Опишите ваши планы подробнее.
REASON: too_short
"""
        try:
            analysis_result = await self.generate_text_async(prompt)
            if not analysis_result:
                return {
                    "is_acceptable": True,
                    "feedback": "✅ Ваш план принят!",
                    "reason": "gemini_unavailable"
                }
            lines = analysis_result.strip().split('\n')
            acceptable = None
            feedback = ""
            reason = ""
            for line in lines:
                line = line.strip()
                if line.startswith('ACCEPTABLE:'):
                    acceptable_text = line.replace('ACCEPTABLE:', '').strip().lower()
                    acceptable = acceptable_text in ['да', 'yes', 'true']
                elif line.startswith('FEEDBACK:'):
                    feedback = line.replace('FEEDBACK:', '').strip()
                elif line.startswith('REASON:'):
                    reason = line.replace('REASON:', '').strip()
            if acceptable is None:
                return {
                    "is_acceptable": True,
                    "feedback": "✅ Ваш план принят!",
                    "reason": "parse_error"
                }
            return {
                "is_acceptable": acceptable,
                "feedback": feedback if feedback else ("✅ Отличный план!" if acceptable else "🤔 Пожалуйста, уточните ваш план."),
                "reason": reason if not acceptable else ""
            }
        except Exception as e:
            logger.error(f"Ошибка анализа качества ответа: {e}")
            return {
                "is_acceptable": True,
                "feedback": "✅ Ваш план принят!",
                "reason": "analysis_error"
            }

    def analyze_response_quality(self, response_text: str) -> dict:
        """Синхронно анализирует качество ответа пользователя через Gemini AI.
        
        Выполняет следующие действия:
        1. Запускает асинхронную функцию анализа качества через event loop
        2. При ошибке event loop — использует ThreadPoolExecutor
        3. Возвращает результат анализа
        
        Args:
            response_text (str): Текст ответа пользователя для анализа
        
        Returns:
            dict: Результат анализа качества (см. analyze_response_quality_async)
        
        Examples:
            >>> service.analyze_response_quality('Работаю')
            {'is_acceptable': False, ...}
        """
        try:
            return asyncio.run(self.analyze_response_quality_async(response_text))
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, 
                    self.analyze_response_quality_async(response_text)
                )
                return future.result(timeout=30)

    def generate_text(self, prompt: str) -> Optional[str]:
        """Синхронно отправляет промпт в Gemini и возвращает сгенерированный текст.
        
        Выполняет следующие действия:
        1. Запускает асинхронную функцию генерации текста через event loop
        2. При ошибке event loop — использует ThreadPoolExecutor
        3. Возвращает результат генерации
        
        Args:
            prompt (str): Текст запроса для генерации
        
        Returns:
            Optional[str]: Сгенерированный текст или None при ошибке
        
        Examples:
            >>> service.generate_text('Привет!')
            'Здравствуйте! Чем могу помочь?'
        """
        try:
            return asyncio.run(self.generate_text_async(prompt))
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, 
                    self.generate_text_async(prompt)
                )
                return future.result(timeout=60)