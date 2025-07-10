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
            username = user.username
            text = message.text
            
            logger.info(f"Processing message from user @{username or user_id}: {text[:50]}...")
            
            # Сначала ищем пользователя по user_id (если уже верифицирован)
            db_user = db.query(User).filter(User.user_id == str(user.id)).first()
            
            # Если не найден по user_id, ищем по username (неверифицированный)
            if not db_user and username:
                db_user = db.query(User).filter(
                    User.username == username, 
                    User.is_verified == False
                ).first()
                
                # Если найден неверифицированный пользователь, верифицируем его
                if db_user:
                    self._verify_user(db_user, user, db)
                    logger.info(f"Пользователь @{username} верифицирован и связан с user_id {user.id}")
                    bot.reply_to(
                        message,
                        f"✅ Отлично! Теперь вы подключены к системе.\n\n"
                        f"🌅 Каждое утро в 9:00 я буду спрашивать у вас планы на день.\n"
                        f"Просто отвечайте на мои сообщения своими рабочими планами."
                    )
                    return
            
            if not db_user:
                bot.reply_to(
                    message,
                    "❌ Вы не добавлены в систему администратором.\n\n"
                    f"Сообщите администратору ваш @username: @{username or 'не_указан'}\n"
                    "После добавления напишите боту /start снова."
                )
                return
            
            # Проверяем, что пользователь верифицирован
            if not db_user.is_verified:
                bot.reply_to(
                    message,
                    "⚠️ Ваш аккаунт еще не активирован. "
                    "Обратитесь к администратору."
                )
                return
            
            # Обновляем информацию о пользователе если нужно
            updated = False
            if user.username and db_user.username != user.username:
                # Проверяем, что новый username не занят
                existing_user = db.query(User).filter(
                    User.username == user.username, 
                    User.id != db_user.id
                ).first()
                if not existing_user:
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
            
            # Проверяем, является ли это командой /start
            if text and text.startswith('/start'):
                bot.reply_to(
                    message,
                    "👋 Привет! Вы подключены к системе сбора утренних планов команды.\n\n"
                    "🌅 Каждое утро в 9:00 я буду спрашивать у вас планы на день.\n\n"
                    "🔹 Просто отвечайте на мои утренние сообщения своими рабочими планами.\n\n"
                    "✅ Ваш аккаунт активен и готов к работе!"
                )
                return
            
            # Обрабатываем ответ как план на день
            self._process_daily_plan(db_user, text, bot, message)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            bot.reply_to(message, "❌ Произошла ошибка при обработке сообщения")
        finally:
            db.close()

    def _verify_user(self, db_user, telegram_user, db):
        """Верификация пользователя - связывание username с user_id"""
        try:
            db_user.user_id = str(telegram_user.id)
            db_user.is_verified = True
            
            # Обновляем полное имя если есть
            if telegram_user.first_name:
                full_name = f"{telegram_user.first_name or ''} {telegram_user.last_name or ''}".strip()
                db_user.full_name = full_name
            
            db.commit()
            logger.info(f"Пользователь @{db_user.username} успешно верифицирован")
            
        except Exception as e:
            logger.error(f"Ошибка верификации пользователя: {e}")
            db.rollback()
            raise

    def _process_daily_plan(self, db_user, text, bot, message):
        """Обработка плана на день"""
        try:
            # Сохраняем ответ пользователя
            from app.services.scheduler import process_user_response
            process_user_response(message.from_user, text)
            
            # Отправляем подтверждение
            # Используем full_name для отображения, если есть
            if db_user.full_name:
                user_display = db_user.full_name
            elif db_user.username:
                user_display = f"@{db_user.username}"
            else:
                user_display = f"ID:{db_user.user_id}"
                
            bot.reply_to(
                message,
                f"✅ Спасибо, {user_display}! Ваш план принят.\n\n"
                "📝 Когда все участники команды ответят, "
                "администратор получит общую сводку планов."
            )
            
            logger.info(f"План пользователя {user_display} сохранен: {text[:100]}...")
            
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