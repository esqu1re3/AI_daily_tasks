# Планировщик утренних вопросов и сводки через Gemini
import asyncio
import telebot
import logging
import threading
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import settings
from app.core.database import SessionLocal
from app.models.user import User
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

def send_morning_questions():
    """Отправляет утренние вопросы всем активным участникам команды.
    
    Выполняет следующие действия:
    1. Сбрасывает флаги ответов для нового дня
    2. Получает список активных и активированных участников
    3. Отправляет утренний вопрос каждому участнику
    4. Планирует генерацию сводки через 1 час
    
    Функция запускается автоматически планировщиком в заданное время.
    Обрабатывает ошибки отправки сообщений индивидуально для каждого пользователя.
    
    Note:
        Время выполнения настраивается в start_scheduler().
        По умолчанию: 9:30 по времени Asia/Bishkek.
    
    Examples:
        >>> # Функция вызывается автоматически планировщиком
        >>> # Вручную можно вызвать для тестирования:
        >>> send_morning_questions()
    """
    _ensure_services_initialized()
    db = SessionLocal()
    try:
        # Сбрасываем флаги ответов на новый день
        db.query(User).update({
            User.has_responded_today: False,
            User.last_response: None
        })
        db.commit()
        
        # Получаем активных И активированных пользователей
        active_users = db.query(User).filter(
            User.is_active == True,
            User.is_verified == True,  # Проверяем активацию
            User.is_group_member == True  # Проверяем участие в команде
        ).all()
        
        if not active_users:
            logger.info("Нет активных активированных участников команды для рассылки")
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
                logger.info(f"Утреннее сообщение отправлено пользователю {username_display}")
            except Exception as e:
                username_display = f"@{user.username}" if user.username else f"ID:{user.user_id}"
                logger.error(f"Ошибка отправки утреннего сообщения пользователю {username_display}: {e}")
        
        logger.info(f"Утренняя рассылка завершена. Отправлено сообщений: {success_count}/{len(active_users)}")
        
        # Запланируем генерацию сводки ровно через 1 час
        summary_time = datetime.now() + timedelta(hours=1)
        scheduler.add_job(
            generate_summary_after_timeout,
            'date',
            run_date=summary_time,
            id='summary_after_1hour'
        )
        
        logger.info(f"Сводка будет сгенерирована в {summary_time.strftime('%H:%M:%S')} (через 1 час)")
        
    except Exception as e:
        logger.error(f"Ошибка в утренней рассылке: {e}")
    finally:
        db.close()

def generate_summary_after_timeout():
    """Генерирует сводку после истечения времени ожидания ответов.
    
    Запускается автоматически через 1 час после отправки утренних вопросов.
    Собирает статистику ответов и запускает генерацию сводки в отдельном потоке.
    
    Выполняет следующие действия:
    1. Получает список активных участников команды
    2. Определяет кто ответил, а кто нет
    3. Запускает генерацию сводки в отдельном потоке
    
    Note:
        Использует многопоточность для предотвращения блокировки планировщика
        во время генерации сводки через Gemini API.
    
    Examples:
        >>> # Функция вызывается автоматически планировщиком
        >>> # Вручную можно вызвать для тестирования:
        >>> generate_summary_after_timeout()
    """
    db = SessionLocal()
    try:
        # Получаем активных активированных участников команды
        active_users = db.query(User).filter(
            User.is_active == True,
            User.is_verified == True,  # Проверяем активацию
            User.is_group_member == True  # Проверяем участие в команде
        ).all()
        
        if not active_users:
            logger.info("Нет активных активированных участников команды для генерации сводки")
            return
        
        # Проверяем кто ответил
        responded_users = [user for user in active_users if user.has_responded_today]
        not_responded_users = [user for user in active_users if not user.has_responded_today]
        
        logger.info(f"Время истекло. Статус ответов: {len(responded_users)}/{len(active_users)} участников ответили")
        
        # Генерируем сводку с тем что есть В ОТДЕЛЬНОМ ПОТОКЕ
        threading.Thread(
            target=generate_and_send_summary, 
            args=(active_users,), 
            daemon=True
        ).start()
        logger.info("Генерация сводки по таймауту запущена в отдельном потоке")
                
    except Exception as e:
        logger.error(f"Ошибка при генерации сводки по таймауту: {e}")
    finally:
        db.close()

def generate_and_send_summary(users):
    """Генерирует сводку планов команды через Gemini AI и отправляет администратору.
    
    Выполняет следующие действия:
    1. Собирает все ответы участников команды
    2. Формирует промпт для Gemini API
    3. Генерирует сводку через Gemini AI
    4. Отправляет готовую сводку администратору в Telegram
    
    Args:
        users (List[User]): Список пользователей для включения в сводку.
    
    Note:
        Функция запускается в отдельном потоке для предотвращения блокировки.
        При недоступности Gemini формирует базовый отчет.
        Длинные сообщения автоматически разбиваются на части.
    
    Examples:
        >>> from app.models.user import User
        >>> users = [user1, user2, user3]
        >>> generate_and_send_summary(users)
        # Сводка будет сгенерирована и отправлена админу
    """
    if not ADMIN_ID:
        logger.error("ADMIN_ID не настроен, не могу отправить сводку")
        return
    
    try:
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
        
        # Формируем финальное сообщение для админа
        admin_message = f"📊 Утренняя сводка планов команды\n"
        admin_message += f"📅 Дата: {datetime.now().strftime('%d/%m/%Y')}\n"
        admin_message += f"👥 Участников: {len(users)}\n"
        admin_message += f"✅ Ответили: {len(responded_users)}\n"
        admin_message += f"⏳ Не ответили: {len(not_responded_users)}\n\n"
        admin_message += summary
        
        # Отправляем админу
        try:
            # Разбиваем длинные сообщения
            if len(admin_message) > 4000:
                parts = [admin_message[i:i+4000] for i in range(0, len(admin_message), 4000)]
                for i, part in enumerate(parts):
                    if i == 0:
                        bot.send_message(chat_id=ADMIN_ID, text=part)
                    else:
                        bot.send_message(chat_id=ADMIN_ID, text=f"(продолжение {i+1})\n{part}")
            else:
                bot.send_message(chat_id=ADMIN_ID, text=admin_message)
            
            logger.info("Сводка успешно отправлена админу")
            
        except Exception as e:
            logger.error(f"Ошибка отправки сводки админу: {e}")
            
    except Exception as e:
        logger.error(f"Ошибка генерации сводки: {e}")

