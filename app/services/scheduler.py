# Планировщик утренних вопросов и сводки через Gemini
import asyncio
import telebot
import logging
import threading
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import get_settings
from app.core.database import SessionLocal
from app.models.user import User
from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

settings = get_settings()

# Создаем экземпляр бота и сервисов
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
    """Утренняя рассылка вопросов в 9:30 UTC+6"""
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
        
        question = "🌅 Доброе утро! Мне нужно знать, какие задачи вчера получилось решить и какой план на сегодня. Какие сложности возникли?"
        
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
    """Генерация сводки через 1 час после отправки утренних сообщений"""
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
    """Генерация сводки через Gemini и отправка админу"""
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
    """Обработка ответа пользователя на утренний вопрос"""
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

def start_scheduler():
    """Запуск планировщика задач"""
    try:
        # Проверяем, не запущен ли уже планировщик
        if scheduler.running:
            logger.info("Scheduler уже запущен, пропускаем инициализацию")
            return
            
        # Удаляем существующие задачи если есть
        existing_jobs = scheduler.get_jobs()
        for job in existing_jobs:
            if job.id == 'morning_questions':
                scheduler.remove_job(job.id)
                logger.info("Удалена существующая задача morning_questions")
        
        # Утренняя рассылка в 9:30 по времени Бишкек (UTC+6)
        scheduler.add_job(
            send_morning_questions,
            'cron',
            hour=9,  # 9:30 по Бишкеку
            minute=30,
            id='morning_questions',
            timezone='Asia/Bishkek'
        )
        
        if not scheduler.running:
            scheduler.start()
            logger.info("✅ Scheduler запущен (утренняя рассылка в 9:30 Asia/Bishkek, только активированным участникам)")
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска планировщика: {e}")

def stop_scheduler():
    """Остановка планировщика"""
    try:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("✅ Scheduler остановлен")
    except Exception as e:
        logger.error(f"❌ Ошибка остановки планировщика: {e}")

# Экспортируем функцию для обработки ответов пользователей
__all__ = ['start_scheduler', 'stop_scheduler', 'process_user_response']
