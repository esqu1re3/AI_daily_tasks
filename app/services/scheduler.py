# Планировщик вечерних вопросов и сводки через Gemini
import asyncio
import telebot
import logging
import threading
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import settings
from app.core.database import SessionLocal
from app.models.user import User
from app.models.user_response import UserResponse
from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

# Lazy initialization of services
bot = None
gemini_service = None
scheduler = None
ADMIN_ID = None

def _ensure_services_initialized():
    """Обеспечивает инициализацию всех сервисов планировщика.
    
    Выполняет ленивую инициализацию Telegram бота, Gemini сервиса и планировщика
    задач. Инициализация происходит только один раз при первом обращении.
    
    Raises:
        RuntimeError: Если настройки приложения не загружены или отсутствуют
                     обязательные переменные окружения.
    
    Note:
        Эта функция использует глобальные переменные для хранения экземпляров
        сервисов и предназначена для внутреннего использования модулем.
    """
    global bot, gemini_service, scheduler, ADMIN_ID
    
    if bot is None:
        if settings is None:
            raise RuntimeError("Settings not loaded. Ensure .env file exists with required variables.")
        
        bot = telebot.TeleBot(settings.TG_BOT_TOKEN)
        gemini_service = GeminiService()
        scheduler = BackgroundScheduler()
        
        # ID администратора
        try:
            ADMIN_ID = int(settings.ADMIN_ID) if settings.ADMIN_ID else None
        except (ValueError, TypeError):
            ADMIN_ID = None
            logger.warning("ADMIN_ID не настроен в переменных окружения")

def send_morning_questions_to_group(group_id):
    """Отправляет вечерние вопросы участникам конкретной группы.
    
    Выполняет следующие действия:
    1. Сбрасывает флаги ответов для нового дня для группы
    2. Получает список активных и активированных участников группы
    3. Отправляет утренний вопрос каждому участнику группы
    4. Планирует генерацию сводки группы через 1 час
    
    Args:
        group_id (int): ID группы для рассылки.
    
    Note:
        Функция запускается автоматически планировщиком для каждой группы.
        Время выполнения индивидуально для каждой группы.
    
    Examples:
        >>> # Функция вызывается автоматически планировщиком
        >>> send_morning_questions_to_group(1)
    """
    _ensure_services_initialized()
    db = SessionLocal()
    try:
        from app.models.group import Group
        
        # Получаем информацию о группе
        group = db.query(Group).filter(Group.id == group_id, Group.is_active == True).first()
        if not group:
            logger.warning(f"Группа {group_id} не найдена или неактивна")
            return
        
        # Сбрасываем флаги ответов на новый день только для участников этой группы
        db.query(User).filter(User.group_id == group_id).update({
            User.has_responded_today: False,
            User.last_response: None,
            User.response_retry_count: 0  # Сбрасываем счетчик попыток для нового дня
        })
        db.commit()
        
        # Получаем активных И активированных участников группы
        active_users = db.query(User).filter(
            User.group_id == group_id,
            User.is_active == True,
            User.is_verified == True,  # Проверяем активацию
            User.is_group_member == True  # Проверяем участие в команде
        ).all()
        
        if not active_users:
            logger.info(f"Нет активных участников в группе '{group.name}' (ID: {group_id}) для рассылки")
            return
        
        question = "🌅 Поздравляю с успешным завершением рабочего дня! Мне нужно знать, какие задачи сегодня получилось решить и какой план на завтра. Какие сложности возникли?"
        
        success_count = 0
        for user in active_users:
            try:
                bot.send_message(
                    chat_id=int(user.user_id),
                    text=question
                )
                success_count += 1
                username_display = f"@{user.username}" if user.username else f"ID:{user.user_id}"
                logger.info(f"Утреннее сообщение отправлено участнику группы '{group.name}': {username_display}")
            except Exception as e:
                username_display = f"@{user.username}" if user.username else f"ID:{user.user_id}"
                logger.error(f"Ошибка отправки утреннего сообщения участнику группы '{group.name}' {username_display}: {e}")
        
        logger.info(f"Утренняя рассылка для группы '{group.name}' завершена. Отправлено сообщений: {success_count}/{len(active_users)}")
        
        # Запланируем генерацию сводки для группы ровно через 1 час
        summary_time = datetime.now() + timedelta(hours=1)
        scheduler.add_job(
            generate_summary_after_timeout_for_group,
            'date',
            run_date=summary_time,
            id=f'summary_group_{group_id}_after_1hour'
        )
        
        logger.info(f"Сводка для группы '{group.name}' будет сгенерирована в {summary_time.strftime('%H:%M:%S')} (через 1 час)")
        
    except Exception as e:
        logger.error(f"Ошибка в утренней рассылке для группы {group_id}: {e}")
    finally:
        db.close()

