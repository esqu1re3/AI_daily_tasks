# Планировщик утренних вопросов и сводки через Gemini
import asyncio
import telebot
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import settings
from app.core.database import SessionLocal
from app.models.user import User
from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

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
    """Утренняя рассылка вопросов в 9:00 UTC+6"""
    db = SessionLocal()
    try:
        # Сбрасываем флаги ответов на новый день
        db.query(User).update({
            User.has_responded_today: False,
            User.last_response: None
        })
        db.commit()
        
        # Получаем активных пользователей
        active_users = db.query(User).filter(
            User.is_active == True
        ).all()
        
        if not active_users:
            logger.info("Нет активных пользователей для рассылки")
            return
        
        question = "🌅 Доброе утро! Какие задачи планируете решать сегодня?"
        
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
        
        # Запускаем проверку ответов через некоторое время
        scheduler.add_job(
            check_responses_and_generate_summary,
            'date',
            run_date=datetime.now() + timedelta(hours=2),  # Проверяем через 2 часа
            id='check_responses_first'
        )
        
    except Exception as e:
        logger.error(f"Ошибка в утренней рассылке: {e}")
    finally:
        db.close()

def check_responses_and_generate_summary():
    """Проверка ответов и генерация сводки если все ответили"""
    db = SessionLocal()
    try:
        # Получаем активных пользователей
        active_users = db.query(User).filter(
            User.is_active == True
        ).all()
        
        if not active_users:
            logger.info("Нет активных пользователей")
            return
        
        # Проверяем кто ответил
        responded_users = [user for user in active_users if user.has_responded_today]
        not_responded_users = [user for user in active_users if not user.has_responded_today]
        
        logger.info(f"Статус ответов: {len(responded_users)}/{len(active_users)} пользователей ответили")
        
        if len(not_responded_users) == 0:
            # Все ответили - генерируем сводку
            logger.info("Все пользователи ответили, генерируем сводку")
            generate_and_send_summary(active_users)
        else:
            # Не все ответили - планируем следующую проверку
            current_hour = datetime.now().hour
            
            if current_hour < 18:  # До 18:00 продолжаем ждать
                next_check = datetime.now() + timedelta(hours=1)
                scheduler.add_job(
                    check_responses_and_generate_summary,
                    'date',
                    run_date=next_check,
                    id=f'check_responses_{next_check.strftime("%H%M")}'
                )
                logger.info(f"Не все ответили, следующая проверка в {next_check.strftime('%H:%M')}")
            else:
                # После 18:00 отправляем сводку с тем что есть
                logger.info("Рабочий день закончился, отправляем сводку с полученными ответами")
                generate_and_send_summary(active_users)
                
    except Exception as e:
        logger.error(f"Ошибка при проверке ответов: {e}")
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
            username_display = f"@{user.username}" if user.username else f"ID:{user.user_id}"
            if user.has_responded_today and user.last_response:
                responses.append(f"{username_display}: {user.last_response}")
                responded_users.append(username_display)
            else:
                responses.append(f"{username_display}: Не ответил")
                not_responded_users.append(username_display)
        
        if not responses:
            logger.info("Нет ответов для создания сводки")
            return
        
        # Формируем дополнительную информацию о статусе ответов
        status_info = ""
        if not_responded_users:
            status_info = f"\n\nСтатус ответов: {len(responded_users)} из {len(users)} сотрудников ответили. Не ответили: {', '.join(not_responded_users)}"
        else:
            status_info = f"\n\nСтатус ответов: Все {len(users)} сотрудников предоставили свои планы."
        
        # Формируем промпт для Gemini
        prompt = f"""
Создай краткую сводку планируемых работ команды на сегодня.

Ответы сотрудников:
{chr(10).join(responses)}{status_info}

Требования к сводке:
- Кратко и структурированно
- Выдели основные направления работы
- Укажи кто чем занимается
- Упомяни о неответивших ТОЛЬКО если они есть в статусе ответов
- Общий объем текста до 500 слов
- НЕ используй звездочки для выделения текста
- НЕ указывай дату в ответе
- Используй простое форматирование без специальных символов

Ответ должен быть в формате краткого отчета для руководителя.
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
            summary = "⚠️ Не удалось сгенерировать сводку через Gemini. Используется базовый отчет:\n\n" + "\n".join(responses)
        
        # Формируем финальное сообщение для админа
        final_message = f"📊 Утренняя сводка планов команды\n"
        final_message += f"📅 Дата: {datetime.now().strftime('%d/%m/%Y')}\n"
        final_message += f"👥 Участников: {len(users)}\n\n"
        final_message += summary
        
        # Отправляем админу
        try:
            # Разбиваем длинные сообщения
            if len(final_message) > 4000:
                parts = [final_message[i:i+4000] for i in range(0, len(final_message), 4000)]
                for i, part in enumerate(parts):
                    if i == 0:
                        bot.send_message(chat_id=ADMIN_ID, text=part)
                    else:
                        bot.send_message(chat_id=ADMIN_ID, text=f"(продолжение {i+1})\n{part}")
            else:
                bot.send_message(chat_id=ADMIN_ID, text=final_message)
            
            logger.info("Сводка успешно отправлена админу")
            
        except Exception as e:
            logger.error(f"Ошибка отправки сводки админу: {e}")
            
    except Exception as e:
        logger.error(f"Ошибка генерации сводки: {e}")

def process_user_response(user, response_text):
    """Обработка ответа пользователя на утренний вопрос"""
    db = SessionLocal()
    try:
        # Обновляем информацию о пользователе
        db_user = db.query(User).filter(User.user_id == str(user.id)).first()
        if db_user:
            db_user.has_responded_today = True
            db_user.last_response = response_text
            
            # Обновляем username и полное имя если их нет
            if user.username and not db_user.username:
                db_user.username = user.username
            
            if not db_user.full_name and user.first_name:
                full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                db_user.full_name = full_name
            
            db.commit()
            username_display = f"@{db_user.username}" if db_user.username else f"ID:{db_user.user_id}"
            logger.info(f"Обновлен ответ пользователя {username_display}")
            
            # Проверяем, не ответили ли все пользователи
            check_if_all_responded()
            
        else:
            logger.warning(f"Пользователь с user_id {user.id} не найден в базе")
            
    except Exception as e:
        logger.error(f"Ошибка обработки ответа пользователя: {e}")
    finally:
        db.close()

def check_if_all_responded():
    """Проверка, ответили ли все пользователи (для досрочной отправки сводки)"""
    db = SessionLocal()
    try:
        active_users = db.query(User).filter(
            User.is_active == True
        ).all()
        
        responded_users = [user for user in active_users if user.has_responded_today]
        
        if len(responded_users) == len(active_users) and len(active_users) > 0:
            logger.info("Все пользователи ответили досрочно, генерируем сводку")
            # Отменяем запланированные проверки
            for job in scheduler.get_jobs():
                if job.id.startswith('check_responses'):
                    scheduler.remove_job(job.id)
            
            # Генерируем сводку
            generate_and_send_summary(active_users)
            
    except Exception as e:
        logger.error(f"Ошибка проверки всех ответов: {e}")
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
        
        # Утренняя рассылка в 17:57 по времени Бишкек (UTC+6)
        scheduler.add_job(
            send_morning_questions,
            'cron',
            hour=19,  # 17:57 по Бишкеку
            minute=6,
            id='morning_questions',
            timezone='Asia/Bishkek'
        )
        
        if not scheduler.running:
            scheduler.start()
            logger.info("✅ Scheduler запущен (утренняя рассылка в 17:57 Asia/Bishkek)")
        
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
