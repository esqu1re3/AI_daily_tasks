import logging
from datetime import datetime
from typing import Optional
from app.config import settings
from app.core.database import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)

class BotService:
    def __init__(self, gemini_service):
        self.gemini_service = gemini_service
        logger.debug("BotService initialized")

    def handle_user_message_sync(self, message, bot):
        """Обработка сообщений пользователей"""
        try:
            user = message.from_user
            user_id = user.id
            text = message.text
            
            logger.info(f"Processing message from user @{user.username or user_id}: {text[:50]}...")
            
            # Проверяем, зарегистрирован ли пользователь
            db_user = self._get_or_register_user(user)
            
            if not db_user:
                bot.reply_to(
                    message,
                    "❌ Вы не добавлены в систему администратором. "
                    "Обратитесь к администратору для получения доступа."
                )
                return
            
            # Если пользователь не активен
            if not db_user.is_active:
                bot.reply_to(
                    message,
                    "⏸️ Ваш аккаунт временно деактивирован. "
                    "Обратитесь к администратору."
                )
                return
            
            # Обрабатываем ответ как план на день
            self._process_daily_plan(db_user, text, bot, message)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            bot.reply_to(message, "❌ Произошла ошибка при обработке сообщения")

    def _get_or_register_user(self, telegram_user):
        """Получение или регистрация пользователя"""
        db = SessionLocal()
        try:
            # Ищем пользователя по telegram_id
            db_user = db.query(User).filter(User.telegram_id == str(telegram_user.id)).first()
            
            if db_user:
                return db_user
            
            # Ищем по username
            username = telegram_user.username
            if username:
                db_user = db.query(User).filter(User.username == username).first()
                if db_user:
                    # Обновляем telegram_id
                    db_user.telegram_id = str(telegram_user.id)
                    
                    # Обновляем полное имя если его нет
                    if not db_user.full_name:
                        full_name = f"{telegram_user.first_name or ''} {telegram_user.last_name or ''}".strip()
                        db_user.full_name = full_name or "Unknown"
                    
                    db.commit()
                    logger.info(f"Пользователь @{username} подключился к боту")
                    return db_user
            
            # Пользователь не найден
            return None
            
        except Exception as e:
            logger.error(f"Ошибка работы с пользователем: {e}")
            return None
        finally:
            db.close()

    def _process_daily_plan(self, db_user, text, bot, message):
        """Обработка плана на день"""
        try:
            # Сохраняем ответ пользователя
            from app.services.scheduler import process_user_response
            process_user_response(message.from_user, text)
            
            # Отправляем подтверждение
            bot.reply_to(
                message,
                f"✅ Спасибо, @{db_user.username}! Ваш план принят.\n\n"
                "📝 Когда все участники команды ответят, "
                "администратор получит общую сводку планов."
            )
            
            logger.info(f"План пользователя @{db_user.username} сохранен: {text[:100]}...")
            
        except Exception as e:
            logger.error(f"Ошибка обработки плана: {e}")
            bot.reply_to(message, "⚠️ Ошибка сохранения плана. Попробуйте еще раз.")

    # Оставляем заглушки для совместимости
    def is_work_related(self, text: Optional[str]) -> bool:
        """Все сообщения считаем рабочими планами"""
        return True

    async def handle_user_message(self, update, context):
        """Асинхронная версия для обратной совместимости"""
        pass

    def _generate_response_sync(self, text: Optional[str]) -> Optional[str]:
        """Не используется в новой логике"""
        return None

    async def _generate_response(self, text: Optional[str]) -> Optional[str]:
        """Не используется в новой логике"""
        return None