def send_morning_questions():
    """Отправляет вечерние вопросы всем группам (legacy-функция для обратной совместимости).
    
    Перебирает все активные группы и запускает для них рассылку по расписанию.
    Используется как fallback для групп без индивидуального расписания.
    """
    _ensure_services_initialized()
    db = SessionLocal()
    try:
        from app.models.group import Group
        
        # Получаем все активные группы
        active_groups = db.query(Group).filter(Group.is_active == True).all()
        
        logger.info(f"Запуск утренней рассылки для {len(active_groups)} групп")
        
        for group in active_groups:
            send_morning_questions_to_group(group.id)
            
    except Exception as e:
        logger.error(f"Ошибка в общей утренней рассылке: {e}")
    finally:
        db.close()

def generate_summary_after_timeout_for_group(group_id):
    """Генерирует сводку для конкретной группы после истечения времени ожидания ответов.
    
    Запускается автоматически через 1 час после отправки утренних вопросов группе.
    Собирает статистику ответов и запускает генерацию сводки в отдельном потоке.
    
    Args:
        group_id (int): ID группы для генерации сводки.
    
    Note:
        Использует многопоточность для предотвращения блокировки планировщика
        во время генерации сводки через Gemini API.
    
    Examples:
        >>> # Функция вызывается автоматически планировщиком
        >>> generate_summary_after_timeout_for_group(1)
    """
    db = SessionLocal()
    try:
        from app.models.group import Group
        
        # Получаем информацию о группе
        group = db.query(Group).filter(Group.id == group_id, Group.is_active == True).first()
        if not group:
            logger.warning(f"Группа {group_id} не найдена или неактивна")
            return
        
        # Получаем активных активированных участников группы
        active_users = db.query(User).filter(
            User.group_id == group_id,
            User.is_active == True,
            User.is_verified == True,  # Проверяем активацию
            User.is_group_member == True  # Проверяем участие в команде
        ).all()
        
        if not active_users:
            logger.info(f"Нет активных участников в группе '{group.name}' (ID: {group_id}) для генерации сводки")
            return
        
        # Проверяем кто ответил
        responded_users = [user for user in active_users if user.has_responded_today]
        not_responded_users = [user for user in active_users if not user.has_responded_today]
        
        logger.info(f"Время истекло для группы '{group.name}'. Статус ответов: {len(responded_users)}/{len(active_users)} участников ответили")
        
        # Генерируем сводку для группы с тем что есть В ОТДЕЛЬНОМ ПОТОКЕ
        threading.Thread(
            target=generate_and_send_summary_for_group, 
            args=(group, active_users), 
            daemon=True
        ).start()
        logger.info(f"Генерация сводки для группы '{group.name}' по таймауту запущена в отдельном потоке")
                
    except Exception as e:
        logger.error(f"Ошибка при генерации сводки по таймауту для группы {group_id}: {e}")
    finally:
        db.close()

def generate_summary_after_timeout():
    """Генерирует сводку после истечения времени ожидания ответов (legacy-функция).
    
    Перебирает все группы и генерирует сводки для каждой.
    Используется для обратной совместимости.
    """
    db = SessionLocal()
    try:
        from app.models.group import Group
        
        # Получаем все активные группы
        active_groups = db.query(Group).filter(Group.is_active == True).all()
        
        logger.info(f"Генерация сводок для {len(active_groups)} групп по таймауту")
        
        for group in active_groups:
            generate_summary_after_timeout_for_group(group.id)
                
    except Exception as e:
        logger.error(f"Ошибка при общей генерации сводок по таймауту: {e}")
    finally:
        db.close()

