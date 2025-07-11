import logging
from datetime import datetime
from typing import Optional
from app.config import settings
from app.core.database import SessionLocal
from app.models.group import Group
from app.models.user import User

logger = logging.getLogger(__name__)

class BotService:
    """Сервис для обработки логики Telegram бота.
    
    Обрабатывает все типы сообщений от пользователей в личных чатах:
    команды активации, ответы на вечерние вопросы, управление пользователями.
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
        - Текстовые ответы на вечерние вопросы
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
            target_group = db.query(Group).filter(Group.id == db_user.group_id).first()
            schedule_time = f"{target_group.morning_hour:02d}:{target_group.morning_minute:02d}"
            bot.reply_to(
                message,
                f"Каждый день в {schedule_time} я буду отправлять вам следующее сообщение:\n\n" \
                "'🌅Поздравляю с успешным завершением рабочего дня! Мне нужно знать, какие задачи сегодня получилось решить и какой план на завтра. \nКакие сложности возникли?'\n\n"
                "Просто отвечайте на мои сообщения своими рабочими планами.\n\n"
                "✅ Ваш аккаунт активен и готов к работе!"
            )
            return
        
        # НОВАЯ ЛОГИКА: Создаем или обновляем пользователя для админа
        if not db_user or not db_user.is_verified:
            if user.username:
                pending_user = db.query(User).filter(
                    User.username == user.username,
                    User.user_id.is_(None)
                ).first()
                
                if pending_user:
                    # Активируем существующую запись админа без user_id
                    pending_user.user_id = str(user.id)
                    pending_user.is_verified = True
                    pending_user.is_active = True
                    pending_user.is_group_member = False  # Не добавляем как участника группы
                    if user.first_name:
                        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                        pending_user.full_name = full_name
                    db.commit()
                    db.refresh(pending_user)
                    db_user = pending_user
                    logger.info(f"Activated pending admin user @{user.username} with user_id {user.id}")
                    
                    # Уведомление для админа
                    bot.reply_to(
                        message,
                        f"✅ Добро пожаловать, @{user.username}! "
                        "Ваш аккаунт администратора активирован. "
                        "Вы будете получать сводки от групп, где вы админ."
                    )
                    return
                
            # Если не нашли pending, создаем нового пользователя (не админ?)
            db_user = User(
                user_id=str(user.id),
                username=user.username,
                is_verified=True,
                is_active=True,
                is_group_member=False
            )
            if user.first_name:
                full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                db_user.full_name = full_name
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            
            # Стандартное сообщение для нового пользователя
            bot.reply_to(
                message,
                "✅ Ваш аккаунт успешно активирован! "
                "Теперь вы можете получать уведомления."
            )
            return
        
        # Если пользователь не найден или не активирован (fallback)
        bot.reply_to(
            message,
            "👋 Привет! Для использования бота перейдите по ссылке активации от администратора.\n\n"
            f"📧 Ваш @username: @{user.username or 'не_указан'}\n"
            f"🆔 Ваш ID: {user.id}\n\n"
            "Если ссылка активации не работает, обратитесь к администратору."
        )

    def _activate_user_with_token(self, activation_token, telegram_user, db, bot, message):
        """Активирует пользователя через токен активации группы.
        
        Выполняет процедуру активации нового пользователя или реактивации существующего:
        1. Проверяет валидность токена активации группы
        2. Находит группу по токену
        3. Ищет существующего пользователя по user_id или username
        4. Создает нового пользователя или обновляет существующего
        5. Назначает пользователя в найденную группу
        6. Устанавливает статус активации и обновляет профиль
        
        Args:
            activation_token (str): Токен активации группы из ссылки.
            telegram_user: Объект пользователя Telegram с атрибутами id, username, first_name, last_name.
            db: Сессия базы данных для работы с пользователями.
            bot: Экземпляр Telegram бота для отправки ответов.
            message: Объект сообщения Telegram для отправки ответа.
        
        Note:
            Обрабатывает конфликты username между пользователями.
            При успешной активации отправляет приветственное сообщение.
            Откатывает изменения в БД при ошибках.
        
        Examples:
            >>> # Вызывается автоматически при команде /start LsKhcPQqknf2pagJZ03...
            >>> self._activate_user_with_token("LsKhcPQqknf2pagJZ03...", telegram_user, db, bot, message)
        """
        try:
            # ===== НОВАЯ ЛОГИКА: Поиск группы по токену =====
            from app.models.group import Group
            
            # Проверяем валидность токена - ищем активную группу с таким токеном
            target_group = db.query(Group).filter(
                Group.activation_token == activation_token,
                Group.is_active == True
            ).first()
            
            if not target_group:
                # Проверяем legacy токен для обратной совместимости
                if activation_token == "group_activation":
                    # Находим группу по умолчанию для legacy активации
                    target_group = db.query(Group).filter(Group.is_active == True).first()
                    
                    if not target_group:
                        bot.reply_to(
                            message,
                            "❌ Система групп не настроена.\n\n"
                            "Обратитесь к администратору для создания группы."
                        )
                        return
                else:
                    bot.reply_to(
                        message,
                        "❌ Неверная ссылка активации или группа неактивна.\n\n"
                        "Используйте актуальную ссылку от администратора или обратитесь к нему."
                    )
                    return
            
            # Ищем пользователя по user_id (приоритет)
            existing_user_by_id = db.query(User).filter(User.user_id == str(telegram_user.id)).first()
            
            # Если пользователь уже активирован
            if existing_user_by_id and existing_user_by_id.is_verified:
                schedule_time = f"{target_group.morning_hour:02d}:{target_group.morning_minute:02d}"
                bot.reply_to(
                    message,
                    "✅ Вы уже активированы в системе!\n\n"
                    f"Каждый день в {schedule_time} я буду отправлять вам следующее сообщение:\n\n" \
                    "'🌅 Поздравляю с успешным завершением рабочего дня! Мне нужно знать, какие задачи сегодня получилось решить и какой план на завтра. Какие сложности возникли?'\n\n"
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
            
            # НОВАЯ ЛОГИКА: Проверяем, существует ли запись с этим username без user_id (созданная при смене админа)
            pending_user_by_username = None
            if not existing_user_by_id and telegram_user.username:
                pending_user_by_username = db.query(User).filter(
                    User.username == telegram_user.username,
                    User.user_id.is_(None)
                ).first()
            
            # Определяем пользователя для активации
            if existing_user_by_id:
                # Активируем существующего пользователя по user_id
                db_user = existing_user_by_id
                db_user.is_verified = True
                db_user.activation_token = None
                db_user.group_id = target_group.id  # ===== НАЗНАЧАЕМ В ГРУППУ =====
                
                # Обновляем username только если он не занят
                if telegram_user.username and not existing_user_by_username:
                    db_user.username = telegram_user.username
                    
            elif pending_user_by_username:
                # Обновляем существующую запись без user_id
                db_user = pending_user_by_username
                db_user.user_id = str(telegram_user.id)
                db_user.is_verified = True
                db_user.activation_token = None
                db_user.group_id = target_group.id
                db_user.is_group_member = False
                # Обновляем full_name
                if telegram_user.first_name:
                    full_name = f"{telegram_user.first_name or ''} {telegram_user.last_name or ''}".strip()
                    db_user.full_name = full_name
            else:
                # Создаем нового пользователя
                # Username устанавливаем только если он не занят
                new_username = telegram_user.username if telegram_user.username and not existing_user_by_username else None
                
                db_user = User(
                    user_id=str(telegram_user.id),
                    username=new_username,
                    is_verified=True,
                    is_group_member=True,
                    activation_token=None,
                    group_id=target_group.id  # ===== НАЗНАЧАЕМ В ГРУППУ =====
                )
                db.add(db_user)
            
            # Обновляем full_name (если не обновили выше)
            if telegram_user.first_name and not pending_user_by_username:  # Избегаем двойного обновления
                full_name = f"{telegram_user.first_name or ''} {telegram_user.last_name or ''}".strip()
                db_user.full_name = full_name
            
            db.commit()
            
            user_display = db_user.full_name or f"@{db_user.username}" if db_user.username else f"ID:{db_user.user_id}"
            logger.info(f"Пользователь {user_display} успешно активирован в группе '{target_group.name}' (ID: {target_group.id})")
            
            # Уведомляем об успешной активации с информацией о группе
            welcome_name = db_user.full_name or (f"@{db_user.username}" if db_user.username else "коллега")
            schedule_time = f"{target_group.morning_hour:02d}:{target_group.morning_minute:02d}"
            welcome_message = f"🎉 Добро пожаловать в группу '{target_group.name}', {welcome_name}!\n\n" \
                            "✅ Ваш аккаунт успешно активирован!\n\n" \
                            f"Каждый день в {schedule_time} я буду отправлять вам следующее сообщение:\n\n" \
                            "'🌅 Поздравляю с успешным завершением рабочего дня! Мне нужно знать, какие задачи сегодня получилось решить и какой план на завтра. Какие сложности возникли?'\n\n" \
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

    def handle_change_command(self, message, bot):
        """Обрабатывает команду /change для редактирования плана пользователя.
        
        Позволяет пользователю изменить свой план на день, если он уже отвечал.
        Проверяет права пользователя и наличие предыдущего ответа.
        
        Args:
            message: Объект сообщения Telegram с командой /change.
            bot: Экземпляр Telegram бота для отправки ответов.
        
        Note:
            Устанавливает флаг editing_mode для следующего сообщения пользователя.
            Следующее текстовое сообщение будет обработано как новый план.
        
        Examples:
            >>> # Вызывается автоматически при команде /change
            >>> self.handle_change_command(change_message, bot)
        """
        from app.core.database import SessionLocal
        
        db = SessionLocal()
        try:
            user = message.from_user
            user_id = user.id
            username = user.username
            
            logger.info(f"Processing /change command from user @{username or user_id}")
            
            # Ищем пользователя по user_id
            db_user = db.query(User).filter(User.user_id == str(user.id)).first()
            
            if not db_user:
                bot.reply_to(
                    message,
                    "❌ Вы не зарегистрированы в системе.\n\n"
                    "Перейдите по ссылке активации от администратора для начала работы."
                )
                return
            
            # Проверяем, что пользователь активирован
            if not db_user.is_verified:
                bot.reply_to(
                    message,
                    "⚠️ Ваш аккаунт еще не активирован.\n\n"
                    "Перейдите по ссылке активации от администратора."
                )
                return
            
            # Проверяем, что пользователь активен
            if not db_user.is_active:
                bot.reply_to(
                    message,
                    "⏸️ Ваш аккаунт временно деактивирован.\n\n"
                    "Обратитесь к администратору для активации."
                )
                return
            
            # Проверяем, есть ли что редактировать
            if not db_user.has_responded_today or not db_user.last_response:
                bot.reply_to(
                    message,
                    "📝 У вас нет плана на сегодня для редактирования.\n\n"
                    "Сначала отправьте свой план, а затем используйте /change для его изменения."
                )
                return
            
            # Получаем отображаемое имя пользователя
            if db_user.full_name:
                user_display = db_user.full_name
            elif db_user.username:
                user_display = f"@{db_user.username}"
            else:
                user_display = f"ID:{db_user.user_id}"
            
            # Показываем текущий план и просим новый
            current_plan_preview = db_user.last_response[:200] + "..." if len(db_user.last_response) > 200 else db_user.last_response
            
            change_message = (
                f"🔄 Редактирование плана на сегодня\n\n"
                f"📝 **Ваш текущий план:**\n"
                f"{current_plan_preview}\n\n"
                f"✏️ **Отправьте новый план для замены.**\n"
                f"Следующее сообщение заменит ваш текущий план на сегодня."
            )
            
            bot.reply_to(message, change_message, parse_mode='Markdown')
            
            # Устанавливаем флаг редактирования для следующего сообщения
            # Сохраняем в базе временный флаг
            db_user.activation_token = "editing_mode"  # Используем поле activation_token как временный флаг
            db.commit()
            
            logger.info(f"Пользователь {user_display} инициировал редактирование плана")
            
        except Exception as e:
            logger.error(f"Error handling change command: {e}", exc_info=True)
            bot.reply_to(message, "❌ Произошла ошибка при обработке команды")
        finally:
            db.close()

    def _process_daily_plan(self, db_user, text, bot, message):
        """Обрабатывает план пользователя на день с анализом качества через Gemini.
        
        Выполняет следующие действия:
        1. Анализирует качество ответа через Gemini AI
        2. Если ответ неприемлем - просит уточнить (максимум 3 попытки)
        3. Если ответ приемлем - сохраняет и интегрируется с планировщиком
        
        Args:
            db_user: Объект пользователя из базы данных (модель User).
            text (str): Текст плана пользователя на день.
            bot: Экземпляр Telegram бота для отправки подтверждения.
            message: Объект сообщения Telegram для отправки ответа.
        
        Note:
            Использует Gemini для анализа качества ответа.
            Отслеживает количество попыток через db_user.response_retry_count.
            Максимум 3 попытки улучшить ответ, затем принимает любой ответ.
        
        Examples:
            >>> # Вызывается автоматически при получении текстового сообщения
            >>> self._process_daily_plan(user_from_db, "Работаю", bot, message)
            # Gemini проанализирует и попросит уточнить
        """
        try:
            # Получаем отображаемое имя пользователя
            if db_user.full_name:
                user_display = db_user.full_name
            elif db_user.username:
                user_display = f"@{db_user.username}"
            else:
                user_display = f"ID:{db_user.user_id}"
            
            # Проверяем, находится ли пользователь в режиме редактирования
            is_editing_mode = db_user.activation_token == "editing_mode"
            
            if is_editing_mode:
                # Режим редактирования - заменяем существующий план
                logger.info(f"Обрабатываем редактирование плана пользователя {user_display}")
                
                # Сохраняем старый план для логирования
                old_plan = db_user.last_response
                
                # Обновляем план
                from app.services.scheduler import process_user_response
                process_user_response(message.from_user, text)
                
                # Очищаем флаг редактирования
                from app.core.database import SessionLocal
                db_edit = SessionLocal()
                try:
                    db_user_update = db_edit.query(type(db_user)).filter(type(db_user).id == db_user.id).first()
                    if db_user_update:
                        db_user_update.activation_token = None  # Очищаем флаг редактирования
                        db_user_update.response_retry_count = 0  # Сбрасываем счетчик попыток
                        db_edit.commit()
                finally:
                    db_edit.close()
                
                # Отправляем подтверждение об успешном редактировании
                confirmation_message = (
                    f"✅ {user_display}, ваш план успешно изменен!\n\n"
                    "📝 Новый план сохранен и будет включен в сводку команды.\n"
                    "🔄 Изменения вступили в силу немедленно."
                )
                
                bot.reply_to(message, confirmation_message)
                
                # Логируем редактирование
                old_preview = old_plan[:50] + "..." if old_plan and len(old_plan) > 50 else old_plan
                new_preview = text[:50] + "..." if len(text) > 50 else text
                logger.info(f"План пользователя {user_display} изменен с '{old_preview}' на '{new_preview}'")
                return
            
            # Проверяем, если пользователь уже ответил сегодня и это не попытка улучшить ответ
            if db_user.has_responded_today and db_user.response_retry_count == 0:
                bot.reply_to(
                    message,
                    f"✅ {user_display}, вы уже предоставили план на сегодня!\n\n"
                    "📝 Ваш ответ уже учтен в сводке команды.\n"
                    "🔄 Для изменения плана используйте команду /change"
                )
                # Увеличиваем счетчик попыток для отслеживания изменений
                from app.core.database import SessionLocal
                db = SessionLocal()
                try:
                    db_user_update = db.query(type(db_user)).filter(type(db_user).id == db_user.id).first()
                    if db_user_update:
                        db_user_update.response_retry_count += 1
                        db.commit()
                finally:
                    db.close()
                return
            
            # Анализируем качество ответа через Gemini (только для первых 3 попыток)
            if db_user.response_retry_count < 3:
                logger.info(f"Анализируем качество ответа пользователя {user_display} (попытка {db_user.response_retry_count + 1}/3)")
                
                try:
                    analysis = self.gemini_service.analyze_response_quality(text)
                    
                    if not analysis.get('is_acceptable', True):
                        # Ответ неприемлем - просим уточнить
                        from app.core.database import SessionLocal
                        db = SessionLocal()
                        try:
                            db_user_update = db.query(type(db_user)).filter(type(db_user).id == db_user.id).first()
                            if db_user_update:
                                db_user_update.response_retry_count += 1
                                db.commit()
                                
                                retry_count = db_user_update.response_retry_count
                                
                        finally:
                            db.close()
                        
                        feedback = analysis.get('feedback', '🤔 Пожалуйста, опишите ваш план более подробно.')
                        remaining_attempts = 3 - retry_count
                        
                        clarification_message = f"🤔 {feedback}\n\n"
                        if remaining_attempts > 0:
                            clarification_message += f"💡 Попробуйте указать конкретные задачи, проекты или цели на сегодня.\n\n"
                            clarification_message += f"⏳ Осталось попыток: {remaining_attempts}"
                        else:
                            clarification_message += "✅ Следующий ответ будет принят в любом случае."
                        
                        bot.reply_to(message, clarification_message)
                        logger.info(f"Ответ пользователя {user_display} отклонен Gemini (причина: {analysis.get('reason', 'неизвестно')}), попытка {retry_count}/3")
                        return
                        
                except Exception as e:
                    logger.warning(f"Ошибка анализа качества ответа пользователя {user_display}: {e}, принимаем ответ")
                    # При ошибке анализа принимаем ответ
            
            # Ответ принят - сохраняем его
            from app.services.scheduler import process_user_response
            process_user_response(message.from_user, text)
            
            # Сбрасываем счетчик попыток после успешного сохранения
            from app.core.database import SessionLocal
            db = SessionLocal()
            try:
                db_user_update = db.query(type(db_user)).filter(type(db_user).id == db_user.id).first()
                if db_user_update:
                    db_user_update.response_retry_count = 0
                    db.commit()
            finally:
                db.close()
            
            # Отправляем подтверждение
            if db_user.response_retry_count > 0:
                confirmation_message = f"✅ Отлично, {user_display}! Теперь ваш план принят и понятен.\n\n"
            else:
                confirmation_message = f"✅ Спасибо, {user_display}! Ваш план принят.\n\n"
                
            confirmation_message += ("📝 Когда все участники команды ответят, "
                                   "администратор получит общую сводку планов.")
            
            bot.reply_to(message, confirmation_message)
            
            logger.info(f"План пользователя {user_display} принят и сохранен: {text[:100]}...")
            
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