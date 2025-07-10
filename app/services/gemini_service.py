# import aiohttp
# import logging
# from typing import Optional
# from tenacity import retry, stop_after_attempt, wait_exponential
# from app.config import settings

# logger = logging.getLogger(__name__)

# class GeminiService:
#     TIMEOUT = aiohttp.ClientTimeout(total=60)

#     def __init__(self):
#         self.api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={settings.GEMINI_API_KEY}"

#     @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
#     async def generate_text_async(self, prompt: str) -> Optional[str]:
#         headers = {"Content-Type": "application/json"}
#         payload = {"contents": [{"parts": [{"text": prompt}]}]}

#         try:
#             async with aiohttp.ClientSession() as session:
#                 async with session.post(
#                     self.api_url,
#                     json=payload,
#                     headers=headers,
#                     timeout=self.TIMEOUT
#                 ) as response:
#                     data = await response.json()
#                     return data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')
#         except Exception as e:
#             logger.error(f"Gemini error: {e}")
#             return None

    # Синхронная версия для совместимости
    # def generate_text(self, prompt: str) -> Optional[str]:
    #     import asyncio
    #     return asyncio.run(self.generate_text_async(prompt))


import aiohttp
import logging
import traceback
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings
logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        logger.debug("Initializing GeminiService")
        self.api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={settings.GEMINI_API_KEY}"

    def _post_process_text(self, text: str) -> str:
        """Постобработка текста от Gemini: удаление звездочек и очистка форматирования"""
        if not text:
            return text
            
        # Удаляем все звездочки (используемые для markdown форматирования)
        cleaned_text = text.replace('*', '')
        
        # Убираем лишние пробелы, которые могли остаться после удаления звездочек
        # cleaned_text = ' '.join(cleaned_text.split())
        
        return cleaned_text

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_text_async(self, prompt: str):
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

    # Синхронная обертка для совместимости с тестами и вызовами без asyncio
    def generate_text(self, prompt: str):
        import asyncio
        return asyncio.run(self.generate_text_async(prompt))