def process_user_response(user, response_text):
    """Обрабатывает ответ пользователя на утренний вопрос.
    
    Выполняет следующие действия:
    1. Сохраняет ответ пользователя в базе данных
    2. Обновляет информацию о пользователе (имя, username)
    3. Проверяет, ответили ли все участники для досрочной генерации сводки
    
    Args:
        user: Объект пользователя Telegram с атрибутами id, username, first_name, last_name.
        response_text (str): Текст ответа пользователя на утренний вопрос.
    
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
            
            db.commit()
            
            # Используем full_name для отображения, если есть
            if db_user.full_name:
                user_display = db_user.full_name
            elif db_user.username:
                user_display = f"@{db_user.username}"
            else:
                user_display = f"ID:{db_user.user_id}"
            
            logger.info(f"Обновлен ответ пользователя {user_display}")
            
            # Проверяем, ответили ли все активные активированные участники команды (досрочная отправка)
            active_users = db.query(User).filter(
                User.is_active == True,
                User.is_verified == True,  # Проверяем активацию
                User.is_group_member == True  # Проверяем участие в команде
            ).all()
            responded_users = [u for u in active_users if u.has_responded_today]
            
            if len(responded_users) == len(active_users) and len(active_users) > 0:
                logger.info(f"Все участники ответили досрочно ({len(responded_users)}/{len(active_users)}). Генерируем сводку немедленно.")
                
                # Отменяем запланированную задачу через 1 час
                try:
                    if scheduler.get_job('summary_after_1hour'):
                        scheduler.remove_job('summary_after_1hour')
                        logger.info("Отменена запланированная задача генерации сводки через 1 час")
                except Exception as e:
                    logger.warning(f"Не удалось отменить запланированную задачу: {e}")
                
                # Генерируем сводку немедленно В ОТДЕЛЬНОМ ПОТОКЕ
                threading.Thread(
                    target=generate_and_send_summary, 
                    args=(active_users,), 
                    daemon=True
                ).start()
                logger.info("Генерация сводки запущена в отдельном потоке")
            else:
                logger.info(f"Ответили {len(responded_users)}/{len(active_users)} участников. Ждем остальных или истечения времени.")
            
        else:
            logger.warning(f"Пользователь с user_id {user.id} не найден в базе")
            
    except Exception as e:
        logger.error(f"Ошибка обработки ответа пользователя: {e}")
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
            User.is_verified == True,  # Проверяем активацию
            User.is_group_member == True  # Проверяем участие в команде
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
    """Запускает планировщик задач для утренних опросов.
    
    Выполняет следующие действия:
    1. Инициализирует все необходимые сервисы
    2. Удаляет существующие задачи при повторном запуске
    3. Настраивает утреннюю рассылку по расписанию
    4. Запускает планировщик в фоновом режиме
    
    Note:
        По умолчанию утренняя рассылка настроена на 9:30 по времени Asia/Bishkek.
        Планировщик работает в фоновом режиме и не блокирует основной поток.
    
    Raises:
        Exception: При ошибках инициализации планировщика.
    
    Examples:
        >>> start_scheduler()
        # Планировщик запущен, утренние вопросы будут отправляться автоматически
    """
    _ensure_services_initialized()
    try:
        logger.info("🔄 Инициализация планировщика...")
        
        # ВСЕГДА удаляем существующие задачи для обновления расписания
        existing_jobs = scheduler.get_jobs()
        logger.info(f"Найдено существующих задач: {len(existing_jobs)}")
        
        for job in existing_jobs:
            if job.id == 'morning_questions':
                scheduler.remove_job(job.id)
                logger.info("✅ Удалена существующая задача morning_questions")
        
        # ВСЕГДА добавляем задачу с актуальным временем
        scheduler.add_job(
            send_morning_questions,
            'cron',
            hour=17,   # 9:30 по Бишкеку (UTC+6)
            minute=30,
            id='morning_questions',
            timezone='Asia/Bishkek'
        )
        logger.info("✅ Добавлена задача morning_questions с обновленным расписанием (9:30 Asia/Bishkek)")
        
        # Запускаем планировщик только если он еще не запущен
        if not scheduler.running:
            scheduler.start()
            logger.info("✅ Scheduler запущен (утренняя рассылка в 9:30 Asia/Bishkek, только активированным участникам)")
        else:
            logger.info("✅ Scheduler уже работает, задачи обновлены (утренняя рассылка в 9:30 Asia/Bishkek)")
        
        # Выводим все активные задачи для диагностики
        active_jobs = scheduler.get_jobs()
        logger.info(f"📋 Активных задач в планировщике: {len(active_jobs)}")
        for job in active_jobs:
            logger.info(f"   - {job.id}: {job.next_run_time}")
        
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
