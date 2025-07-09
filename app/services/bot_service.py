import logging
import traceback
import asyncio
from datetime import datetime
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

class BotService:
    WORK_KEYWORDS = {
        'задача', 'проект', 'отчет', 'план', 'встреча', 'дедлайн', 'kpi',
        'работа', 'задачи', 'проблема', 'статус', 'итоги', 'продвижение',
        'сотрудник', 'команда', 'клиент', 'срок', 'метрика', 'результат',
        'обсудить', 'вопрос', 'помощь', 'сделал', 'делаю', 'план', 'цель',
        'kpi', 'okr', 'запланировать', 'отчитаться', 'прогресс', 'обновление'
    }
    BANNED_KEYWORDS = {
        'какать', 'туалет', 'личное', 'медицина', 'здоровье', 'диета',
        'секс', 'отношения', 'политика', 'религия', 'фильм', 'музыка',
        'игра', 'развлечение', 'еда', 'ресторан', 'шутка', 'анекдот'
    }
    WORK_PATTERNS = [
        'работ', 'отчет', 'помощ', 'планир', 'дела', 'выполн', 'сдела', 'прогресс',
        'задач', 'проект', 'встреч', 'дедлайн', 'статус', 'итог', 'команд', 'клиент',
        'результат', 'обновл', 'отчит', 'kpi', 'okr', 'собираюсь', 'оптимизир', 'помочь'
    ]

    def __init__(self, gemini_service):
        self.gemini_service = gemini_service
        logger.debug("BotService initialized")

    def is_work_related(self, text: Optional[str]) -> bool:
        if not text:
            return False
        text_lower = text.lower()
        if any(banned in text_lower for banned in self.BANNED_KEYWORDS):
            return False
        # Более гибкая фильтрация по частям слов и паттернам
        return any(work in text_lower for work in self.WORK_PATTERNS)

    def handle_user_message_sync(self, message, bot):
        """Синхронная версия обработки сообщений для telebot"""
        try:
            user_id = message.from_user.id
            text = message.text
            
            logger.info(f"Processing message from user {user_id}: {text[:50]}...")
            
            if not self.is_work_related(text):
                logger.warning(f"Non-work related message from user {user_id}: {text[:50]}...")
                bot.reply_to(
                    message,
                    "🚫 Я могу отвечать только на рабочие вопросы!\n\n"
                    "Примеры корректных запросов:\n"
                    "- Какие задачи на сегодня?\n"
                    "- Какой статус по проекту X?\n"
                    "- Нужна помощь с задачей Y\n"
                    "- Отправляю отчет о проделанной работе"
                )
                return

            # Если пишет не админ, отправить админу уведомление
            admin_id = None
            try:
                admin_id = int(settings.ADMIN_ID)
            except Exception as e:
                logger.error(f"ADMIN_ID is not set or invalid: {e}")
            
            if admin_id and user_id and int(user_id) != admin_id:
                # Формируем текст уведомления для админа
                user = message.from_user
                user_name = user.username or "(без username)"
                first_name = user.first_name or ''
                last_name = user.last_name or ''
                full_name = f"{first_name} {last_name}".strip()
                if not full_name:
                    full_name = first_name or "Unknown"
                
                plan_text = f"Пользователь @{user_name} ({full_name}) отправил рабочий план/сообщение:\n{text}\n"
                
                try:
                    bot.send_message(chat_id=admin_id, text=plan_text)
                    logger.info(f"Message forwarded to admin: user {user_id} -> admin {admin_id}")
                except Exception as e:
                    logger.error(f"Не удалось отправить сообщение админу: {e}")

            # Генерируем ответ через Gemini
            logger.info(f"Generating response for user {user_id}")
            response = self._generate_response_sync(text)
            
            if response:
                bot.reply_to(message, response[:4000])
                logger.info(f"Response sent to user {user_id}: {response[:50]}...")
            else:
                bot.reply_to(message, "⚠️ Не удалось обработать ваш запрос")
                logger.warning(f"No response generated for user {user_id}")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            bot.reply_to(message, "❌ Произошла ошибка при обработке запроса")

    def _generate_response_sync(self, text: Optional[str]) -> Optional[str]:
        """Синхронная версия генерации ответа"""
        if not text:
            return None
        
        prompt = (
            "Ты - ассистент проектного менеджера. Ответь кратко и по делу на рабочий вопрос.\n\n"
            f"Сообщение сотрудника: {text}\n\n"
            "Если вопрос неясен - уточни детали. "
            "Ответ должен быть строго профессиональным и касаться только рабочих тем."
        )
        
        # Используем синхронную версию или запускаем асинхронную в новом event loop
        try:
            # Пытаемся получить текущий event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Если loop уже запущен, создаем новый для этого вызова
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, 
                        self.gemini_service.generate_text_async(prompt)
                    )
                    return future.result(timeout=30)
            else:
                # Если loop не запущен, используем его
                return loop.run_until_complete(self.gemini_service.generate_text_async(prompt))
        except RuntimeError:
            # Если нет event loop, создаем новый
            return asyncio.run(self.gemini_service.generate_text_async(prompt))
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "⚠️ Извините, не удалось обработать ваш запрос"

    # Оставляем старый асинхронный метод для совместимости
    async def handle_user_message(self, update, context):
        """Асинхронная версия для обратной совместимости (не используется с telebot)"""
        # Этот метод больше не используется, но оставляем для совместимости
        pass

    async def _generate_response(self, text: Optional[str]) -> Optional[str]:
        """Асинхронная версия генерации ответа"""
        if not text:
            return None
        
        prompt = (
            "Ты - ассистент проектного менеджера. Ответь кратко и по делу на рабочий вопрос.\n\n"
            f"Сообщение сотрудника: {text}\n\n"
            "Если вопрос неясен - уточни детали. "
            "Ответ должен быть строго профессиональным и касаться только рабочих тем."
        )
        return await self.gemini_service.generate_text_async(prompt)