def generate_and_send_summary_for_group(group, users):
    """Генерирует сводку планов группы через Gemini AI и отправляет администратору группы.
    
    Выполняет следующие действия:
    1. Собирает все ответы участников группы
    2. Формирует промпт для Gemini API
    3. Генерирует сводку через Gemini AI
    4. Отправляет готовую сводку администратору группы в Telegram
    
    Args:
        group (Group): Объект группы.
        users (List[User]): Список пользователей группы для включения в сводку.
    
    Note:
        Функция запускается в отдельном потоке для предотвращения блокировки.
        При недоступности Gemini формирует базовый отчет.
        Длинные сообщения автоматически разбиваются на части.
    
    Examples:
        >>> from app.models.group import Group
        >>> from app.models.user import User
        >>> group = Group(...)
        >>> users = [user1, user2, user3]
        >>> generate_and_send_summary_for_group(group, users)
        # Сводка будет сгенерирована и отправлена админу группы
    """
    if not group.admin_username:
        logger.error(f"У группы '{group.name}' (ID: {group.id}) не настроен admin_username, не могу отправить сводку")
        return
    
    # Создаем сессию БД для поиска администратора
    db = SessionLocal()
    try:
        # Находим администратора группы по username
        from app.models.user import User
        admin_user = db.query(User).filter(User.username == group.admin_username).first()
        if not admin_user or not admin_user.user_id:
            logger.error(f"Не найден пользователь с username '{group.admin_username}' для группы '{group.name}' (ID: {group.id})")
            return
        # Собираем все ответы
        responses = []
        responded_users = []
        not_responded_users = []
        
        for user in users:
            # Используем full_name, если есть, иначе username, иначе ID
            if user.full_name:
                user_display = user.full_name
            elif user.username:
                user_display = f"@{user.username}"
            else:
                user_display = f"ID:{user.user_id}"
                
            if user.has_responded_today and user.last_response:
                responses.append(f"{user_display}: {user.last_response}")
                responded_users.append(user_display)
            else:
                not_responded_users.append(user_display)
        
        if not responses and not not_responded_users:
            logger.info("Нет пользователей для создания сводки")
            return
        
        # Формируем промпт для Gemini
        prompt = f"""
Создай краткую сводку планируемых работ команды на сегодня.

Ответы сотрудников:
{chr(10).join(responses) if responses else "Никто не ответил"}

Требования к сводке:
- Кратко и структурированно
- Выдели основные направления работы
- Укажи кто чем занимается (только тех, кто ответил)
- Общий объем текста на каждого сотрудника до 70 слов
- НЕ используй звездочки для выделения текста
- НЕ указывай дату в ответе
- Используй простое форматирование без специальных символов

Ответ должен быть в формате краткого отчета для руководителя.
В конце отчета обязательно укажи статус ответов: {f"Не ответили: {', '.join(not_responded_users)}" if not_responded_users else "Все участники команды предоставили свои планы"}.
"""
        
        # Генерируем сводку через Gemini
        logger.info("Генерируем сводку через Gemini...")
        
        # Используем синхронную версию
        try:
            summary = asyncio.run(gemini_service.generate_text_async(prompt))
        except RuntimeError:
            # Если есть проблемы с event loop, используем простую обертку
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, 
                    gemini_service.generate_text_async(prompt)
                )
                summary = future.result(timeout=60)
        
        if not summary:
            # Формируем базовый отчет если Gemini недоступен
            basic_summary = "⚠️ Не удалось сгенерировать сводку через Gemini. Базовый отчет:\n\n"
            if responses:
                basic_summary += "\n".join(responses)
            else:
                basic_summary += "Никто из команды не предоставил планы на сегодня."
            
            if not_responded_users:
                basic_summary += f"\n\nНе ответили: {', '.join(not_responded_users)}"
            
            summary = basic_summary
        
        # Формируем финальное сообщение для админа группы
        admin_message = f"📊 Утренняя сводка планов группы '{group.name}'\n"
        admin_message += f"📅 Дата: {datetime.now().strftime('%d/%m/%Y')}\n"
        admin_message += f"👥 Участников: {len(users)}\n"
        admin_message += f"✅ Ответили: {len(responded_users)}\n"
        admin_message += f"⏳ Не ответили: {len(not_responded_users)}\n\n"
        admin_message += summary
        
        # Отправляем администратору группы
        try:
            # Разбиваем длинные сообщения
            if len(admin_message) > 4000:
                parts = [admin_message[i:i+4000] for i in range(0, len(admin_message), 4000)]
                for i, part in enumerate(parts):
                    if i == 0:
                        bot.send_message(chat_id=int(admin_user.user_id), text=part)
                    else:
                        bot.send_message(chat_id=int(admin_user.user_id), text=f"(продолжение {i+1})\n{part}")
            else:
                bot.send_message(chat_id=int(admin_user.user_id), text=admin_message)
            
            admin_display_name = admin_user.full_name or f"@{group.admin_username}"
            logger.info(f"Сводка группы '{group.name}' успешно отправлена администратору {admin_display_name}")
            
        except Exception as e:
            admin_display_name = admin_user.full_name or f"@{group.admin_username}"
            logger.error(f"Ошибка отправки сводки группы '{group.name}' администратору {admin_display_name}: {e}")
            
    except Exception as e:
        logger.error(f"Ошибка генерации сводки группы '{group.name}': {e}")
    finally:
        db.close()

