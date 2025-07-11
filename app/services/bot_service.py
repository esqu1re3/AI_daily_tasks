import logging
from datetime import datetime
from typing import Optional
from app.config import settings
from app.core.database import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)

class BotService:
    """Сервис для обработки логики Telegram бота.
    
    Обрабатывает все типы сообщений от пользователей в личных чатах:
    команды активации, ответы на утренние вопросы, управление пользователями.
    Интегрируется с Gemini AI для обработки планов команды.
    
    Attributes:
        gemini_service: Экземпляр GeminiService для работы с AI.
    
    Examples:
        >>> from app.services.gemini_service import GeminiService
        >>> gemini = GeminiService()
        >>> bot_service = BotService(gemini)
        >>> # Сервис готов к обработке сообщений
    """
    
    def __init__(self, gemini_service):
        """Инициализация сервиса бота.
        
        Args:
            gemini_service: Экземпляр GeminiService для генерации ответов и сводок.
        
        Examples:
            >>> gemini = GeminiService()
            >>> bot_service = BotService(gemini)
        """
        self.gemini_service = gemini_service
        logger.debug("BotService initialized")

    def handle_user_message_sync(self, message, bot):
        """Обрабатывает сообщения пользователей в личных чатах.
        
        Основная точка входа для обработки всех сообщений от пользователей.
        Определяет тип сообщения и направляет его соответствующему обработчику.
        
        Поддерживаемые сценарии:
        - Команда /start с токеном активации
        - Команда /start без токена (для активированных пользователей)
        - Текстовые ответы на утренние вопросы
        - Управление неактивированными пользователями
        
        Args:
            message: Объект сообщения от Telegram API с атрибутами from_user, text, chat.
            bot: Экземпляр Telegram бота для отправки ответов.
        
        Note:
            Обрабатывает только личные сообщения (chat.type == 'private').
            Все ошибки логируются, пользователь получает уведомление об ошибке.
        
        Examples:
            >>> # Вызывается автоматически при получении сообщения
            >>> bot_service.handle_user_message_sync(telegram_message, telegram_bot)
        """
        db = SessionLocal()
        try:
            user = message.from_user
            user_id = user.id
            username = user.username
            text = message.text
            chat_type = message.chat.type
            
            logger.info(f"Processing message from user @{username or user_id} in {chat_type}: {text[:50]}...")
            
            # Обрабатываем только личные сообщения
            if chat_type != 'private':
                return
            
            # Обрабатываем команду /start в приватном чате
            if text and text.startswith('/start'):
                self._handle_start_command(message, bot, db)
                return
            
            # Ищем пользователя по user_id (если уже активирован)
            db_user = db.query(User).filter(User.user_id == str(user.id)).first()
            
            if not db_user:
                # Предлагаем активироваться
                bot.reply_to(
                    message,
                    "👋 Привет! Чтобы пользоваться ботом, перейдите по ссылке активации от администратора.\n\n"
                    f"📧 Ваш @username: @{username or 'не_указан'}\n"
                    f"🆔 Ваш ID: {user_id}\n\n"
                    "Если вы не получили ссылку активации, обратитесь к администратору."
                )
                return
            
            # Проверяем, что пользователь активирован
            if not db_user.is_verified:
                bot.reply_to(
                    message,
                    "⚠️ Ваш аккаунт еще не активирован. "
                    "Перейдите по ссылке активации от администратора или обратитесь к нему."
                )
                return
            
            # Обновляем информацию о пользователе если нужно
            updated = False
            if user.username and user.username != db_user.username:
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
            
            # Обрабатываем ответ как план на день
            self._process_daily_plan(db_user, text, bot, message)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            bot.reply_to(message, "❌ Произошла ошибка при обработке сообщения")
        finally:
            db.close()

    def _handle_start_command(self, message, bot, db):
        """Обрабатывает команду /start с возможным токеном активации.
        
        Различает два сценария:
        1. /start с токеном - активация нового пользователя
        2. /start без токена - приветствие активированного пользователя
        
        Args:
            message: Объект сообщения Telegram с командой /start.
            bot: Экземпляр Telegram бота для отправки ответов.
            db: Сессия базы данных для работы с пользователями.
        
        Examples:
            >>> # Вызывается автоматически при команде /start
            >>> self._handle_start_command(start_message, bot, db_session)
        """
        user = message.from_user
        text = message.text
        
        # Извлекаем токен из команды /start (если есть)
        parts = text.split(' ', 1)
        activation_token = parts[1] if len(parts) > 1 else None
        
        if activation_token:
            # Активация через токен (новые пользователи)
            self._activate_user_with_token(activation_token, user, db, bot, message)
            return
        
        # Команда /start без токена - проверяем существующего пользователя
        db_user = db.query(User).filter(User.user_id == str(user.id)).first()
        
        if db_user and db_user.is_verified:
            bot.reply_to(
                message,
                "👋 Привет! Вы подключены к системе сбора утренних планов команды.\n\n"
                "🌅 Каждое утро в 9:30 я буду спрашивать у вас планы на день.\n\n"
                "🔹 Просто отвечайте на мои утренние сообщения своими рабочими планами.\n\n"
                "✅ Ваш аккаунт активен и готов к работе!"
            )
        else:
            bot.reply_to(
                message,
                "👋 Привет! Для использования бота перейдите по ссылке активации от администратора.\n\n"
                f"📧 Ваш @username: @{user.username or 'не_указан'}\n"
                f"🆔 Ваш ID: {user.id}\n\n"
                "Если ссылка активации не работает, обратитесь к администратору."
            )

    def _activate_user_with_token(self, activation_token, telegram_user, db, bot, message):
        """Активирует пользователя через токен активации.
        
        Выполняет процедуру активации нового пользователя или реактивации существующего:
        1. Проверяет валидность токена активации
        2. Ищет существующего пользователя по user_id или username
        3. Создает нового пользователя или обновляет существующего
        4. Устанавливает статус активации и обновляет профиль
        
        Args:
            activation_token (str): Токен активации из ссылки (например, "group_activation").
            telegram_user: Объект пользователя Telegram с атрибутами id, username, first_name, last_name.
            db: Сессия базы данных для работы с пользователями.
            bot: Экземпляр Telegram бота для отправки ответов.
            message: Объект сообщения Telegram для отправки ответа.
        
        Note:
            Обрабатывает конфликты username между пользователями.
            При успешной активации отправляет приветственное сообщение.
            Откатывает изменения в БД при ошибках.
        
        Examples:
            >>> # Вызывается автоматически при команде /start group_activation
            >>> self._activate_user_with_token("group_activation", telegram_user, db, bot, message)
        """
        try:
            # Проверяем валидность токена сначала
            if activation_token != "group_activation":
                bot.reply_to(
                    message,
                    "❌ Неверная ссылка активации.\n\n"
                    "Используйте актуальную ссылку от администратора или обратитесь к нему."
                )
                return
            
            # Ищем пользователя по user_id (приоритет)
            existing_user_by_id = db.query(User).filter(User.user_id == str(telegram_user.id)).first()
            
            # Если пользователь уже активирован
            if existing_user_by_id and existing_user_by_id.is_verified:
                bot.reply_to(
                    message,
                    "✅ Вы уже активированы в системе!\n\n"
                    "🌅 Каждое утро в 9:30 я буду спрашивать у вас планы на день.\n"
                    "Просто отвечайте на мои сообщения своими рабочими планами."
                )
                return
            
            # Проверяем, не занят ли username другим user_id
            existing_user_by_username = None
            if telegram_user.username:
                existing_user_by_username = db.query(User).filter(
                    User.username == telegram_user.username,
                    User.user_id != str(telegram_user.id)
                ).first()
            
            # Определяем пользователя для активации
            if existing_user_by_id:
                # Активируем существующего пользователя по user_id
                db_user = existing_user_by_id
                db_user.is_verified = True
                db_user.activation_token = None
                
                # Обновляем username только если он не занят
                if telegram_user.username and not existing_user_by_username:
                    db_user.username = telegram_user.username
                    
            else:
                # Создаем нового пользователя
                # Username устанавливаем только если он не занят
                new_username = telegram_user.username if telegram_user.username and not existing_user_by_username else None
                
                db_user = User(
                    user_id=str(telegram_user.id),
                    username=new_username,
                    is_verified=True,
                    is_group_member=True,
                    activation_token=None
                )
                db.add(db_user)
            
            # Обновляем full_name
            if telegram_user.first_name:
                full_name = f"{telegram_user.first_name or ''} {telegram_user.last_name or ''}".strip()
                db_user.full_name = full_name
            
            db.commit()
            
            user_display = db_user.full_name or f"@{db_user.username}" if db_user.username else f"ID:{db_user.user_id}"
            logger.info(f"Пользователь {user_display} успешно активирован через ссылку")
            
            # Уведомляем об успешной активации
            welcome_name = db_user.full_name or (f"@{db_user.username}" if db_user.username else "коллега")
            welcome_message = f"🎉 Добро пожаловать в команду, {welcome_name}!\n\n" \
                            "✅ Ваш аккаунт успешно активирован!\n\n" \
                            "🌅 Каждое утро в 9:30 я буду спрашивать у вас планы на день.\n" \
                            "Просто отвечайте на мои сообщения своими рабочими планами.\n\n" \
                            "🚀 Система готова к работе!"
            
            logger.info(f"Отправка приветственного сообщения пользователю {user_display}")
            try:
                bot.reply_to(message, welcome_message)
                logger.info(f"✅ Приветственное сообщение успешно отправлено пользователю {user_display}")
            except Exception as msg_error:
                logger.error(f"❌ Ошибка отправки приветственного сообщения пользователю {user_display}: {msg_error}")
            
        except Exception as e:
            logger.error(f"Ошибка активации пользователя: {e}")
            db.rollback()
            bot.reply_to(
                message,
                "❌ Произошла ошибка при активации аккаунта. "
                "Попробуйте еще раз или обратитесь к администратору."
            )

    def _process_daily_plan(self, db_user, text, bot, message):
        """Обрабатывает план пользователя на день.
        
        Сохраняет ответ пользователя как план на день и интегрируется с системой
        планировщика для автоматической генерации сводок команды.
        
        Args:
            db_user: Объект пользователя из базы данных (модель User).
            text (str): Текст плана пользователя на день.
            bot: Экземпляр Telegram бота для отправки подтверждения.
            message: Объект сообщения Telegram для отправки ответа.
        
        Note:
            Автоматически интегрируется с планировщиком для проверки полноты ответов.
            Отправляет пользователю подтверждение о принятии плана.
            Использует scheduler.process_user_response для дальнейшей обработки.
        
        Examples:
            >>> # Вызывается автоматически при получении текстового сообщения
            >>> self._process_daily_plan(user_from_db, "План на сегодня: доделать проект", bot, message)
        """
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