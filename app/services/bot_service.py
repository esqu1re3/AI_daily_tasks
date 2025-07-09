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
        db = SessionLocal()
        try:
            user = message.from_user
            user_id = user.id
            text = message.text
            
            logger.info(f"Processing message from user @{user.username or user_id}: {text[:50]}...")
            
            # Ищем пользователя по user_id
            db_user = db.query(User).filter(User.user_id == str(user.id)).first()
            
            if not db_user:
                bot.reply_to(
                    message,
                    "❌ Вы не добавлены в систему администратором. "
                    "Обратитесь к администратору для получения доступа."
                )
                return
            
            # Обновляем информацию о пользователе если нужно
            updated = False
            if user.username and db_user.username != user.username:
                db_user.username = user.username
                updated = True
            
            if user.first_name:
                full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                if db_user.full_name != full_name:
                    db_user.full_name = full_name
                    updated = True
            
            if updated:
                db.commit()
                logger.info(f"Обновлена информация пользователя {user.id}")
            
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
        finally:
            db.close()

    def _process_daily_plan(self, db_user, text, bot, message):
        """Обработка плана на день"""
        try:
            # Сохраняем ответ пользователя
            from app.services.scheduler import process_user_response
            process_user_response(message.from_user, text)
            
            # Отправляем подтверждение
            username_display = f"@{db_user.username}" if db_user.username else f"ID:{db_user.user_id}"
            bot.reply_to(
                message,
                f"✅ Спасибо, {username_display}! Ваш план принят.\n\n"
                "📝 Когда все участники команды ответят, "
                "администратор получит общую сводку планов."
            )
            
            logger.info(f"План пользователя {username_display} сохранен: {text[:100]}...")
            
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