def generate_and_send_summary(users):
    """Генерирует сводку планов команды через Gemini AI (legacy-функция для обратной совместимости).
    
    Перебирает группы пользователей и генерирует отдельные сводки для каждой группы.
    Используется для обратной совместимости с существующим кодом.
    
    Args:
        users (List[User]): Список пользователей для включения в сводку.
    
    Examples:
        >>> users = [user1, user2, user3]
        >>> generate_and_send_summary(users)
        # Сводки будут сгенерированы для каждой группы отдельно
    """
    if not users:
        return
    
    # Группируем пользователей по группам
    from collections import defaultdict
    from app.models.group import Group
    
    db = SessionLocal()
    try:
        groups_users = defaultdict(list)
        
        for user in users:
            if user.group_id:
                groups_users[user.group_id].append(user)
            else:
                # Пользователи без группы - добавляем к группе по умолчанию
                default_group = db.query(Group).filter(Group.is_active == True).first()
                if default_group:
                    groups_users[default_group.id].append(user)
        
        # Генерируем сводки для каждой группы
        for group_id, group_users in groups_users.items():
            group = db.query(Group).filter(Group.id == group_id).first()
            if group:
                generate_and_send_summary_for_group(group, group_users)
                
    except Exception as e:
        logger.error(f"Ошибка в legacy-функции генерации сводки: {e}")
    finally:
        db.close()

