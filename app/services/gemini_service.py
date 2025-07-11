import aiohttp
import logging
import traceback
import asyncio
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        logger.debug(f"Initializing GeminiService with model: {settings.GEMINI_MODEL}")
        # Store API key securely without logging it
        self.api_url = f"https://generativelanguage.googleapis.com/v1/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"

    def _post_process_text(self, text: str) -> str:
        """Постобработка текста от Gemini: удаление звездочек и очистка форматирования"""
        if not text:
            return text
            
        # Удаляем все звездочки (используемые для markdown форматирования)
        cleaned_text = text.replace('*', '')
        
        return cleaned_text

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_text_async(self, prompt: str) -> Optional[str]:
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
                    
                    # Упрощенная обработка ответа
                    if "candidates" in data and data["candidates"]:
                        text = data['candidates'][0]['content']['parts'][0]['text']
                        
                        # Применяем постобработку для удаления звездочек
                        cleaned_text = self._post_process_text(text)
                        
                        logger.debug(f"Gemini response text (cleaned): {cleaned_text[:100]}...")
                        return cleaned_text
                    
                    logger.warning(f"Unexpected Gemini response: {data}")
                    return None
                    
        except Exception as e:
            logger.error(f"Gemini API error: {e}\n{traceback.format_exc()}")
            return None

    def generate_text(self, prompt: str) -> Optional[str]:
        """Синхронная версия для совместимости с тестами"""
        try:
            return asyncio.run(self.generate_text_async(prompt))
        except RuntimeError:
            # Если есть проблемы с event loop, используем простую обертку
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, 
                    self.generate_text_async(prompt)
                )
                return future.result(timeout=60)