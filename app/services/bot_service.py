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

    def handle_admin_command(self, message, bot):
        """Обрабатывает команду /admin для активации администраторов.
        
        Проверяет наличие pending записи по username с user_id=None,
        и активирует ее, устанавливая user_id и верифицируя.
        """
        from app.core.database import SessionLocal
        
        db = SessionLocal()
        try:
            user = message.from_user
            
            # Ищем существующего пользователя по user_id
            db_user = db.query(User).filter(User.user_id == str(user.id)).first()
            
            if db_user and db_user.is_verified:
                bot.reply_to(
                    message,
                    "✅ Ваш аккаунт администратора уже активирован!\n\n"
                    "Вы будете получать сводки от групп, где вы администратор."
                )
                return
            
            # Если не найден по user_id, ищем pending по username
            if user.username:
                pending_user = db.query(User).filter(
                    User.username == user.username,
                    User.user_id.is_(None)
                ).first()
                
                if pending_user:
                    # Активируем pending запись
                    pending_user.user_id = str(user.id)
                    pending_user.is_verified = True
                    pending_user.is_active = True
                    pending_user.is_group_member = False
                    
                    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                    pending_user.full_name = full_name
                    
                    db.commit()
                    db.refresh(pending_user)
                    
                    bot.reply_to(
                        message,
                        f"✅ Добро пожаловать, @{user.username}! \n\n"
                        "Ваш аккаунт администратора успешно активирован.\n"
                        "Вы будете получать сводки от своих групп."
                    )
                    logger.info(f"Activated admin user @{user.username} with user_id {user.id}")
                else:
                    bot.reply_to(
                        message,
                        "❌ Нет ожидающей активации для этого username.\n\n"
                        "Обратитесь к администратору системы."
                    )
            else:
                bot.reply_to(
                    message,
                    "❌ У вас не установлен username в Telegram.\n\n"
                    "Установите его в настройках и попробуйте снова."
                )
                
        except Exception as e:
            logger.error(f"Error handling admin command: {e}")
            bot.reply_to(message, "❌ Произошла ошибка при активации")
        finally:
            db.close()

    def _handle_start_command(self, message, bot, db):
        """Обрабатывает команду /start с возможным токеном активации.
        
        Различает два сценария:
        1. /start с токеном - активация нового пользователя
        2. /start без токена - приветствие активированного пользователя
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
            if target_group:
                schedule_time = f"{target_group.morning_hour:02d}:{target_group.morning_minute:02d}"
                bot.reply_to(
                    message,
                    f"✅ Ваш аккаунт активен!\n\n"
                    f"Каждый день в {schedule_time} я буду отправлять вам сообщение с вопросами о планах."
                )
            else:
                bot.reply_to(
                    message,
                    "✅ Ваш аккаунт активен, но группа не найдена. Обратитесь к администратору."
                )
            return
        
        # Если не активирован
        bot.reply_to(
            message,
            "👋 Привет! Для использования бота перейдите по ссылке активации от администратора.\n\n"
            f"📧 Ваш @username: @{user.username or 'не_указан'}\n"
            f"🆔 Ваш ID: {user.id}\n\n"
            "Если ссылка активации не работает, обратитесь к администратору."
        )

    def _activate_user_with_token(self, activation_token, telegram_user, db, bot, message):
        """Активирует пользователя через токен активации группы."""
        try:
            # Поиск группы по токену
            from app.models.group import Group
            
            target_group = db.query(Group).filter(
                Group.activation_token == activation_token,
                Group.is_active == True
            ).first()
            
            if not target_group:
                bot.reply_to(
                    message,
                    "❌ Неверная ссылка активации или группа неактивна."
                )
                return
            
            # Ищем пользователя по user_id
            existing_user_by_id = db.query(User).filter(User.user_id == str(telegram_user.id)).first()
            
            if existing_user_by_id and existing_user_by_id.is_verified:
                schedule_time = f"{target_group.morning_hour:02d}:{target_group.morning_minute:02d}"
                bot.reply_to(
                    message,
                    f"✅ Вы уже активированы!\n\n"
                    f"Ежедневно в {schedule_time} я буду присылать вопросы о планах."
                )
                return
            
            # Проверяем, не занят ли username
            existing_user_by_username = None
            if telegram_user.username:
                existing_user_by_username = db.query(User).filter(
                    User.username == telegram_user.username,
                    User.user_id != str(telegram_user.id)
                ).first()
            
            # Определяем пользователя
            if existing_user_by_id:
                db_user = existing_user_by_id
                db_user.is_verified = True
                db_user.activation_token = None
                db_user.group_id = target_group.id
                
                if telegram_user.username and not existing_user_by_username:
                    db_user.username = telegram_user.username
                    
            else:
                new_username = telegram_user.username if telegram_user.username and not existing_user_by_username else None
                
                db_user = User(
                    user_id=str(telegram_user.id),
                    username=new_username,
                    is_verified=True,
                    is_group_member=True,
                    activation_token=None,
                    group_id=target_group.id
                )
                db.add(db_user)
            
            # Обновляем full_name
            if telegram_user.first_name:
                full_name = f"{telegram_user.first_name or ''} {telegram_user.last_name or ''}".strip()
                db_user.full_name = full_name
            
            db.commit()
            
            user_display = db_user.full_name or f"@{db_user.username}" if db_user.username else f"ID:{db_user.user_id}"
            logger.info(f"Activated user {user_display} in group '{target_group.name}'")
            
            welcome_name = db_user.full_name or (f"@{db_user.username}" if db_user.username else "коллега")
            schedule_time = f"{target_group.morning_hour:02d}:{target_group.morning_minute:02d}"
            welcome_message = f"🎉 Добро пожаловать в группу '{target_group.name}', {welcome_name}!\n\n" \
                            f"✅ Аккаунт активирован!\n" \
                            f"Ежедневно в {schedule_time} я буду присылать вопросы о планах."
            
            bot.reply_to(message, welcome_message)
            
        except Exception as e:
            logger.error(f"Activation error: {e}")
            db.rollback()
            bot.reply_to(message, "❌ Ошибка активации. Попробуйте снова.")

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