def process_user_response(user, response_text):
    """Обрабатывает ответ пользователя на вечерний вопрос.
    
    Выполняет следующие действия:
    1. Сохраняет ответ пользователя в базе данных
    2. Сохраняет полную историю ответа в user_responses
    3. Обновляет информацию о пользователе (имя, username)
    4. Проверяет, ответили ли все участники для досрочной генерации сводки
    
    Args:
        user: Объект пользователя Telegram с атрибутами id, username, first_name, last_name.
        response_text (str): Текст ответа пользователя на вечерний вопрос.
    
    Note:
        Если все активные участники ответили, сводка генерируется досрочно.
        Автоматически отменяет запланированную задачу генерации через 1 час.
    
    Examples:
        >>> # Вызывается автоматически при получении сообщения от пользователя
        >>> process_user_response(telegram_user, "Сегодня работаю над проектом X")
    """
    _ensure_services_initialized()
    db = SessionLocal()
    try:
        # Обновляем информацию о пользователе - ищем по user_id
        db_user = db.query(User).filter(User.user_id == str(user.id)).first()
        if db_user:
            db_user.has_responded_today = True
            db_user.last_response = response_text
            
            # Обновляем username и полное имя
            if user.username:
                # Проверяем уникальность username
                existing_user = db.query(User).filter(
                    User.username == user.username,
                    User.id != db_user.id
                ).first()
                if not existing_user:
                    db_user.username = user.username
            
            if user.first_name:
                full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                db_user.full_name = full_name
            
            # ===== НОВАЯ ЛОГИКА: Сохраняем в историю ответов =====
            # Создаем запись в user_responses для истории
            user_response = UserResponse(
                user_id=db_user.id,
                response_text=response_text,
                telegram_user_id=str(user.id),
                telegram_username=user.username,
                full_name=db_user.full_name
            )
            db.add(user_response)
            
            db.commit()
            
            # Используем full_name для отображения, если есть
            if db_user.full_name:
                user_display = db_user.full_name
            elif db_user.username:
                user_display = f"@{db_user.username}"
            else:
                user_display = f"ID:{db_user.user_id}"
            
            logger.info(f"Обновлен ответ пользователя {user_display}, сохранен в историю (ID: {user_response.id})")
            
            # ===== НОВАЯ ЛОГИКА: Проверяем только участников той же группы =====
            if db_user.group_id:
                # Проверяем, ответили ли все активные участники ЭТОЙ ГРУППЫ (досрочная отправка)
                from app.models.group import Group
                
                group = db.query(Group).filter(Group.id == db_user.group_id).first()
                if group:
                    active_users_in_group = db.query(User).filter(
                        User.group_id == db_user.group_id,
                        User.is_active == True,
                        User.is_verified == True,  # Проверяем активацию
                        User.is_group_member == True  # Проверяем участие в команде
                    ).all()
                    responded_users_in_group = [u for u in active_users_in_group if u.has_responded_today]
                    
                    if len(responded_users_in_group) == len(active_users_in_group) and len(active_users_in_group) > 0:
                        logger.info(f"Все участники группы '{group.name}' ответили досрочно ({len(responded_users_in_group)}/{len(active_users_in_group)}). Генерируем сводку немедленно.")
                        
                        # Отменяем запланированную задачу для этой группы через 1 час
                        try:
                            job_id = f'summary_group_{db_user.group_id}_after_1hour'
                            if scheduler.get_job(job_id):
                                scheduler.remove_job(job_id)
                                logger.info(f"Отменена запланированная задача генерации сводки для группы '{group.name}' через 1 час")
                        except Exception as e:
                            logger.warning(f"Не удалось отменить запланированную задачу для группы '{group.name}': {e}")
                        
                        # Генерируем сводку для группы немедленно В ОТДЕЛЬНОМ ПОТОКЕ
                        threading.Thread(
                            target=generate_and_send_summary_for_group, 
                            args=(group, active_users_in_group), 
                            daemon=True
                        ).start()
                        logger.info(f"Генерация сводки для группы '{group.name}' запущена в отдельном потоке")
                    else:
                        logger.info(f"В группе '{group.name}' ответили {len(responded_users_in_group)}/{len(active_users_in_group)} участников. Ждем остальных или истечения времени.")
                else:
                    logger.warning(f"Группа с ID {db_user.group_id} не найдена")
            else:
                logger.warning(f"Пользователь {user_display} не привязан ни к одной группе")
            
        else:
            logger.warning(f"Пользователь с user_id {user.id} не найден в базе")
            
    except Exception as e:
        logger.error(f"Ошибка обработки ответа пользователя: {e}")
        db.rollback()
    finally:
        db.close()

def send_repeat_questions():
    """Отправляет повторные вопросы всем активным участникам команды по запросу админа.
    
    Выполняет следующие действия:
    1. Получает список активных и активированных участников
    2. Отправляет повторный вопрос каждому участнику
    3. Логирует результаты отправки
    
    Функция вызывается при нажатии кнопки "Сбросить ответы дня" в админ панели.
    Не сбрасывает флаги ответов в базе данных - только отправляет сообщения.
    
    Returns:
        dict: Словарь с результатами отправки {"success_count": int, "total_count": int, "errors": list}
    
    Examples:
        >>> result = send_repeat_questions()
        >>> print(f"Отправлено {result['success_count']}/{result['total_count']} сообщений")
    """
    _ensure_services_initialized()
    db = SessionLocal()
    try:
        # Получаем активных И активированных пользователей
        active_users = db.query(User).filter(
            User.is_active == True,
            User.is_verified == True,
            User.is_group_member == True,
            User.has_responded_today == False
        ).all()
        
        if not active_users:
            logger.info("Нет активных активированных участников команды для повторной рассылки")
            return {"success_count": 0, "total_count": 0, "errors": []}
        
        # Формируем сообщение с указанием что это повторная отправка
        question = "🔄 Повторное напоминание от администратора!\n\n🌅 Мне нужно знать, какие задачи вчера получилось решить и какой план на сегодня. Какие сложности возникли?\n\n📝 Пожалуйста, отправьте ваш отчет."
        
        success_count = 0
        errors = []
        
        for user in active_users:
            try:
                bot.send_message(
                    chat_id=int(user.user_id),
                    text=question
                )
                success_count += 1
                username_display = f"@{user.username}" if user.username else f"ID:{user.user_id}"
                logger.info(f"Повторное сообщение отправлено пользователю {username_display}")
            except Exception as e:
                username_display = f"@{user.username}" if user.username else f"ID:{user.user_id}"
                error_msg = f"Ошибка отправки повторного сообщения пользователю {username_display}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        logger.info(f"Повторная рассылка завершена. Отправлено сообщений: {success_count}/{len(active_users)}")
        
        return {
            "success_count": success_count,
            "total_count": len(active_users),
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Ошибка в повторной рассылке: {e}")
        return {"success_count": 0, "total_count": 0, "errors": [str(e)]}
    finally:
        db.close()

def send_test_message(user_id: str, message: str = "🔔 Тестовое сообщение от бота"):
    """Отправляет тестовое сообщение конкретному пользователю.
    
    Функция для диагностики работы Telegram бота.
    Позволяет проверить связь с пользователем и корректность настроек.
    
    Args:
        user_id (str): Telegram User ID получателя.
        message (str): Текст сообщения для отправки.
    
    Returns:
        dict: Результат отправки {"success": bool, "error": str|None}
    
    Examples:
        >>> result = send_test_message("123456789", "Привет!")
        >>> if result["success"]:
        ...     print("Сообщение отправлено")
        ... else:
        ...     print(f"Ошибка: {result['error']}")
    """
    _ensure_services_initialized()
    try:
        bot.send_message(chat_id=int(user_id), text=message)
        logger.info(f"Тестовое сообщение отправлено пользователю {user_id}")
        return {"success": True, "error": None}
    except Exception as e:
        error_msg = f"Ошибка отправки тестового сообщения пользователю {user_id}: {e}"
        logger.error(error_msg)
        return {"success": False, "error": str(e)}

def start_scheduler():
    """Запускает планировщик задач для утренних опросов по группам.
    
    Выполняет следующие действия:
    1. Инициализирует все необходимые сервисы
    2. Удаляет существующие задачи при повторном запуске
    3. Создает индивидуальные задачи для каждой активной группы
    4. Запускает планировщик в фоновом режиме
    
    Note:
        Каждая группа имеет свое расписание (morning_hour, morning_minute, timezone).
        Планировщик работает в фоновом режиме и не блокирует основной поток.
    
    Raises:
        Exception: При ошибках инициализации планировщика.
    
    Examples:
        >>> start_scheduler()
        # Планировщик запущен, для каждой группы созданы отдельные задачи
    """
    _ensure_services_initialized()
    try:
        logger.info("🔄 Инициализация планировщика групп...")
        
        from app.models.group import Group
        db = SessionLocal()
        
        try:
            # Получаем все активные группы
            active_groups = db.query(Group).filter(Group.is_active == True).all()
            logger.info(f"Найдено активных групп: {len(active_groups)}")
            
            # ВСЕГДА удаляем существующие задачи для обновления расписания
            existing_jobs = scheduler.get_jobs()
            logger.info(f"Найдено существующих задач: {len(existing_jobs)}")
            
            # Удаляем все старые задачи (как legacy, так и group-based)
            for job in existing_jobs:
                if (job.id == 'morning_questions' or 
                    job.id.startswith('morning_group_') or 
                    job.id.startswith('summary_group_')):
                    scheduler.remove_job(job.id)
                    logger.info(f"✅ Удалена существующая задача: {job.id}")
            
            # Создаем задачи для каждой группы
            created_jobs = 0
            for group in active_groups:
                try:
                    job_id = f'morning_group_{group.id}'
                    
                    # Создаем задачу утренней рассылки для группы
                    scheduler.add_job(
                        send_morning_questions_to_group,
                        'cron',
                        args=[group.id],
                        hour=group.morning_hour,
                        minute=group.morning_minute,
                        id=job_id,
                        timezone=group.timezone
                    )
                    
                    schedule_time = f"{group.morning_hour:02d}:{group.morning_minute:02d} {group.timezone}"
                    logger.info(f"✅ Создана задача для группы '{group.name}' (ID: {group.id}): {schedule_time}")
                    created_jobs += 1
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка создания задачи для группы '{group.name}' (ID: {group.id}): {e}")
            
            logger.info(f"✅ Создано задач рассылки: {created_jobs}/{len(active_groups)}")
            
            # Добавляем legacy-задачу для обратной совместимости (если нет групп)
            if len(active_groups) == 0:
                scheduler.add_job(
                    send_morning_questions,
                    'cron',
                    hour=9,
                    minute=30,
                    id='morning_questions_legacy',
                    timezone='Asia/Bishkek'
                )
                logger.info("✅ Добавлена legacy-задача (нет групп в системе)")
            
        finally:
            db.close()
        
        # Запускаем планировщик только если он еще не запущен
        if not scheduler.running:
            scheduler.start()
            logger.info("✅ Scheduler запущен с индивидуальными расписаниями групп")
        else:
            logger.info("✅ Scheduler уже работает, задачи групп обновлены")
        
        # Выводим все активные задачи для диагностики
        active_jobs = scheduler.get_jobs()
        logger.info(f"📋 Активных задач в планировщике: {len(active_jobs)}")
        for job in active_jobs:
            if hasattr(job, 'next_run_time') and job.next_run_time:
                logger.info(f"   - {job.id}: {job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            else:
                logger.info(f"   - {job.id}: (не запланирована)")
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска планировщика: {e}")

def stop_scheduler():
    """Останавливает планировщик задач.
    
    Корректно завершает работу планировщика и освобождает ресурсы.
    Останавливает все запланированные задачи.
    
    Note:
        Функция безопасна для повторного вызова.
        Если планировщик уже остановлен, функция завершается без ошибок.
    
    Examples:
        >>> stop_scheduler()
        # Планировщик остановлен, задачи больше не выполняются
    """
    _ensure_services_initialized()
    try:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("✅ Scheduler остановлен")
    except Exception as e:
        logger.error(f"❌ Ошибка остановки планировщика: {e}")

def get_scheduler_info():
    """Получает информацию о планировщике и активных задачах.
    
    Возвращает статус планировщика, список активных задач
    и время их следующего выполнения для диагностики.
    
    Returns:
        dict: Информация о планировщике {
            "running": bool,
            "jobs_count": int,
            "jobs": list,
            "next_morning_questions": str|None
        }
    
    Examples:
        >>> info = get_scheduler_info()
        >>> print(f"Планировщик работает: {info['running']}")
        >>> print(f"Следующая рассылка: {info['next_morning_questions']}")
    """
    try:
        _ensure_services_initialized()
        
        if not scheduler:
            return {
                "running": False,
                "jobs_count": 0,
                "jobs": [],
                "next_morning_questions": None,
                "error": "Планировщик не инициализирован"
            }
        
        jobs = scheduler.get_jobs()
        jobs_info = []
        next_morning_questions = None
        
        for job in jobs:
            job_info = {
                "id": job.id,
                "name": str(job.func.__name__) if hasattr(job.func, '__name__') else str(job.func),
                "next_run_time": job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z') if job.next_run_time else None,
                "trigger": str(job.trigger)
            }
            jobs_info.append(job_info)
            
            if job.id == 'morning_questions' and job.next_run_time:
                next_morning_questions = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        
        return {
            "running": scheduler.running,
            "jobs_count": len(jobs),
            "jobs": jobs_info,
            "next_morning_questions": next_morning_questions,
            "error": None
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о планировщике: {e}")
        return {
            "running": False,
            "jobs_count": 0,
            "jobs": [],
            "next_morning_questions": None,
            "error": str(e)
        }

# Экспортируем функцию для обработки ответов пользователей
__all__ = ['start_scheduler', 'stop_scheduler', 'process_user_response', 'send_repeat_questions', 'send_test_message', 'get_scheduler_info']
